# AWS Deployment — single EC2 + Docker Compose + Caddy

Pragmatic deployment path for a client demo. **Not production**. The
production-readiness gaps from `docs/enterprise-readiness.md` (auth,
PII handling, secrets management, HA, observability) all still apply.
This gets a demo URL with HTTPS that clients can click.

## What lands

```
[browser] ─https─► [Caddy on EC2 :443] ─┬─► api:8765      (FastAPI + admin UIs)
                                        ├─► dagster:3000  (under /dagster)
                                        └─► neo4j:7687    (internal only)
```

Public URLs after deploy:

| URL | Purpose |
|---|---|
| `https://<your-domain>/` | Landing page |
| `https://<your-domain>/workstation` | Kanban with violation tickets |
| `https://<your-domain>/admin/upload` | Excel upload demo |
| `https://<your-domain>/admin/schedule` | Dagster schedule editor |
| `https://<your-domain>/dagster/` | Dagster web UI (data-team view) |

## Cost (us-east-1, on-demand)

| Item | Monthly |
|---|---|
| EC2 t3.medium (2 vCPU, 4 GB) | ~$30 |
| EBS gp3 30 GB | ~$3 |
| Elastic IP (attached, while running) | $0 |
| Data egress (demo volumes) | <$5 |
| Route 53 hosted zone (optional, for a real domain) | $0.50 |
| **Total** | **~$35–40/mo** |

Cheaper with reserved instance (~$12/mo for the EC2 alone). For a
one-off demo: stop the instance when not using it (~$3 EBS-only).

## One-time setup (~30 min)

### 1. Launch the EC2

- **AMI**: Amazon Linux 2023 (free, ships with `dnf`)
- **Instance type**: `t3.medium`
- **Storage**: 30 GB gp3
- **Key pair**: pick or create one; you'll SSH in
- **Network**: default VPC is fine

### 2. Security group

Inbound rules:

| Port | Protocol | Source | Purpose |
|---|---|---|---|
| 22 | TCP | **your IP** (`x.x.x.x/32`) | SSH |
| 80 | TCP | `0.0.0.0/0` | Caddy ACME challenge + HTTP→HTTPS redirect |
| 443 | TCP | `0.0.0.0/0` | HTTPS |

Don't open 3000, 7474, 7687, 8765 — those are internal to the compose network.

### 3. (Optional) Elastic IP + DNS

Without an Elastic IP, the public DNS changes every time the instance
restarts. For a stable demo URL, attach one.

If using a real domain (recommended for HTTPS that doesn't trigger
browser warnings):

1. In Route 53 (or your registrar): create an A record pointing
   `demo.<your-domain>` at the Elastic IP
2. Wait for DNS to propagate (~1–10 min)
3. Set `REGULAI_DOMAIN=demo.<your-domain>` in `.env` (see step 6)

If you want to skip the domain dance:

- Use the EC2 public DNS (e.g. `ec2-3-123-45-67.compute-1.amazonaws.com`)
- Caddy will get a Let's Encrypt cert for that hostname
- Set `REGULAI_DOMAIN=ec2-3-123-45-67.compute-1.amazonaws.com` in `.env`

### 4. SSH in + install Docker

```bash
ssh -i ~/.ssh/<your-key>.pem ec2-user@<elastic-ip>

# Install Docker + Compose plugin
sudo dnf install -y docker git
sudo systemctl enable --now docker
sudo usermod -aG docker ec2-user
# Logout + back in so the group takes effect, or:
newgrp docker

# Docker Compose v2 (plugin form)
DOCKER_CONFIG=${DOCKER_CONFIG:-$HOME/.docker}
mkdir -p $DOCKER_CONFIG/cli-plugins
curl -sSL https://github.com/docker/compose/releases/latest/download/docker-compose-linux-$(uname -m) \
  -o $DOCKER_CONFIG/cli-plugins/docker-compose
chmod +x $DOCKER_CONFIG/cli-plugins/docker-compose
docker compose version  # should print v2.x.x
```

### 5. Clone the repo

```bash
git clone https://github.com/jjayarajdev/regulAI.git
cd regulAI
git checkout release  # always deploy from the release branch
```

### 6. Populate `.env`

```bash
cp .env.example .env
nano .env  # or vim, your call
```

Required:

```
# OpenAI key for Sentinel
OPENAI_API_KEY=sk-...

# Snowflake — PAT auth (recommended for this account)
SNOWFLAKE_ACCOUNT=xxx-xxx
SNOWFLAKE_USER=...
SNOWFLAKE_TOKEN=...
SNOWFLAKE_AUTHENTICATOR=PROGRAMMATIC_ACCESS_TOKEN
SNOWFLAKE_ROLE=...
SNOWFLAKE_WAREHOUSE=COMPUTE_WH
SNOWFLAKE_DATABASE=INSURANCE_REGULATORY

# Caddy / domain
REGULAI_DOMAIN=demo.<your-domain>
REGULAI_ACME_EMAIL=ops@<your-domain>
```

