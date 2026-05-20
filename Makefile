.PHONY: help install up down logs migrate smoke seed test clean

help:
	@echo "RegulAI LHS dev commands:"
	@echo "  make install   - install Python deps via uv"
	@echo "  make up        - start Neo4j (docker compose, wait until ready)"
	@echo "  make down      - stop Neo4j"
	@echo "  make logs      - tail Neo4j logs"
	@echo "  make migrate   - run Cypher schema migrations (constraints + indexes)"
	@echo "  make smoke     - run LHS-1 smoke test (write + read a node)"
	@echo "  make seed      - DESTRUCTIVE: wipe DB and load regulatory canon"
	@echo "  make extract-pdfs        - extract PDFs in references/regulations to text files"
	@echo "  make extract-bulletin    - run Sentinel on the synthetic change bulletin"
	@echo "  make extract-hb2067      - run Sentinel on HB 2067 statute text"
	@echo "  make extract DOC=path    - run Sentinel on an arbitrary document"
	@echo "  make split-sections      - split TICO stat plan into per-section files"
	@echo "  make batch-extract       - run Sentinel on every doc (idempotent — skips cached)"
	@echo "  make ui                  - start FastAPI side-by-side UI on localhost:8000"
	@echo "  make test      - run pytest (model + adapter integration tests)"
	@echo "  make clean     - tear down Neo4j (preserves named volumes)"

install:
	uv sync --extra dev

up:
	docker compose up -d neo4j
	@echo "Waiting for Neo4j..."
	@until curl -sf http://localhost:7474 > /dev/null 2>&1; do sleep 2; done
	@echo "Neo4j ready at http://localhost:7474 (user: neo4j)"

down:
	docker compose stop neo4j

logs:
	docker compose logs -f neo4j

migrate:
	uv run python -m scripts.migrate

smoke:
	uv run python -m scripts.smoke

seed:
	uv run python -m scripts.seed

extract-pdfs:
	uv run python -m scripts.extract_pdfs

split-sections:
	uv run python -m scripts.split_sections

batch-extract:
	uv run python -m scripts.batch_extract

batch-extract-force:
	uv run python -m scripts.batch_extract --force

compute-rects:
	uv run python -m scripts.compute_rects

compute-rects-force:
	uv run python -m scripts.compute_rects --force

parse-wire-layout:
	uv run python -m scripts.parse_record_layout

rebuild-kg:
	uv run python -m scripts.rebuild_kg

validate-kg:
	uv run python -m scripts.validate_kg_coverage

kg-hygiene:
	uv run python -m scripts.kg_hygiene

seed-jurisdictions:
	uv run python -m scripts.seed_jurisdictions

tag-federal-defaults:
	uv run python -m scripts.tag_federal_defaults

seed-filing-obligations:
	uv run python -m scripts.seed_filing_obligations

p2-regression-gate:
	uv run python -m scripts.p2_regression_gate

# ── Phase 3: Florida intake ──
extract-fl-627-062:
	uv run python -m scripts.extract synthetic_regulations/real/florida/FL_627_062_rate_standards.txt

materialize-fl:
	@if [ -z "$(EXT)" ]; then echo "Usage: make materialize-fl EXT=<extraction.json>"; exit 1; fi
	uv run python -m scripts.materialize_florida_extraction $(EXT)

seed-florida:
	uv run python -m scripts.seed_florida

cleanup-kg:
	uv run python -m scripts.cleanup_kg

demo-bulletin:
	uv run python -m scripts.demo_bulletin

demo-new-bulletin:
	@if [ -n "$(AUTO)" ]; then \
	    uv run python -m scripts.demo_new_bulletin --auto; \
	else \
	    uv run python -m scripts.demo_new_bulletin; \
	fi

cypher-favorites:
	uv run python -m scripts.build_cypher_favorites > cypher/saved-cypher.json
	uv run python -m scripts.build_cypher_favorites --csv > cypher/saved-cypher.csv
	@echo "Wrote cypher/saved-cypher.json (older Browser builds)"
	@echo "Wrote cypher/saved-cypher.csv  (newer Browser 5.x — try this if JSON import fails)"
	@echo ""
	@echo "Import in Neo4j Browser: ☰ → Favorites → ⋮ → Import favorites"
	@echo "  Pick whichever file your Browser accepts."

