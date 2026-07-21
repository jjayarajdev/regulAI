#!/usr/bin/env bash
# Run RegulAI's Docker build locally, on a distinct port block so it never
# clashes with other local projects (AI gateway, CLM, …). Ports + Databricks
# env are defined in docker-compose.local.yml; creds come from .env.
#
#   ./run-docker.sh                     # api only (experience, Databricks) → :8899
#   ./run-docker.sh api neo4j           # + Knowledge Graph (regulation approve)
#   ./run-docker.sh api neo4j dagster   # full stack
#   REGULAI_API_PORT=9100 ./run-docker.sh   # different host port
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; cd "$ROOT"

API_PORT="${REGULAI_API_PORT:-8899}"
FILES=(-f docker-compose.yml -f docker-compose.local.yml)
[ $# -eq 0 ] && set -- api          # default service

echo "▶ RegulAI (Docker) — building + starting: $*"
docker compose "${FILES[@]}" up --build -d "$@"

echo
echo "  app   → http://localhost:${API_PORT}/app/          (React experience)"
echo "  api   → http://localhost:${API_PORT}/api/rhs/filings"
echo "  logs  → docker compose ${FILES[*]} logs -f $*"
echo "  stop  → docker compose ${FILES[*]} down"
