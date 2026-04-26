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

clean:
	docker compose down
