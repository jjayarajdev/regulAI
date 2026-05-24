"""Editable schedule backed by runtime_config.json.

The trick: Dagster's `@schedule` decorator takes a cron string at
definition time, but Dagster also re-evaluates the schedule's
`should_execute` function on every tick (~30s). We use that hook to:

  1. Re-read packages.scheduling config on every tick
  2. Return False if `enabled` is False — schedule is a no-op
  3. Return True only if the current minute matches the configured
     cron in the config file

We use a 1-minute base cron (`* * * * *`) so Dagster ticks every
minute, then `should_execute` checks the *user-configured* cron against
the current time. This means the admin can change the cron in the
config file (via UI) and the new schedule takes effect on the next
minute boundary — no Dagster restart.

Why not use Dagster's built-in cron + a separate "enabled" toggle?
Because changing the cron string itself requires re-registering the
schedule, and the user wants to set arbitrary times from the UI.
The 1-minute-tick pattern is the cleanest way to make schedules
runtime-editable without a daemon restart.
"""

import datetime as dt

from croniter import croniter
from dagster import RunRequest, ScheduleEvaluationContext, SkipReason, schedule

from dagster_project.jobs import full_pipeline_job
from packages.scheduling import load as load_schedule_config


@schedule(
    job=full_pipeline_job,
    cron_schedule="* * * * *",  # Tick every minute; the gate is in should_execute below.
    name="full_pipeline_schedule",
    description=(
        "Editable schedule for the full pipeline. The cron is read from "
        "dagster_project/runtime_config.json on every tick, so the admin "
        "UI's schedule changes take effect on the next minute boundary."
    ),
)
def full_pipeline_schedule(context: ScheduleEvaluationContext):
    cfg = load_schedule_config()

    if not cfg.enabled:
        return SkipReason(f"Schedule is disabled in runtime_config.json (cron={cfg.cron_schedule!r}).")

    # Check whether the current minute matches the user's configured cron.
    # croniter.get_prev gives the most recent fire-time at-or-before now;
    # if that equals the current minute, this is a real fire tick.
    now = context.scheduled_execution_time.replace(second=0, microsecond=0)
    try:
        it = croniter(cfg.cron_schedule, now + dt.timedelta(seconds=1))
        prev_fire = it.get_prev(dt.datetime)
    except (ValueError, KeyError) as e:
        return SkipReason(f"Invalid cron_schedule in runtime_config.json: {cfg.cron_schedule!r} ({e}).")

    if prev_fire.replace(tzinfo=now.tzinfo) != now:
        # The configured cron didn't fire this minute. Skip silently —
        # Dagster will tick again next minute.
        return SkipReason(
            f"Current minute {now.isoformat()} doesn't match cron {cfg.cron_schedule!r} "
            f"(most recent fire was {prev_fire.isoformat()})."
        )

    return RunRequest(
        run_key=f"scheduled-{now.isoformat()}",
        tags={
            "schedule.cron": cfg.cron_schedule,
            "schedule.pipeline": cfg.pipeline,
            "schedule.triggered_by": "runtime_config",
        },
    )