cypher-guide:
	uv run python -m scripts.build_cypher_guide
	@echo ""
	@echo "Then in Neo4j Browser at http://localhost:7474, run:"
	@echo "    :play http://localhost:8765/cypher-guide"

apply-bulletin:
	@if [ -z "$(BULLETIN)" ] && [ -z "$(ALL)" ]; then \
	    echo "Usage: make apply-bulletin BULLETIN=\"<name>\"  OR  make apply-bulletin ALL=1"; exit 1; \
	fi
	@if [ -n "$(ALL)" ]; then \
	    uv run python -m scripts.apply_bulletin --all; \
	else \
	    uv run python -m scripts.apply_bulletin --bulletin "$(BULLETIN)"; \
	fi

generate-sample:
	uv run python -m scripts.generate_sample_submission

validate-sample:
	uv run python -m scripts.validate_submission --layout "Premium Record Layout"

extract:
	@if [ -z "$(DOC)" ]; then echo "Usage: make extract DOC=path/to/document.txt"; exit 1; fi
	uv run python -m scripts.extract $(DOC)

extract-bulletin:
	uv run python -m scripts.extract synthetic_regulations/synthetic/bulletins/B-2026-Q3-104.md

extract-hb2067:
	uv run python -m scripts.extract synthetic_regulations/real/HB02067I.txt

ui:
	uv run uvicorn api.main:app --reload --port 8765

test:
	uv run pytest tests/ -v

e2e:
	uv run python -m scripts.regression_test

# ── RHS (Snowflake) ─────────────────────────────────────────────────────
snowflake-test:
	@snow connection test --connection regulai

snowflake-setup:
	@snow sql -c regulai -q "\
		CREATE DATABASE IF NOT EXISTS INSURANCE_REGULATORY; \
		USE DATABASE INSURANCE_REGULATORY; \
		CREATE SCHEMA IF NOT EXISTS BRONZE; \
		CREATE SCHEMA IF NOT EXISTS SILVER; \
		CREATE SCHEMA IF NOT EXISTS GOLD; \
		CREATE SCHEMA IF NOT EXISTS REFERENCE; \
		CREATE SCHEMA IF NOT EXISTS STAGING;"

build-reference:
	uv run python -m scripts.build_reference_reason_codes

load-reference: build-reference
	@snow sql -c regulai -f materialized/reference/tspr_reason_code_map.sql

build-reference-all: build-reference
	uv run python -m scripts.build_all_reference_tables

