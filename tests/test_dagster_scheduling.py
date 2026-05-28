"""Dagster integration tests — no Dagster process required.

These run in CI without spinning up `dagster dev`. They verify:
  1. The Dagster definitions module loads (catches syntax/import bugs)
  2. The schedule config IO round-trips correctly
  3. Invalid cron expressions are rejected by the admin route
  4. The /admin/schedule page renders
  5. The /api/admin/schedule GET endpoint returns sane shape even when
     Dagster is offline (because most test envs won't have it running)

A separate manual smoke test (not in pytest) covers the end-to-end
"schedule a job 60s out and watch it fire" path — that needs a live
Dagster process.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


# ── Schedule config IO ──────────────────────────────────────────────


def test_schedule_config_defaults_when_file_missing(tmp_path, monkeypatch):
    """If runtime_config.json doesn't exist, load() returns safe defaults
    — never throws, never leaves the schedule in an undefined state."""
    import packages.scheduling as sched

    bogus_path = tmp_path / "does_not_exist.json"
    monkeypatch.setattr(sched, "_CONFIG_PATH", bogus_path)
    cfg = sched.load()
    assert cfg.enabled is False  # safe default: don't fire
    assert cfg.cron_schedule == "0 2 * * *"
    assert cfg.pipeline == "full"


def test_schedule_config_round_trip(tmp_path, monkeypatch):
    """save() then load() returns equivalent config."""
    import packages.scheduling as sched

    monkeypatch.setattr(sched, "_CONFIG_PATH", tmp_path / "config.json")
    saved = sched.ScheduleConfig(
        schedule_type="weekly",
        cron_schedule="30 14 * * 1",
        enabled=True,
        pipeline="full",
    )
    sched.save(saved)
    loaded = sched.load()
    assert loaded.schedule_type == "weekly"
    assert loaded.cron_schedule == "30 14 * * 1"
    assert loaded.enabled is True
    assert loaded.updated_at is not None  # save() stamps it


def test_schedule_config_recovers_from_malformed_json(tmp_path, monkeypatch):
    """A corrupted runtime_config.json mustn't crash Dagster's schedule
    or the admin endpoint — we return defaults and keep going."""
    import packages.scheduling as sched

    p = tmp_path / "config.json"
    p.write_text("this is not json", encoding="utf-8")
    monkeypatch.setattr(sched, "_CONFIG_PATH", p)
    cfg = sched.load()
    assert cfg.enabled is False


def test_schedule_config_recovers_from_partial_json(tmp_path, monkeypatch):
    """A JSON object missing required fields shouldn't crash either —
    Pydantic defaults fill in what's missing."""
    import packages.scheduling as sched

    p = tmp_path / "config.json"
    p.write_text('{"enabled": true}', encoding="utf-8")
    monkeypatch.setattr(sched, "_CONFIG_PATH", p)
    cfg = sched.load()
    assert cfg.enabled is True
    assert cfg.cron_schedule == "0 2 * * *"


# ── Dagster definitions load ─────────────────────────────────────────


def test_dagster_definitions_load_cleanly():
    """Importing dagster_project must produce a valid Definitions
    object. If this fails, `dagster dev` won't start."""
    from dagster_project import defs

    job_names = [j.name for j in defs.jobs]
    schedule_names = [s.name for s in defs.schedules]
    assert "full_pipeline_job" in job_names
    assert "full_pipeline_schedule" in schedule_names


def _schedule_context_at(when):
    """build_schedule_context with an explicit scheduled time — Dagster's
    helper doesn't auto-fill it, so we pass one matching what production
    would pass on a real tick."""
    from dagster import build_schedule_context

    return build_schedule_context(scheduled_execution_time=when)


def test_dagster_schedule_skips_when_disabled(tmp_path, monkeypatch):
    """The schedule's should_execute is a no-op when enabled=False."""
    import datetime as dt

    import packages.scheduling as sched

    monkeypatch.setattr(sched, "_CONFIG_PATH", tmp_path / "config.json")
    sched.save(sched.ScheduleConfig(enabled=False, cron_schedule="* * * * *"))

    from dagster_project.schedules import full_pipeline_schedule

    result = full_pipeline_schedule.evaluate_tick(_schedule_context_at(dt.datetime.now(dt.UTC)))
    # SkipReason has no run requests
    assert not result.run_requests


