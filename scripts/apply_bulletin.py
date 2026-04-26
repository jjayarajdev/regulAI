"""Apply a BulletinOverride: bump versions on the rules/codes it overrides.

This is the rules-level loop's actuator. After Sentinel has extracted a
bulletin (and `materialize()` has written its `BulletinOverride` and
`OVERRIDES` edges into the KG), this script:

  1. Looks up the BulletinOverride node by name (or all of them, --all).
  2. For each `OVERRIDES` target (Rule, CodeValue, CodeList, etc.):
     - Sets the target's `effective_to` to the bulletin's `effective_date - 1 day`.
     - Sets `status = "superseded"`.
  3. Reports what changed.

The new versions of the affected nodes (e.g., the bulletin's CodeValue 26
"Named Storm Wind") are already in the KG from the materialize step —
they have `effective_from` = the bulletin's effective date. So after this
script runs, the KG contains both: the OLD rule, marked superseded with
an `effective_to` date, AND the NEW rule, active. Edition pinning queries
(WHERE effective_from <= AS_OF AND (effective_to IS NULL OR effective_to > AS_OF))
will pick the right version automatically.

Run:
  uv run python -m scripts.apply_bulletin BULLETIN="<override name>"
  uv run python -m scripts.apply_bulletin --all
  uv run python -m scripts.apply_bulletin --bulletin "Named Storm..." --dry-run
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta

from packages.adapters.lhs.gre.neo4j_adapter import Neo4jGREAdapter


def _color(text: str, code: str) -> str:
    if not sys.stdout.isatty():
        return text
    return f"\033[{code}m{text}\033[0m"


GREEN = lambda s: _color(s, "32")  # noqa: E731
YELLOW = lambda s: _color(s, "33") # noqa: E731
BOLD = lambda s: _color(s, "1")    # noqa: E731


def apply_bulletin(bulletin_name: str | None, dry_run: bool) -> int:
    """Bump versions on every node a BulletinOverride points to.

    Returns the count of (target_node, edge) pairs processed.
    """
    with Neo4jGREAdapter() as gre, gre.driver.session() as s:
        if bulletin_name:
            bulletins = s.run(
                "MATCH (b:BulletinOverride {name: $n}) "
                "RETURN b.name AS name, b.id AS id, b.effective_date AS effective_date",
                n=bulletin_name,
            ).data()
            if not bulletins:
                print(f"No BulletinOverride named {bulletin_name!r} in KG.")
                return 0
        else:
            bulletins = s.run(
                "MATCH (b:BulletinOverride) "
                "RETURN b.name AS name, b.id AS id, b.effective_date AS effective_date "
                "ORDER BY b.name"
            ).data()
            if not bulletins:
                print("No BulletinOverride nodes in the KG.")
                return 0

        total = 0
        for b in bulletins:
            print(BOLD(f"\n━━ {b['name']} ━━"))
            eff = b["effective_date"]
            if not eff:
                # Fall back to today; in production, every bulletin would
                # carry an effective_date. Print a warning so it's visible.
                print(YELLOW(f"  ⚠ no effective_date on bulletin; using today"))
                eff_iso = date.today().isoformat()
            else:
                eff_iso = str(eff)[:10]
            try:
                eff_date = date.fromisoformat(eff_iso)
            except ValueError:
                print(YELLOW(f"  ⚠ unparseable effective_date {eff_iso!r}; skipping"))
                continue
            cutoff = (eff_date - timedelta(days=1)).isoformat()

            targets = s.run("""
                MATCH (b:BulletinOverride {id: $bid})-[:OVERRIDES]->(target)
                RETURN target.id AS id,
                       target.name AS name,
                       labels(target) AS labels,
                       target.status AS status,
                       target.effective_to AS effective_to,
                       target.effective_from AS effective_from
            """, bid=b["id"]).data()

            if not targets:
                print(f"  (no OVERRIDES targets — nothing to bump)")
                continue

            for t in targets:
                lbl = next((x for x in (t["labels"] or []) if x != "GRENode"), "?")
                already = t["status"] == "superseded" and t["effective_to"]
                marker = "→" if not already else "(already superseded)"
                print(
                    f"  {marker:<22} ({lbl:<14}) {t['name']!r}"
                    + (f"   was status={t['status']!r}, effective_to={t['effective_to']!s}" if already else "")
                )
                total += 1

                if dry_run or already:
                    continue

                s.run("""
                    MATCH (n:GRENode {id: $id})
                    SET  n.status = 'superseded',
                         n.effective_to = date($cutoff)
                """, id=t["id"], cutoff=cutoff)
            print(GREEN(f"  ✓ effective_to set to {cutoff} on {len(targets)} target(s)"))

            # Backfill effective_from on the *new* content this bulletin
            # introduces — any node that CITES a Rule contained in this
            # bulletin's RegulationDocument and that doesn't already have an
            # effective_from. Without this, edition-pinning queries treat
            # Code 26 as "always active" rather than "active from 2026-10-01."
            if not dry_run:
                update = s.run("""
                    MATCH (b:BulletinOverride {id: $bid})-[:CITES]->(rule:Rule)
                          -[:CONTAINED_IN]->(d:RegulationDocument)
                    WITH b, collect(DISTINCT d) AS docs
                    UNWIND docs AS d
                    MATCH (n)-[:CITES]->(:Rule)-[:CONTAINED_IN]->(d)
                    WHERE n.effective_from IS NULL
                      AND NOT n:RegulationDocument
                      AND NOT n:BulletinOverride
                      AND NOT n:Rule
                      AND NOT (b)-[:OVERRIDES]->(n)         // skip targets being superseded
                    SET n.effective_from = date($eff_iso)
                    RETURN count(DISTINCT n) AS n_set
                """, bid=b["id"], eff_iso=eff_iso).single()
                if update and update["n_set"]:
                    print(GREEN(f"  ✓ effective_from = {eff_iso} on {update['n_set']} new node(s) introduced by this bulletin"))

        return total


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bulletin", help="Apply just this BulletinOverride name.")
    ap.add_argument("--all", action="store_true", help="Apply every BulletinOverride in the KG.")
    ap.add_argument("--dry-run", action="store_true", help="Show what would change without writing.")
    args = ap.parse_args()

    if not args.bulletin and not args.all:
        # Convenience: env var BULLETIN= so `make apply-bulletin BULLETIN=...` works.
        import os
        env = os.environ.get("BULLETIN")
        if env:
            args.bulletin = env
        else:
            ap.error("Pass --bulletin <name> or --all")

    n = apply_bulletin(args.bulletin, args.dry_run)
    print()
    if args.dry_run:
        print(f"[dry-run] {n} target(s) would be superseded.")
    else:
        print(f"Applied — {n} target(s) marked superseded.")


if __name__ == "__main__":
    main()
