"""P2.5 — workstation UI jurisdiction surfacing tests.

Verifies that the workstation HTML carries the new jurisdiction picker
markup + the data flow patterns that surface jurisdiction in the UI
(top-bar pill, dashboard filing-row pill, picker dialog handler).

These are markup/data-shape tests — they don't drive a browser. The /filings
API smoke test in test_filing_obligations.py already proves the data side.
"""

from __future__ import annotations

from pathlib import Path

import pytest


WORKSTATION_HTML = Path(__file__).resolve().parent.parent / "ui" / "workstation.html"


@pytest.fixture(scope="module")
def html() -> str:
    return WORKSTATION_HTML.read_text(encoding="utf-8")


def test_topbar_carries_jurisdiction_pill(html: str):
    """Top bar has the data-bind=topbar-jurisdiction element."""
    assert 'data-bind="topbar-jurisdiction"' in html, "topbar-jurisdiction binding missing"
    assert 'data-action="open-jurisdiction-picker"' in html


def test_jurisdiction_picker_handler_present(html: str):
    """The open-jurisdiction-picker action handler is wired."""
    assert "action === 'open-jurisdiction-picker'" in html
    # Handler should render an info dialog explaining the architecture
    assert "Active regulatory jurisdictions" in html
    assert "Federal defaults" in html or "federal defaults" in html


def test_filing_row_renders_jurisdiction_code(html: str):
    """Dashboard filing rows display the jurisdiction_code pill."""
    # The new render path includes jurisdiction_code on each row
    assert "jurisdiction_code" in html
    # The renderer falls back to US-TX when the field is missing
    assert "f.jurisdiction_code || 'US-TX'" in html or 'jur = f.jurisdiction_code' in html


def test_topbar_pill_updates_with_active_filing(html: str):
    """renderTopbar reads jurisdiction_code from the active filing."""
    assert "topbar-jurisdiction" in html
    # Pattern: jurEl.textContent = f.jurisdiction_code (or fallback)
    assert "jurEl.textContent" in html
