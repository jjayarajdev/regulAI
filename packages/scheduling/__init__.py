"""Shared schedule-config schema + IO.

Used by both:
  - dagster_project/schedules.py — reads config to decide cron + enabled
  - api/main.py /admin/schedule routes — reads/writes via the admin UI

Single source of truth for the JSON shape so the two sides can't drift.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# Path resolved from repo root, not CWD, so it works whether you run via
# `make dagster` from repo root or via `dagster dev -m dagster_project`
# from anywhere.
_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "dagster_project" / "runtime_config.json"

PipelineKind = Literal["full"]  # Phase 1 — extend as we add jobs in dagster_project/jobs/
ScheduleKind = Literal["daily", "weekly", "manual"]


class ScheduleConfig(BaseModel):
    """The editable bits of the pipeline schedule.

    Cron expression is canonical — schedule_type is a UI-friendly view of
    it ("daily" = `0 H * * *`, "weekly" = `0 H * * D`, "manual" = enabled=False).
    The admin UI lets users pick by schedule_type + time, but a power user
    can edit the raw cron in runtime_config.json if needed.
    """

    model_config = ConfigDict(extra="forbid")

    schedule_type: ScheduleKind = "daily"
    cron_schedule: str = Field(
        default="0 2 * * *",
        description="Standard 5-field cron expression in UTC. Read by Dagster's ScheduleDefinition.",
    )
    enabled: bool = False
    pipeline: PipelineKind = "full"
    updated_at: dt.datetime | None = None
    updated_by: str | None = None


def load() -> ScheduleConfig:
    """Read the current schedule config from disk.

    Returns sensible defaults if the file is missing or malformed — the
    Dagster schedule never crashes on bad config; it just stays disabled.
    """
    try:
        raw = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return ScheduleConfig()
    except json.JSONDecodeError:
        return ScheduleConfig()
    # Drop the underscore-prefixed _description field if present (it's docs only).
    cleaned = {k: v for k, v in raw.items() if not k.startswith("_")}
    try:
        return ScheduleConfig.model_validate(cleaned)
    except Exception:
        return ScheduleConfig()


def save(config: ScheduleConfig) -> None:
    """Atomic write — write to a sibling .tmp file then rename. Prevents
    Dagster from reading a half-written file at a schedule evaluation tick."""
    config.updated_at = dt.datetime.now(dt.UTC)
    out = config.model_dump(mode="json")
    # Preserve the documentation field
    out = {"_description": "Editable scheduler config. See packages/scheduling/__init__.py.", **out}
    tmp = _CONFIG_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    tmp.replace(_CONFIG_PATH)


def config_path() -> Path:
    """Where the config lives on disk. Exposed for the admin route's
    'last modified at' display and for tests."""
    return _CONFIG_PATH
