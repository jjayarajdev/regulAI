# Fly.io Deployment

Two flavors documented here. Pick **A** for the fastest demo URL;
pick **B** when you want the full stack on Fly.

## Flavor A — minimum demo (~15 min after account verification)

Single Fly app for the FastAPI. Neo4j and Dagster hosted elsewhere.

| Component | Where | Cost |
|---|---|---|
| `regulai` (FastAPI) | Fly.io single app | ~$5–10/mo |
| Neo4j | [Neo4j Aura free tier](https://neo4j.com/cloud/platform/aura-graph-database/) | $0 |
| Dagster | not deployed | $0 |
| Snowflake | existing account | unchanged |
| **Total** | | **~$5–10/mo** |

What works in Flavor A:
- All five demo URLs respond (the admin/schedule page degrades
  gracefully when DAGSTER_URL points at a missing app — it shows
  "Dagster offline" and the rest of the page works)
- Kanban (/workstation) shows violations from Snowflake
- KG canon browser (/explore) reads from Neo4j Aura
- Excel upload (/admin/upload) accepts files + validates schema +
  writes Parquet. **The "Process" button won't fire** without Dagster
  but the upload itself works for the demo narrative

What doesn't:
- Click-to-run pipeline from /admin/upload Process button
- Cron-style scheduled pipeline runs

### Steps

```bash
# 1. Account verification (one-time, if not already done)
# Visit https://fly.io/high-risk-unlock if you hit the verification gate.

# 2. Install CLI
brew install flyctl
fly auth login

# 3. Provision a Neo4j Aura free instance
# Visit https://console.neo4j.io → create a free DB
# Copy the connection URI + generated password — you'll need them below

# 4. Create the Fly app
fly apps create regulai

# 5. Set secrets
fly secrets set \
  OPENAI_API_KEY=sk-... \
  SNOWFLAKE_ACCOUNT=<account-id> \
  SNOWFLAKE_USER=<username> \
  SNOWFLAKE_TOKEN=<PAT> \
  SNOWFLAKE_AUTHENTICATOR=PROGRAMMATIC_ACCESS_TOKEN \
  SNOWFLAKE_ROLE=<role> \
  SNOWFLAKE_WAREHOUSE=COMPUTE_WH \
  SNOWFLAKE_DATABASE=INSURANCE_REGULATORY \
  NEO4J_URI=neo4j+s://<aura-id>.databases.neo4j.io \
  NEO4J_USER=neo4j \
  NEO4J_PASSWORD=<aura-password>

# 6. Deploy
fly deploy

# 7. Seed the KG inside the running machine (~60s)
fly ssh console -C "make rebuild-kg migrate-validation-rules seed-jurisdictions tag-federal-defaults seed-filing-obligations seed-florida migrate-fl-validation-rules"

# 8. Seed demo violations (so Kanban populates)
fly ssh console -C "make seed-demo-violations"

# 9. Open it
fly open    # https://regulai.fly.dev/workstation
```

## Flavor B — full stack on Fly (~45 min after verification)

Three Fly apps + persistent volumes. Cost: ~$25–35/mo.

```bash
# Apps
fly apps create regulai
fly apps create regulai-dagster
fly apps create regulai-neo4j  # OPTIONAL — Aura is simpler

# Volumes (region must match each fly.toml's primary_region)
fly volumes create dagster_home --region bom --size 1 --app regulai-dagster
fly volumes create neo4j_data   --region bom --size 3 --app regulai-neo4j

# Secrets — set on each app independently. Use a strong NEO4J_PASSWORD
# shared across all three apps. The values for SNOWFLAKE_* are the same.
fly secrets set --app regulai-neo4j NEO4J_AUTH=neo4j/<strong-password>
fly secrets set --app regulai-dagster \
  NEO4J_URI=bolt://regulai-neo4j.internal:7687 \
  NEO4J_USER=neo4j \
  NEO4J_PASSWORD=<strong-password> \
  OPENAI_API_KEY=... SNOWFLAKE_*=...
fly secrets set --app regulai \
  NEO4J_URI=bolt://regulai-neo4j.internal:7687 \
  NEO4J_USER=neo4j \
  NEO4J_PASSWORD=<strong-password> \
  DAGSTER_URL=http://regulai-dagster.internal:3000 \
  OPENAI_API_KEY=... SNOWFLAKE_*=...

# Deploy in order — Neo4j first, then dagster, then api
fly deploy --config fly.neo4j.toml --app regulai-neo4j
fly deploy --config fly.dagster.toml --app regulai-dagster
fly deploy   # uses fly.toml, --app inferred from the file

# Seed
fly ssh console --app regulai -C "make rebuild-kg ... seed-florida ... seed-demo-violations"

# Open
fly open --app regulai             # https://regulai.fly.dev/workstation
fly open --app regulai-dagster     # https://regulai-dagster.fly.dev
```

## Common ops

| Action | Command |
|---|---|
| Deploy an update | `fly deploy` |
| Tail logs | `fly logs` (add `--app` for non-default app) |
| SSH into the machine | `fly ssh console` |
| Scale memory | `fly scale memory 2048` |
| Add region | `fly regions add iad` |
| Open browser | `fly open` |
| List secrets (names only) | `fly secrets list` |
| Suspend (no charges) | `fly scale count 0` |
| Resume | `fly scale count 1` |

## Troubleshooting

**"Your account has been marked as high risk"**
- Visit https://fly.io/high-risk-unlock, complete verification (usually
  a card challenge + sometimes a short form about your use case).
- Common for new accounts; typically resolved in minutes to a few hours.

**`/api/rhs/validate` returns 500**
- `fly secrets list` to confirm SNOWFLAKE_* are set
- `fly logs` to see the actual error

**Kanban empty after seed-demo-violations**
- Snowflake Bronze tables not loaded. Run inside the machine:
  `fly ssh console -C "make load-bronze"` then re-seed.

**/admin/schedule shows "Dagster offline"**
- Flavor A: expected (no Dagster). Demo continues; UI degrades gracefully.
- Flavor B: check `fly status --app regulai-dagster` and the
  DAGSTER_URL secret on the api app.

**Cold-start latency on first request**
- `auto_stop_machines = "stop"` is on by default. Either accept the
  ~5–10s wake-up OR set `min_machines_running = 1` in fly.toml to
  keep one machine warm 24/7 (adds ~$5/mo).

## Production-readiness gaps still apply

Same list as the AWS doc — no auth on /admin/*, PII in clear text,
single point of failure per app, no automated backups. For a 30-min
demo: fine. For anything else: see docs/enterprise-readiness.md.