### 7. Bring it up

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

First boot takes ~3 minutes (image pull + Neo4j initial config + Caddy
cert acquisition). Watch progress:

```bash
docker compose logs -f
```

Wait for:
- `regulai-neo4j` → healthy
- `regulai-api` → healthy
- `regulai-dagster` → healthy
- `regulai-caddy` → starting → "certificate obtained successfully"

### 8. Seed the KG (one-time, ~60s)

```bash
docker compose exec api make \
  rebuild-kg \
  migrate-validation-rules \
  seed-jurisdictions \
  tag-federal-defaults \
  seed-filing-obligations \
  seed-florida \
  migrate-fl-validation-rules
```

Verify:

```bash
curl -s https://demo.<your-domain>/api/kg/stats | head
```

Should return ~1,695 nodes / 3,891 relationships.

### 9. Seed demo violations (so Kanban populates)

```bash
docker compose exec api make seed-demo-violations
```

### 10. Test the URLs

Open in browser:

- `https://demo.<your-domain>/` → landing
- `https://demo.<your-domain>/workstation` → 15 violations on TPA
- `https://demo.<your-domain>/admin/upload` → upload demo
- `https://demo.<your-domain>/admin/schedule` → Dagster schedule
- `https://demo.<your-domain>/dagster/` → Dagster UI

If any 502s: `docker compose logs caddy api dagster`.

## Day-2 operations

### Deploy an update

```bash
ssh ec2-user@<elastic-ip>
cd regulAI
git pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

### Restart a single service

```bash
docker compose restart api
```

### Backup the KG

```bash
docker compose exec neo4j /var/lib/neo4j/bin/neo4j-admin database dump neo4j --to-path=/data
docker cp regulai-neo4j:/data/neo4j.dump ./neo4j-$(date +%Y%m%d).dump
```

The cached extractions in the repo (`materialized/extractions/`)
guarantee the KG is rebuildable from disk — so a backup is for
*manual edits*, not for the canonical canon.

### Stop everything (e.g. demo over, save EBS cost)

```bash
docker compose down  # keep volumes
# or
docker compose down -v  # nuke volumes (KG + Dagster history gone — rebuild via step 8)
```

### Pause the EC2 (no compute charges, EBS only)

AWS console → Instances → Stop. Restart when needed. Public DNS is
preserved if you have an Elastic IP attached.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| 502 Bad Gateway on all routes | api or dagster container down | `docker compose ps`, then `docker compose logs <service>` |
| `/api/rhs/validate` returns 500 | Missing Snowflake env vars | `docker compose exec api env \| grep SNOWFLAKE` — should show all SNOWFLAKE_* set |
| Cert not issued | DNS not propagating, or REGULAI_DOMAIN wrong | `dig demo.<your-domain>` → must resolve to your EIP. Check `docker logs regulai-caddy` for ACME errors |
| Kanban empty after seed-demo-violations | Snowflake tables not loaded | `docker compose exec api make load-bronze` then re-seed |
| Dagster UI shows blank page | Path-prefix mismatch | `https://...../dagster/` (trailing slash required), check `--path-prefix=/dagster` in compose.prod |

## Alternative: Fly.io (~same cost, less AWS-specific)

If the demo doesn't need to be "on AWS" specifically:

```bash
fly launch  # interactive — point at Dockerfile
fly secrets set OPENAI_API_KEY=... SNOWFLAKE_ACCOUNT=... ...
fly deploy
```

Fly gives you HTTPS + a domain (`<app-name>.fly.dev`) automatically. No
Caddy needed. Persistent volumes for Neo4j data work similarly. Cost
is comparable (~$30/mo for the same-sized VM). Pick AWS if a security
review / corporate compliance requires it; pick Fly.io if you want the
simplest path.

## What's NOT in this deployment

These remain open from the production-readiness assessment. None of
them are blockers for a controlled demo, but **none of them are
acceptable for a real customer engagement either**:

1. **No authn/authz** — anyone with the URL can hit `/admin/*` and
   trigger pipelines, modify the schedule, upload Excels.
2. **No PII protection** — policy numbers and addresses flow through
   in clear text including in logs.
3. **Secrets in `.env` on the EC2 box** — not Secrets Manager.
4. **Single EBS volume** — KG data lives on the same disk as everything;
   no snapshotted backup schedule.
5. **No autoscaling / HA** — EC2 dies, demo dies. KG rebuildable
   from cached extractions; Snowflake data is durable.
6. **No CI/CD** — deploys are `git pull && docker compose up -d`.
7. **No structured logging or metrics** — `docker logs` is the
   monitoring story.

For a 30-minute demo with one prospect, all acceptable. For anything
else, work the production-readiness list before opening this URL.