load-reference-all: build-reference-all
	@for f in materialized/reference/*.sql; do \
	  echo "→ Loading $$f"; \
	  snow sql -c regulai --enable-templating standard -f "$$f" > /dev/null && echo "  ✓ done" || echo "  ✗ failed"; \
	done

migrate-validation-rules:
	uv run python -m scripts.migrate_kg_validation_rules

build-validation-rules: migrate-validation-rules
	uv run python -m scripts.build_validation_rules_reference

load-validation-rules: build-validation-rules
	@snow sql -c regulai --enable-templating standard -f materialized/reference/tspr_validation_rules.sql

# Re-apply rules that don't survive `load-validation-rules` (which DELETEs the
# table before re-loading from the auto-generated SQL — sourced only from
# rules with target_table set in the KG). These two files carry the
# hand-curated rules (A.22, A.34 variants, A.30/A.40/A.42, B.11, B.14, D.12).
# Idempotent: each INSERT is guarded with WHERE NOT EXISTS.
load-custom-validation-rules: load-validation-rules
	@snow sql -c regulai -f materialized/migrations/002_extra_validation_rules.sql > /dev/null && echo "  ✓ 002_extra_validation_rules.sql"
	@snow sql -c regulai -f materialized/migrations/003_claim_validation_rules.sql > /dev/null && echo "  ✓ 003_claim_validation_rules.sql"

# Run every numbered migration in materialized/migrations/ in order.
# All migrations are idempotent (CREATE TABLE IF NOT EXISTS, ALTER ADD COLUMN
# IF NOT EXISTS, INSERTs guarded with WHERE NOT EXISTS) so this is safe to
# re-run against an existing database.
migrate-snowflake:
	@echo "Applying Snowflake migrations:"
	@for f in materialized/migrations/[0-9]*.sql; do \
	  echo "  → $$f"; \
	  snow sql -c regulai -f "$$f" > /dev/null && echo "    ✓ done" || echo "    ✗ failed"; \
	done

run-silver:
	uv run python -m scripts.run_silver

run-gold:
	uv run python -m scripts.run_gold

detect-anomalies:
	uv run python -m scripts.detect_anomalies --month 2026-03

run-pipeline: load-bronze load-reference-all load-custom-validation-rules run-silver run-gold detect-anomalies
	@echo ""
	@echo "Full pipeline complete: Bronze → Silver → Gold."

reference: load-reference
	@echo ""
	@echo "Verification — querying Snowflake:"
	@snow sql -c regulai -q "SELECT tspr_reason_code, description, must_appear_alone, credit_score_companion_required FROM INSURANCE_REGULATORY.REFERENCE.TSPR_REASON_CODE_MAP ORDER BY tspr_reason_code;"

bronze-ddl:
	@echo "Loading IBM Bronze DDLs (PolicyCenter + ClaimCenter)..."
	@snow sql -c regulai --enable-templating standard -f "references/files -Snowflake/01_bronze_policycenter.sql" 2>&1 | tail -3
	@snow sql -c regulai --enable-templating standard -f "references/files -Snowflake/02_bronze_claimcenter.sql" 2>&1 | tail -3

build-bronze:
	uv run python -m scripts.generate_bronze_data

load-bronze: build-bronze
	uv run python -m scripts.load_bronze_to_snowflake

## Bulletin demo flow — show the flip
demo-bulletin-baseline:
	@echo "═══ BASELINE (no bulletin) ═══"
	@echo ""
	@$(MAKE) -s demo-join

demo-bulletin-apply:
	@echo "═══ APPLYING BULLETIN B-2026-Q4-118 ═══"
	@echo "  → Materializing bulletin into KG..."
	@uv run python -m scripts.apply_credit_score_bulletin 2>&1 | grep -v "Received notification" | tail -10
	@echo ""
	@echo "  → Bumping versions (supersede old Code L)..."
	@uv run python -m scripts.apply_bulletin --bulletin "Credit Score Declination Reporting Override" 2>&1 | tail -5
	@echo ""
	@echo "  → Regenerating reference table from KG..."
	@$(MAKE) -s load-reference > /dev/null
	@echo "  ✓ Snowflake reference table updated"
	@echo ""
	@echo "═══ AFTER BULLETIN — POL-0011 should now be VALID ═══"
	@$(MAKE) -s demo-join

demo-bulletin-reset:
	@echo "═══ RESETTING bulletin (back to baseline) ═══"
	@uv run python -m scripts.reset_credit_score_bulletin 2>&1 | grep -v "Received notification"
	@echo ""
	@echo "  → Regenerating reference table from KG..."
	@$(MAKE) -s load-reference > /dev/null
	@echo '  ✓ Reset complete. Run "make demo-bulletin-baseline" to see baseline.'

demo-join:
	@snow sql -c regulai -q "USE DATABASE INSURANCE_REGULATORY; \
		SELECT \
			p.policynumber AS policy, \
			j.subtype AS action, \
			COALESCE(j.cancellationreason, j.nonrenewalreason, j.declinereason) AS reason_code, \
			r.description AS regulation_describes, \
			CASE \
				WHEN r.must_appear_alone AND LENGTH(COALESCE(j.cancellationreason, j.nonrenewalreason, j.declinereason)) > 1 THEN 'INVALID — must_appear_alone' \
				WHEN r.credit_score_companion_required AND LENGTH(COALESCE(j.cancellationreason, j.nonrenewalreason, j.declinereason)) = 1 THEN 'INVALID — credit_score needs companion' \
				ELSE 'VALID' \
			END AS validation_status \
		FROM BRONZE.GW_PC_JOB j \
		JOIN BRONZE.GW_PC_POLICY p ON p.id = j.policy_id \
		LEFT JOIN REFERENCE.TSPR_REASON_CODE_MAP r ON r.tspr_reason_code = SUBSTR(COALESCE(j.cancellationreason, j.nonrenewalreason, j.declinereason), 1, 1) \
		ORDER BY p.policynumber;"

clean:
	docker compose down
