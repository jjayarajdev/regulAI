"""LHS-2 seed — populates Neo4j with hand-crafted regulatory canon.

DESTRUCTIVE: wipes the database first, then writes a coherent starter graph
covering the TICO Texas Statistical Plan for Residential Risks (eff. 2026-01-01),
HB 2067, Commissioner's Bulletin B-0008-25, and supporting structure.

After seeding, Neo4j Browser will show a meaningful graph at http://localhost:7474.
Try: MATCH (n) RETURN n LIMIT 100

Run via: make seed
"""

from datetime import date

from packages.adapters.lhs.gre.neo4j_adapter import Neo4jGREAdapter
from packages.core.enums import (
    CitationKind,
    DocumentKind,
    HITLSeverity,
    NodeStatus,
    OrgKind,
    RelationshipType,
    ReportCadence,
)
from packages.core.nodes import (
    BulletinOverride,
    CodeList,
    CodeValue,
    CoverageType,
    EndorsementRule,
    HITLTriggerRule,
    Organization,
    ReconciliationRule,
    RecordLayout,
    RegulationDocument,
    ReportTemplate,
    Rule,
    StatPlanEdition,
)
from packages.core.relationships import CitesRelationship, GRERelationship


def seed() -> None:
    print("LHS-2 seed — populating Neo4j with regulatory canon\n")

    with Neo4jGREAdapter() as gre:
        print("Wiping existing data...")
        gre.wipe_all()
        print("  ✓ Database empty\n")

        # ---- Documents ------------------------------------------------------

        tico_plan = RegulationDocument(
            name="Texas Statistical Plan for Residential Risks (eff. 2026-01-01)",
            kind=DocumentKind.STAT_PLAN,
            title="Texas Statistical Plan for Residential Risks",
            hash="tico-tx-stat-plan-2026-01-01",
            source_url="https://www.tdi.texas.gov/rules/2025/documents/statplanres.pdf",
            published_date=date(2025, 12, 18),
            status=NodeStatus.APPROVED,
            effective_from=date(2026, 1, 1),
        )

        hb_2067 = RegulationDocument(
            name="HB 2067 (89th Legislature, Regular Session)",
            kind=DocumentKind.STATUTE,
            title="HB 2067 — Declination, Cancellation, Nonrenewal of Insurance Policies",
            hash="hb-2067-89r",
            source_url="https://capitol.texas.gov/tlodocs/89R/billtext/pdf/HB02067I.pdf",
            published_date=date(2025, 5, 28),
            status=NodeStatus.APPROVED,
            effective_from=date(2025, 9, 1),
        )

        bulletin_0008 = RegulationDocument(
            name="Commissioner's Bulletin B-0008-25",
            kind=DocumentKind.BULLETIN,
            title="HB 2067 Implementation — Phase 1 Residential & PPA",
            hash="tdi-bulletin-b-0008-25",
            source_url="https://www.tdi.texas.gov/bulletins/2025/b-0008-25.html",
            published_date=date(2025, 6, 12),
            status=NodeStatus.APPROVED,
        )

        for doc in (tico_plan, hb_2067, bulletin_0008):
            gre.create_node(doc)
        print(f"  ✓ 3 RegulationDocuments")

        # ---- Edition --------------------------------------------------------

        thsp_2026 = StatPlanEdition(
            name="THSP_2026",
            edition_name="THSP_2026",
            effective_date=date(2026, 1, 1),
            supersedes_edition="THSP_2022",
            status=NodeStatus.APPROVED,
            effective_from=date(2026, 1, 1),
        )
        gre.create_node(thsp_2026)
        print(f"  ✓ 1 StatPlanEdition (THSP_2026)")

        # ---- Organizations --------------------------------------------------

        tico_org = Organization(
            name="TICO",
            org_name="Texas Insurance Checking Office",
            org_kind=OrgKind.STATISTICAL_AGENT,
            description="TDI's designated statistical agent for residential property insurance",
            status=NodeStatus.APPROVED,
        )
        tdi_org = Organization(
            name="TDI",
            org_name="Texas Department of Insurance",
            org_kind=OrgKind.REGULATOR,
            status=NodeStatus.APPROVED,
        )
        naic_org = Organization(
            name="NAIC",
            org_name="National Association of Insurance Commissioners",
            org_kind=OrgKind.REGULATOR,
            status=NodeStatus.APPROVED,
        )
        for org in (tico_org, tdi_org, naic_org):
            gre.create_node(org)
        print(f"  ✓ 3 Organizations (TICO, TDI, NAIC)")

        # ---- Rules ----------------------------------------------------------

        rules_data = [
            ("A", 6, "Amounts of Insurance — Premiums and Losses"),
            ("A", 21, "Experience to Be Reported"),
            ("A", 28, "Designated Statistical Agent"),
            ("A", 29, "Transmittal Form"),
            ("A", 34, "Reason Codes"),
            ("A", 35, "Actual Cancellations, Nonrenewals, and Declinations"),
            ("B", 12, "Cause of Loss Codes"),
        ]
        rule_nodes: dict[tuple[str, int], Rule] = {}
        for section, num, title in rules_data:
            r = Rule(
                name=f"Rule {section}.{num} — {title}",
                section=section,
                rule_number=num,
                title=title,
                document_id=tico_plan.id,
                status=NodeStatus.APPROVED,
            )
            gre.create_node(r)
            rule_nodes[(section, num)] = r
            gre.create_relationship(
                GRERelationship(
                    type=RelationshipType.CONTAINED_IN,
                    src_node_id=r.id,
                    dst_node_id=tico_plan.id,
                )
            )
        print(f"  ✓ {len(rules_data)} Rules (A.6, A.21, A.28, A.29, A.34, A.35, B.12)")

        # ---- Report Templates -----------------------------------------------

        templates_data = [
            ("HO Premiums", "Dwelling, HO Premiums", ReportCadence.MONTHLY, 45),
            ("HO Losses", "Dwelling, HO Losses", ReportCadence.MONTHLY, 45),
            (
                "HO Notice Report",
                "Dwelling, HO Cancellation, Nonrenewal, and Declination Notices",
                ReportCadence.MONTHLY,
                45,
            ),
            (
                "HO Notice Count Report",
                "Dwelling, HO Number of Actual Cancellations, Nonrenewals, and Declinations",
                ReportCadence.MONTHLY,
                45,
            ),
            (
                "Transmittal Form",
                "Residential Property Data Submission Transmittal Form",
                ReportCadence.MONTHLY,
                45,
            ),
        ]
        templates: dict[str, ReportTemplate] = {}
        rule_a28 = rule_nodes[("A", 28)]
        rule_a29 = rule_nodes[("A", 29)]
        for short_name, full_name, cadence, days in templates_data:
            t = ReportTemplate(
                name=short_name,
                report_name=full_name,
                cadence=cadence,
                deadline_days_after_close=days,
                status=NodeStatus.APPROVED,
                effective_from=date(2026, 1, 1),
            )
            gre.create_node(t)
            templates[short_name] = t
            # Reports cite Rule A.28 (which establishes the four required reports);
            # transmittal cites A.29.
            cite_target = rule_a29 if short_name == "Transmittal Form" else rule_a28
            gre.create_relationship(
                CitesRelationship(
                    src_node_id=t.id,
                    dst_node_id=cite_target.id,
                    char_start=0,
                    char_end=200,
                    kind=CitationKind.DEFINES,
                )
            )
        print(f"  ✓ {len(templates_data)} ReportTemplates (with CITES → A.28/A.29)")

        # ---- Record Layouts -------------------------------------------------

        layouts_data = [
            ("Premium Record Layout", "HO Premiums", "C"),
            ("Loss Record Layout", "HO Losses", "D"),
            ("Notice Record Layout", "HO Notice Report", "E"),
            ("Notice Count Record Layout", "HO Notice Count Report", "G"),
        ]
        for layout_name, template_name, _section in layouts_data:
            rl = RecordLayout(
                name=layout_name,
                layout_name=layout_name,
                status=NodeStatus.APPROVED,
            )
            gre.create_node(rl)
            gre.create_relationship(
                GRERelationship(
                    type=RelationshipType.CONTAINS_LAYOUT,
                    src_node_id=templates[template_name].id,
                    dst_node_id=rl.id,
                )
            )
        print(f"  ✓ 4 RecordLayouts (with CONTAINS_LAYOUT from templates)")

        # ---- Code Lists + Values --------------------------------------------

        # Use the same canonical naming the bulletin extraction produces, so
        # the bulletin's BulletinOverride dedups onto these seeded nodes
        # rather than creating parallel "Cause of Loss Code N" siblings.
        col_list = CodeList(
            name="Cause of Loss Code List",
            code_list_name="Cause of Loss Code List",
            description="Loss-cause classification per Rule B§12",
            status=NodeStatus.APPROVED,
        )
        gre.create_node(col_list)

        rule_b12 = rule_nodes[("B", 12)]
        col_values = [
            ("05", "Fire — Internal Source"),
            ("10", "Fire — External Source (Including fire caused by lightning)"),
            ("25", "Windstorm"),
            ("30", "Hail"),
            ("32", "Flood or Rising Water"),
            ("75", "Burglary, Theft, Robbery"),
        ]
        for code, desc in col_values:
            cv = CodeValue(
                name=f"Cause of Loss Code {code} — {desc}",
                code=code,
                description=desc,
                code_list_id=col_list.id,
                status=NodeStatus.APPROVED,
            )
            gre.create_node(cv)
            gre.create_relationship(
                GRERelationship(
                    type=RelationshipType.HAS_VALUE,
                    src_node_id=col_list.id,
                    dst_node_id=cv.id,
                )
            )
            gre.create_relationship(
                CitesRelationship(
                    src_node_id=cv.id,
                    dst_node_id=rule_b12.id,
                    char_start=0,
                    char_end=120,
                    kind=CitationKind.DEFINES,
                )
            )

        lob_list = CodeList(
            name="Line of Business",
            code_list_name="Line of Business",
            description="Per Rule B§4",
            status=NodeStatus.APPROVED,
        )
        gre.create_node(lob_list)
        for code, desc in [
            ("02", "Homeowners Tenants Policies, including Condominium Owners"),
            ("03", "Homeowners Policies, Excluding Tenants Forms"),
            ("13", "Dwelling Policies — TWIA Wind-Only"),
        ]:
            cv = CodeValue(
                name=f"LOB {code} — {desc}",
                code=code,
                description=desc,
                code_list_id=lob_list.id,
                status=NodeStatus.APPROVED,
            )
            gre.create_node(cv)
            gre.create_relationship(
                GRERelationship(
                    type=RelationshipType.HAS_VALUE,
                    src_node_id=lob_list.id,
                    dst_node_id=cv.id,
                )
            )

        hb2067_reason_list = CodeList(
            name="HB 2067 Reason Codes",
            code_list_name="HB 2067 Reason Codes",
            description="Cancellation/Nonrenewal/Declination reason codes per Section F (populated in LHS-3)",
            status=NodeStatus.APPROVED,
        )
        gre.create_node(hb2067_reason_list)
        print(f"  ✓ 3 CodeLists (Cause of Loss with 6 values, Line of Business with 3, HB 2067 Reasons)")

        # ---- Coverage Types -------------------------------------------------

        rule_a6 = rule_nodes[("A", 6)]
        for coverage_name, forms in [
            ("Dwelling", ["HO-3", "HO-5", "DP-3"]),
            ("Personal Property", ["HO-3", "HO-5", "DP-3", "Tenants"]),
            ("Loss of Use", ["HO-3", "HO-5"]),
        ]:
            cov = CoverageType(
                name=coverage_name,
                coverage_name=coverage_name,
                applies_to_forms=forms,
                status=NodeStatus.APPROVED,
            )
            gre.create_node(cov)
            gre.create_relationship(
                CitesRelationship(
                    src_node_id=cov.id,
                    dst_node_id=rule_a6.id,
                    char_start=0,
                    char_end=180,
                    kind=CitationKind.DEFINES,
                )
            )
        print(f"  ✓ 3 CoverageTypes (cite Rule A.6)")

        # ---- Endorsement ----------------------------------------------------

        ho15 = EndorsementRule(
            name="HO-15",
            form_code="HO-15",
            form_name="Special Personal Property Coverage",
            coverage_effect="Upgrades personal property coverage from named perils to all risk",
            status=NodeStatus.APPROVED,
        )
        gre.create_node(ho15)
        print(f"  ✓ 1 EndorsementRule (HO-15)")

        # ---- Reconciliation -------------------------------------------------

        recon = ReconciliationRule(
            name="Notice Count vs NAIC MCAS",
            from_report_id=templates["HO Notice Count Report"].id,
            against_target="NAIC Market Conduct Annual Statement (Cancellations & Nonrenewals)",
            status=NodeStatus.APPROVED,
        )
        gre.create_node(recon)
        rule_a35 = rule_nodes[("A", 35)]
        gre.create_relationship(
            CitesRelationship(
                src_node_id=recon.id,
                dst_node_id=rule_a35.id,
                char_start=0,
                char_end=300,
                kind=CitationKind.DEFINES,
            )
        )
        gre.create_relationship(
            GRERelationship(
                type=RelationshipType.RECONCILES_WITH,
                src_node_id=templates["HO Notice Count Report"].id,
                dst_node_id=naic_org.id,
            )
        )
        print(f"  ✓ 1 ReconciliationRule (Notice Count → NAIC MCAS)")

        # ---- Bulletin Override ----------------------------------------------

        b0008_override = BulletinOverride(
            name="B-0008-25 → Phase 1 Residential & PPA",
            bulletin_ref=bulletin_0008.id,
            effective_date=date(2026, 4, 1),
            status=NodeStatus.APPROVED,
        )
        gre.create_node(b0008_override)
        gre.create_relationship(
            GRERelationship(
                type=RelationshipType.OVERRIDES,
                src_node_id=b0008_override.id,
                dst_node_id=rule_nodes[("A", 34)].id,
            )
        )
        print(f"  ✓ 1 BulletinOverride (B-0008-25 → Rule A.34)")

        # ---- HITL Trigger Rules (application-derived) -----------------------

        for trigger_name, condition, severity in [
            (
                "Wind/Hail Named Storm Ambiguity",
                "Wind or hail claim during a named storm event requires manual classification",
                HITLSeverity.TIER2,
            ),
            (
                "Novel Endorsement Form",
                "Endorsement form not previously seen by the system requires SOP authoring",
                HITLSeverity.TIER3,
            ),
        ]:
            htr = HITLTriggerRule(
                name=trigger_name,
                trigger_name=trigger_name,
                condition_summary=condition,
                severity=severity,
                status=NodeStatus.APPROVED,
            )
            gre.create_node(htr)
        print(f"  ✓ 2 HITLTriggerRules")

        # ---- Org relationships ---------------------------------------------

        gre.create_relationship(
            GRERelationship(
                type=RelationshipType.DESIGNATED_BY,
                src_node_id=tico_org.id,
                dst_node_id=tdi_org.id,
            )
        )
        print(f"  ✓ 1 DESIGNATED_BY relationship (TICO → TDI)")

        # ---- Verify ---------------------------------------------------------

        total = gre.count_nodes()
        rels = gre.count_relationships()
        by_type = gre.count_by_type()
        print(f"\nSeed complete: {total} nodes, {rels} relationships")
        print("\nBy type:")
        for type_name, count in by_type.items():
            print(f"  {type_name:25s} {count:3d}")

        print("\n→ Open Neo4j Browser: http://localhost:7474")
        print("  Credentials: neo4j / regulai-dev-password")
        print("\nUseful starter queries:")
        print("  MATCH (n) RETURN n LIMIT 100")
        print("  MATCH (d:RegulationDocument)<-[:CONTAINED_IN]-(r:Rule) RETURN d, r")
        print("  MATCH (cv:CodeValue)-[:CITES]->(rule:Rule) RETURN cv, rule")
        print("  MATCH (t:ReportTemplate)-[:CITES]->(rule:Rule) RETURN t, rule")


if __name__ == "__main__":
    seed()
