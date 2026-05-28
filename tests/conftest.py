"""Shared pytest fixtures + hygiene hooks.

Notably: this conftest detects that `test_neo4j_adapter.py` and
`test_materialization.py` wipe the live KG in their fixtures (necessary for
isolated adapter testing, but destructive for the development environment).
After the test session finishes, we re-seed the KG via `make rebuild-kg` if
those destructive test modules ran — so the workstation isn't left looking
at an empty graph.

The proper long-term fix is a dedicated test database (per
docs/enterprise-readiness.md), but until that lands this hook prevents the
"pytest wiped my demo" footgun.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent

# Test modules that call Neo4jGREAdapter.wipe_all() in their fixtures.
_DESTRUCTIVE_MODULES = {"test_neo4j_adapter", "test_materialization"}


def pytest_collection_modifyitems(config, items):
    """Tag destructive tests + reorder them to run LAST.

    The wipe_all-based fixtures destroy the live KG. Running them after
    every other test means tests that depend on the seeded canon
    (test_kg_audit, test_version_chain, etc.) get the populated graph
    they expect. The post-session conftest hook re-seeds for next time.
    """
    destructive: list = []
    other: list = []
    for item in items:
        mod = item.module.__name__.split(".")[-1]
        if mod in _DESTRUCTIVE_MODULES:
            item.add_marker(pytest.mark.kg_destructive)
            destructive.append(item)
        else:
            other.append(item)
    items[:] = other + destructive


@pytest.hookimpl(trylast=True)
def pytest_sessionfinish(session, exitstatus):
    """If any destructive tests ran in this session, re-seed the KG."""
    if not hasattr(session, "items"):
        return
    ran_destructive = any(
        getattr(item, "module", None) is not None
        and item.module.__name__.split(".")[-1] in _DESTRUCTIVE_MODULES
        for item in session.items
    )
    if not ran_destructive:
        return
    # Best-effort reseed — don't fail the session if this errors out.
    # The full restoration chain matches the dev-bring-up flow:
    #   rebuild-kg                — base canon (nodes only)
    #   migrate                    — constraints + indexes + Phase 2 unique constraint
    #   migrate-validation-rules   — attach executable rule SQL
    #   seed-jurisdictions         — Phase 2: Jurisdiction/Regulator/Agent + APPLIES_IN
    #   tag-federal-defaults       — Phase 2: ~9 federal-default rules, ~5 codelists
    try:
        for target in (
            "rebuild-kg",
            "migrate",
            "migrate-validation-rules",
            "seed-jurisdictions",
            "tag-federal-defaults",
            "seed-filing-obligations",
            "seed-florida",
            "migrate-fl-validation-rules",
        ):
            subprocess.run(
                ["make", target],
                cwd=_REPO_ROOT,
                check=False,
                capture_output=True,
                timeout=120,
            )
        print("\n[conftest] Re-seeded KG + migrate + Phase 2 state after destructive tests.")
    except Exception as e:
        print(f"\n[conftest] WARNING: KG re-seed failed: {e}")
