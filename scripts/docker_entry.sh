#!/usr/bin/env bash
# RegulAI container entrypoint — prepare state, then exec the service command.
#
# Parameters (env):
#   REGULAI_DB         duckdb | snowflake | databricks   (warehouse backend)
#   REGULAI_BOOTSTRAP  auto | force | skip               (default: auto)
#       auto  — seed the KG only if empty; seed the DuckDB warehouse only if
#               the file is missing. Cloud backends are never auto-seeded.
#       force — re-run the warehouse seed chain even if state exists (KG is
#               rebuilt only when empty; use `make rebuild-kg` for a KG wipe).
#       skip  — start the service with no checks (used by the dagster service,
#               which shares the api's state and must not race its bootstrap).
#
# Special command: `bootstrap-only` runs the bootstrap and exits — used by
# `make docker-seed` to (re)seed without starting a second API process
# (DuckDB is single-writer; the seed must not race a running api container).
set -euo pipefail

DB="${REGULAI_DB:-duckdb}"
BOOTSTRAP="${REGULAI_BOOTSTRAP:-auto}"
echo "[entry] REGULAI_DB=${DB} · REGULAI_BOOTSTRAP=${BOOTSTRAP}"

wait_for_neo4j() {
  echo "[entry] waiting for Neo4j at ${NEO4J_URI:-bolt://neo4j:7687} …"
  python - <<'PY'
import os, sys, time
from neo4j import GraphDatabase
uri = os.environ.get("NEO4J_URI", "bolt://neo4j:7687")
auth = (os.environ.get("NEO4J_USER", "neo4j"), os.environ.get("NEO4J_PASSWORD", ""))
for _ in range(60):
    try:
        with GraphDatabase.driver(uri, auth=auth) as d:
            d.verify_connectivity()
        sys.exit(0)
    except Exception:
        time.sleep(2)
print("[entry] Neo4j unreachable after 120s", file=sys.stderr)
sys.exit(1)
PY
}

kg_is_empty() {
  python - <<'PY'
import sys
from packages.adapters.lhs.gre.neo4j_adapter import Neo4jGREAdapter
with Neo4jGREAdapter() as gre:
    sys.exit(0 if gre.count_nodes() == 0 else 1)
PY
}

bootstrap_kg() {
  echo "[entry] KG is empty — bootstrapping (replays cached extractions; no LLM calls) …"
  python -m scripts.rebuild_kg
  # rebuild_kg does not cover these (all idempotent MERGEs):
  python -m scripts.seed_jurisdictions
  python -m scripts.seed_filing_obligations
  python -m scripts.migrate_fl_validation_rules
  echo "[entry] KG bootstrap done."
}

bootstrap_duckdb() {
  echo "[entry] seeding DuckDB warehouse (${REGULAI_DUCKDB_PATH:-materialized/regulai.duckdb}) …"
  python -m scripts.seed_duckdb
  python -m scripts.seed_databricks_medallion   # duckdb mode: plain CREATE TABLEs
  python -m scripts.seed_fl_fhcf
  python -m scripts.run_silver
  python -m scripts.run_gold
  echo "[entry] DuckDB warehouse ready."
}

if [ "${BOOTSTRAP}" != "skip" ]; then
  wait_for_neo4j
  if kg_is_empty; then
    bootstrap_kg
  else
    echo "[entry] KG already populated — skipping KG bootstrap."
  fi

  if [ "${DB}" = "duckdb" ]; then
    DUCK_FILE="${REGULAI_DUCKDB_PATH:-materialized/regulai.duckdb}"
    if [ "${BOOTSTRAP}" = "force" ] || [ ! -f "${DUCK_FILE}" ]; then
      bootstrap_duckdb
    else
      echo "[entry] DuckDB file exists — skipping warehouse seed (REGULAI_BOOTSTRAP=force to reseed)."
    fi
  else
    echo "[entry] ${DB} backend — warehouse assumed provisioned; not auto-seeding a cloud warehouse."
  fi
fi

if [ "${1:-}" = "bootstrap-only" ]; then
  echo "[entry] bootstrap-only: done."
  exit 0
fi

exec "$@"
