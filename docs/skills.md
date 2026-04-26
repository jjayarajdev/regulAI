# Operational know-how — RegulAI LHS

Accumulated learnings, conventions, and gotchas from building RegulAI. Updated as we discover things worth remembering for future work. NOT a tutorial — assumes context from `docs/poc-decisions.md` and `docs/lhs-build-plan.md`.

---

## OpenAI

### Available models (verified 2026-04-25 against user's account)

134 models accessible. Sentinel-relevant candidates:

| Model | Released | Use for |
|---|---|---|
| `gpt-5.5` | 2026-04-23 | **Sentinel — current default**. Latest, best for structured extraction over regulatory text. |
| `gpt-5.5-pro` | 2026-04-23 | Reach for if 5.5 falls short on a specific extraction. More expensive. |
| `gpt-5.4` | 2026-03-05 | Stable fallback if 5.5 has rough edges. |
| `gpt-5.1` | 2025-11-13 | Cost/quality tradeoff. |
| `gpt-5` | original | Most conservative GPT-5 baseline. |
| `gpt-5-mini`, `gpt-5-nano` | | Test iteration to save cost. Use during dev loops. |

Switching models is one config line: `OPENAI_MODEL=...` in `.env`. `make` targets pick it up automatically.

Verify with: `uv run python -m scripts.verify_openai`

### Structured Outputs

OpenAI's strict-JSON-schema mode (`response_format={"type": "json_schema", "json_schema": {"strict": true, ...}}`) constraints worth remembering:

- All fields **must be required** in strict mode. Model optionality via `anyOf: [type, "null"]`.
- `additionalProperties: false` required at every object level.
- `oneOf` not supported — use `anyOf`.
- Max 100 total properties across the whole schema.
- Max 5 levels of nesting.
- Recursive types limited.

Pydantic → JSON Schema: use `Model.model_json_schema()` then post-process to satisfy the strict-mode rules (set `additionalProperties: false`, mark all fields required, replace `Optional[T]` with `anyOf [T, null]`).

Or use the `openai` SDK's `client.chat.completions.parse(response_format=PydanticModel)` helper — it handles the conversion automatically.

### Prompt caching

OpenAI auto-caches prompt prefixes ≥1024 tokens that are reused. For Sentinel, cache the schema description + closed-vocabulary system prompt as a stable prefix; rotate only the regulation text per call.

---

## Neo4j

### Connection

- Local Docker: `bolt://localhost:7687`, user `neo4j`, password from `.env` (`NEO4J_PASSWORD`).
- Browser: http://localhost:7474.
- Docker container name: `regulai-neo4j`. Volumes named `regulai-neo4j-data` and `regulai-neo4j-logs` — survive `docker compose down`, killed only by `docker compose down -v`.

### Idiomatic Cypher patterns we're using

- **Multi-label nodes**: every KG node carries `:GRENode` plus its specific type label (e.g., `:RegulationDocument`). Lets us query the whole graph (`MATCH (n:GRENode)`) or a single type (`MATCH (n:RegulationDocument)`).
- **Labels and relationship types CANNOT be parameterized** in Cypher. We inject them via Python f-strings — safe because they come from closed `NodeType` / `RelationshipType` enums, never user input.
- **Append-only versioning**: change = new node version + `SUPERSEDES` relationship from new → old.
- **Effective windows**: `effective_from` / `effective_to` properties on every node. Temporal queries filter by `as_of` date; null `effective_to` means "still active."
- **UUIDs as strings**: Neo4j has no native UUID; we store IDs as strings. Pydantic UUID fields accept strings on parse.
- **Dates as ISO strings**: simpler than mapping to `neo4j.time.Date` — Pydantic accepts ISO strings cleanly on read.

### Useful Browser queries

```cypher
// Whole canon
MATCH (n) RETURN n LIMIT 100

// Citation chain — Cause of Loss values back to the rule that defines them
MATCH (cv:CodeValue)-[:CITES]->(rule:Rule) RETURN cv, rule

// Rules and their parent regulation document
MATCH (d:RegulationDocument)<-[:CONTAINED_IN]-(r:Rule) RETURN d, r

// Bulletin overrides
MATCH path = (bo:BulletinOverride)-[:OVERRIDES]->(:Rule) RETURN path

// Counts by type (shows the regulatory canon's shape)
MATCH (n:GRENode) RETURN n.type AS type, count(n) AS n ORDER BY n DESC
```

---

## Pydantic v2

### Patterns we use

- **Closed vocabulary via `Literal`**: each node class has `type: Literal["RegulationDocument"] = "RegulationDocument"`. Forces correct type for every instance, gives static type-checkers something to discriminate on.
- **`model_dump(mode="json")`**: serializes to JSON-safe dict (UUIDs → strings, dates → ISO, enums → values). Always use `mode="json"` when going to Neo4j or to OpenAI.
- **Round-trip via `model_validate(props)`**: Pydantic permissively converts string IDs/dates back to typed fields on parse.
- **Settings**: `BaseSettings` from `pydantic-settings` with `env_file=".env"`. `extra="ignore"` keeps unknown env vars from blowing up.

---

## Project conventions

- **No buried constants**: every tunable lives in `packages/config/settings.py`. Override via `.env` or environment.
- **Cypher centralized**: all Cypher queries in `packages/lhs/kg/queries.py` — never embedded in adapter methods inline. Makes review and testing easier.
- **Adapters as context managers**: `with Neo4jGREAdapter() as gre: ...`. Driver close on exit.
- **Tests can hit the real Neo4j**: integration tests use a fixture that wipes the DB. Don't run against real data.
- **Seed is destructive**: `make seed` wipes everything. POC trade.

---

## Things we deliberately don't do (yet)

- No connection pooling beyond what the neo4j driver does internally.
- No transactions across multiple writes — each `create_node` / `create_relationship` is its own session. Good enough for POC scale.
- No retry/backoff on OpenAI calls — assumes happy path. Add when we hit rate limits.
- No PII handling. Synthetic data only.
- No auth on the FastAPI (added in LHS-4).
