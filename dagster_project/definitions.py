"""Top-level Dagster Definitions — the entry point Dagster loads.

`dagster dev -m dagster_project` will find this `defs` object (re-exported
from dagster_project/__init__.py) and wire everything up. Adding a new
job/schedule/sensor means importing it and appending to the right list.
"""

from dagster import Definitions

from dagster_project.jobs import ALL_JOBS
from dagster_project.schedules import full_pipeline_schedule

defs = Definitions(
    jobs=ALL_JOBS,
    schedules=[full_pipeline_schedule],
    # Phase 2: add resources (Snowflake/Neo4j as Dagster resources)
    # and sensors (e.g. "new cached extraction lands → re-run materialize").
)