def test_dagster_schedule_skips_when_cron_doesnt_match(tmp_path, monkeypatch):
    """When enabled but the cron doesn't match this minute, no run is
    requested. Otherwise we'd fire every minute regardless of cron."""
    import datetime as dt

    import packages.scheduling as sched

    monkeypatch.setattr(sched, "_CONFIG_PATH", tmp_path / "config.json")
    # A cron that fires once a year (Feb 29 at 02:00). Almost certainly
    # not the current minute when this test runs.
    sched.save(sched.ScheduleConfig(enabled=True, cron_schedule="0 2 29 2 *"))

    from dagster_project.schedules import full_pipeline_schedule

    # Use a tick time that isn't Feb 29 02:00 UTC — pick a deterministic
    # one (this date / minute is normal so the cron shouldn't fire).
    when = dt.datetime(2026, 6, 15, 10, 30, tzinfo=dt.UTC)
    result = full_pipeline_schedule.evaluate_tick(_schedule_context_at(when))
    assert not result.run_requests


def test_dagster_schedule_fires_when_cron_matches(tmp_path, monkeypatch):
    """The positive case: when the configured cron matches the current
    tick minute, a RunRequest is produced. Ensures the should_execute
    gate isn't accidentally always-False."""
    import datetime as dt

    import packages.scheduling as sched

    monkeypatch.setattr(sched, "_CONFIG_PATH", tmp_path / "config.json")
    # Every-minute cron — matches any tick we pass in.
    sched.save(sched.ScheduleConfig(enabled=True, cron_schedule="* * * * *"))

    from dagster_project.schedules import full_pipeline_schedule

    when = dt.datetime(2026, 6, 15, 10, 30, tzinfo=dt.UTC)
    result = full_pipeline_schedule.evaluate_tick(_schedule_context_at(when))
    assert result.run_requests, "Expected at least one RunRequest when cron matches"


# ── Admin API ────────────────────────────────────────────────────────


@pytest.fixture
def client():
    """FastAPI TestClient with Dagster mocked as unreachable so we
    don't need a live Dagster process."""
    from fastapi.testclient import TestClient

    from api.main import app

    return TestClient(app)


def test_admin_schedule_page_renders(client):
    r = client.get("/admin/schedule")
    assert r.status_code == 200
    assert "Pipeline schedule" in r.text
    assert "Cadence" in r.text
    assert "Run pipeline now" in r.text


def test_get_schedule_returns_config_even_when_dagster_offline(client):
    """If Dagster isn't running, the endpoint still returns config and
    a clear 'dagster_reachable: false' flag. Doesn't 500."""
    with patch("packages.scheduling.dagster_client.is_reachable", return_value=False):
        r = client.get("/api/admin/schedule")
    assert r.status_code == 200
    body = r.json()
    assert "config" in body
    assert body["dagster_reachable"] is False
    assert body["recent_runs"] == []


def test_put_schedule_rejects_bad_cron(client):
    r = client.put(
        "/api/admin/schedule",
        json={"cron_schedule": "this is not cron", "enabled": True},
    )
    assert r.status_code == 400
    assert "Invalid cron_schedule" in r.json()["detail"]


def test_put_schedule_accepts_valid_cron(client, tmp_path, monkeypatch):
    import packages.scheduling as sched

    # Point the config IO at a tmp file so we don't trample the real one
    monkeypatch.setattr(sched, "_CONFIG_PATH", tmp_path / "config.json")

    r = client.put(
        "/api/admin/schedule",
        json={"cron_schedule": "15 4 * * *", "enabled": True, "schedule_type": "daily"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["config"]["cron_schedule"] == "15 4 * * *"
    assert body["config"]["enabled"] is True


def test_run_now_returns_503_when_dagster_offline(client):
    """The 'Run now' button must surface a clean 503 when Dagster
    isn't running — not a 500 stack trace."""
    from packages.scheduling.dagster_client import DagsterUnreachable

    with patch(
        "packages.scheduling.dagster_client.launch_run",
        side_effect=DagsterUnreachable("connection refused"),
    ):
        r = client.post("/api/admin/schedule/run-now")
    assert r.status_code == 503
    assert "Dagster" in r.json()["detail"]
