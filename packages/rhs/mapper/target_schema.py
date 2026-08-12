"""The canonical target contracts the agent maps *to*.

This is the load-bearing piece of agentic ETL: the agent can only map an
arbitrary source well if the target columns carry machine-readable *semantics*
(meaning, units, allowed codes, whether the pipeline derives them). Today this
lives implicitly inside run_silver.py's hand-written INSERT…SELECT; here we lift
it out as data so the agent — and later the compiler — can consume it.

Targets are *registered*: a `TargetSchema` descriptor (name, table, described
columns) per mappable staging table, looked up by name via `get_target()`.
Registered today:

  CIOM           (default) SILVER.TSPR_PREMIUM_STAGING — the canonical
                 insurance object model premium record. Unchanged behavior.
  FHCF_EXPOSURE  SILVER.FHCF_EXPOSURE_STAGING — the FL Hurricane Catastrophe
                 Fund annual data-call exposure record (scripts/run_fhcf.py).

Provenance note (FHCF_EXPOSURE): the approved KG materialization for the FHCF
data-call form (materialized/approved/fl-fhcf-data-call.materialized.json)
deliberately did NOT extract the record-layout tables into FieldRequirement
nodes ("Record-layout tables and code-list values were deliberately not
extracted…"), so the column semantics below are hardcoded from the FHCF-D1A
data-call form + the FL OIR-B1-1802 wind-mitigation attributes rather than
sourced from the graph.
"""

from __future__ import annotations

from pydantic import BaseModel


class TargetColumn(BaseModel):
    name: str
    dtype: str
    description: str
    required: bool = False
    # system_populated: filled by the pipeline (run id, source system, encoded
    # accounting month, validation status) — the agent must NOT map these.
    system_populated: bool = False
    # domain_encoded: value needs a TSPR-specific transform the agent should
    # flag for human curation rather than infer (e.g. the MMDDY date encoding).
    domain_encoded: bool = False


TSPR_PREMIUM_STAGING: list[TargetColumn] = [
    TargetColumn(name="NAIC_COMPANY_NO", dtype="string", required=True,
                 description="NAIC company code of the reporting insurer (5-digit)."),
    TargetColumn(name="POLICY_ID", dtype="string", required=True,
                 description="Unique policy number / identifier for the record."),
    TargetColumn(name="EFFECTIVE_DATE", dtype="string", required=True, domain_encoded=True,
                 description="TSPR MMDDY-encoded policy period start (MM + DD + last digit of year). "
                             "Source supplies a real date; the pipeline applies the encoding."),
    TargetColumn(name="EXPIRY_DATE", dtype="string", required=True, domain_encoded=True,
                 description="TSPR MMY-encoded policy period end (MM + last digit of year)."),
    TargetColumn(name="AMT_INSURANCE_DW", dtype="number",
                 description="Dwelling coverage limit (Coverage A), whole dollars."),
    TargetColumn(name="AMT_INSURANCE_PP", dtype="number",
                 description="Personal property coverage limit (Coverage C), whole dollars."),
    TargetColumn(name="AMT_INSURANCE_ALU", dtype="number",
                 description="Additional living / other-structures coverage limit, whole dollars."),
    TargetColumn(name="LINE_OF_BUSINESS", dtype="string",
                 description="Line of business code (e.g. HO homeowners, DP dwelling fire)."),
    TargetColumn(name="POLICY_FORM", dtype="string",
                 description="Policy form code (e.g. HO-3, HO-5, DP-3)."),
    TargetColumn(name="NUMBER_OF_FAMILIES", dtype="number",
                 description="Number of dwelling units / families (1–4)."),
    TargetColumn(name="COVERAGE_OCCUPANCY", dtype="string",
                 description="Occupancy code (owner-occupied, tenant, seasonal, vacant)."),
    TargetColumn(name="CONSTRUCTION", dtype="string",
                 description="Construction class (frame, masonry, fire-resistive)."),
    TargetColumn(name="PPC_SIMPLE", dtype="string",
                 description="Public Protection Class, single value (1–10)."),
    TargetColumn(name="PPC_SPLIT", dtype="string",
                 description="Public Protection Class in split form (e.g. 3/3Y). Use only if the source is split."),
    TargetColumn(name="DEDUCTIBLE_1_AMT", dtype="number",
                 description="Primary (all-other-perils) deductible amount, whole dollars."),
    TargetColumn(name="FIRE_PREMIUM", dtype="number",
                 description="Fire portion of written premium, whole dollars."),
    TargetColumn(name="EC_PREMIUM", dtype="number",
                 description="Extended-coverage portion of written premium, whole dollars."),
    TargetColumn(name="ROOF_COVERING", dtype="string",
                 description="Roof covering material (asphalt shingle, metal, tile, etc.)."),
    TargetColumn(name="ROOF_INSTALL_YEAR", dtype="number",
                 description="Four-digit year the roof was installed/replaced."),
    TargetColumn(name="ZIP9", dtype="string",
                 description="Risk-location ZIP, up to 9 digits (ZIP+4), digits only."),
    TargetColumn(name="YEAR_OF_CONSTRUCTION", dtype="number",
                 description="Four-digit year the dwelling was built."),
    TargetColumn(name="TENURE_CODE", dtype="string",
                 description="Continuous-tenure discount tier code, if the source carries one."),

    # System-populated — the pipeline sets these; the agent must not map them.
    TargetColumn(name="ACCOUNTING_MONTH", dtype="string", system_populated=True,
                 description="Reporting month; set from the pipeline run parameter."),
    TargetColumn(name="RUN_ID", dtype="string", system_populated=True,
                 description="Pipeline run id; provenance."),
    TargetColumn(name="RECORD_TYPE", dtype="string", system_populated=True,
                 description="TSPR record-type constant for premium rows."),
    TargetColumn(name="VALIDATION_STATUS", dtype="string", system_populated=True,
                 description="Set downstream by the rule engine."),
    TargetColumn(name="_SOURCE_SYSTEM", dtype="string", system_populated=True,
                 description="Provenance tag for the source system."),
]


class TargetSchema(BaseModel):
    """A registered mapping target: a named table plus described columns."""

    name: str          # registry key, e.g. "CIOM" or "FHCF_EXPOSURE"
    table: str         # the table the compiled INSERT loads
    description: str = ""
    columns: list[TargetColumn]


# ── FHCF_EXPOSURE — SILVER.FHCF_EXPOSURE_STAGING ──────────────────────────
# Columns exactly match _EXPOSURE_COLS_DDL in scripts/run_fhcf.py (minus the
# three system-populated audit columns, listed last). Descriptions carry the
# FHCF-D1A data-call semantics; see the module docstring for why they are
# hardcoded here rather than read from KG FieldRequirement nodes.
FHCF_EXPOSURE_STAGING: list[TargetColumn] = [
    TargetColumn(name="insurer_naic", dtype="string", required=True,
                 description="NAIC company code of the reporting insurer, zero-padded to the "
                             "FHCF 10-digit format (left-pad with '0'). Carrier-level, not "
                             "per-policy — comes from the underwriting-company reference table."),
    TargetColumn(name="policy_number", dtype="string", required=True,
                 description="Unique policy number of the Florida property policy."),
    TargetColumn(name="risk_zip", dtype="string", required=True,
                 description="5-digit ZIP of the insured risk location. FL ZIPs start with 3 "
                             "(32xxx–34xxx); keep as text to preserve leading digits, trimmed."),
    TargetColumn(name="risk_zip4", dtype="string",
                 description="ZIP+4 add-on of the risk location (4 digits), if known."),
    TargetColumn(name="county_fips", dtype="string", required=True,
                 description="Florida county FIPS sub-code, 2 digits, valid range 01–67. "
                             "Keep as text (leading zero significant), trimmed."),
    TargetColumn(name="state_code", dtype="string", required=True,
                 description="Two-letter state of the risk location — always 'FL' for the FHCF "
                             "data call; uppercase and trim the source value."),
    TargetColumn(name="policy_form", dtype="string",
                 description="Homeowners policy form code (HO3, HO5, DP1, …)."),
    TargetColumn(name="effective_date", dtype="date", required=True,
                 description="Policy period start as a DATE (cast from the source timestamp)."),
    TargetColumn(name="expiry_date", dtype="date", required=True,
                 description="Policy period end as a DATE (cast from the source timestamp)."),
    TargetColumn(name="occupancy_type", dtype="string", domain_encoded=True,
                 description="FHCF occupancy code: 'O1' owner-occupied single family, "
                             "'O2' any other occupancy."),
    TargetColumn(name="construction_type", dtype="string",
                 description="Construction class code (F frame, M masonry, …)."),
    TargetColumn(name="year_built", dtype="number",
                 description="Four-digit year the dwelling was built, as an integer."),
    TargetColumn(name="protection_class", dtype="number",
                 description="Public Protection Class (1–10) as an integer."),
    TargetColumn(name="coverage_a", dtype="number", required=True,
                 description="Coverage A (dwelling) limit in whole dollars, integer."),
    TargetColumn(name="hurricane_deductible", dtype="number",
                 description="Hurricane deductible in whole dollars, integer. Guidewire's "
                             "natural home is the tropical-cyclone deductible on the coverage."),
    TargetColumn(name="written_premium", dtype="number",
                 description="Written premium in whole dollars, integer."),
    TargetColumn(name="wind_mitigation", dtype="string", domain_encoded=True,
                 description="Wind-mitigation credit flag: 'Y' when an FL OIR-B1-1802 inspection "
                             "is on file, else 'N'. Normalize: any non-'Y' source value "
                             "(including null) reports 'N'."),
    TargetColumn(name="opening_protection", dtype="string",
                 description="Wind-mitigation companion (OIR-B1-1802): opening-protection class "
                             "code (e.g. 'A' = FBC-rated). Null when no inspection."),
    TargetColumn(name="roof_cover_type", dtype="string", domain_encoded=True,
                 description="Wind-mitigation companion (OIR-B1-1802): roof cover type code. "
                             "Reported only when wind_mitigation = 'Y', else NULL. In Guidewire "
                             "this rides the HO policy line's roof covering type."),
    TargetColumn(name="roof_deck_attachment", dtype="string",
                 description="Wind-mitigation companion (OIR-B1-1802): roof deck attachment "
                             "code (e.g. 'C' = 8d nails). Null when no inspection."),
    TargetColumn(name="roof_to_wall_connection", dtype="string",
                 description="Wind-mitigation companion (OIR-B1-1802): roof-to-wall connection "
                             "code (e.g. 'D' = double wrap). Null when no inspection."),
    TargetColumn(name="secondary_water_resistance", dtype="string",
                 description="Wind-mitigation companion (OIR-B1-1802): secondary water "
                             "resistance present, 'Y'/'N'. Null when no inspection."),
    TargetColumn(name="latitude", dtype="number",
                 description="Risk geocode latitude in micro-degrees (degrees × 1e6, BIGINT)."),
    TargetColumn(name="longitude", dtype="number",
                 description="Risk geocode longitude in micro-degrees (degrees × 1e6, BIGINT; "
                             "negative in Florida)."),
    TargetColumn(name="reporting_year", dtype="number", required=True, domain_encoded=True,
                 description="Data-call reporting year — a constant per cycle, the year of the "
                             "filing period start (2025 for FHCF-A-2026)."),
    TargetColumn(name="source_file", dtype="string",
                 description="Provenance: fixed name of the generated data-call extract, "
                             "'FHCF_D1A_GUIDEWIRE_<reporting_year>.txt'."),

    # System-populated — the pipeline sets these; the agent must not map them.
    TargetColumn(name="_created_timestamp", dtype="timestamp", system_populated=True,
                 description="Load timestamp; set by the pipeline."),
    TargetColumn(name="_pipeline_run_id", dtype="string", system_populated=True,
                 description="Pipeline run id; provenance."),
    TargetColumn(name="_source_system", dtype="string", system_populated=True,
                 description="Provenance tag for the source system (GUIDEWIRE)."),
]


# ── Registry ──────────────────────────────────────────────────────────────
DEFAULT_TARGET_NAME = "CIOM"

TARGETS: dict[str, TargetSchema] = {
    "CIOM": TargetSchema(
        name="CIOM",
        table="SILVER.TSPR_PREMIUM_STAGING",
        description="Canonical insurance object model — TSPR premium staging record.",
        columns=TSPR_PREMIUM_STAGING,
    ),
    "FHCF_EXPOSURE": TargetSchema(
        name="FHCF_EXPOSURE",
        table="INSURANCE_REGULATORY.SILVER.FHCF_EXPOSURE_STAGING",
        description="Florida Hurricane Catastrophe Fund annual data-call exposure record "
                    "(FHCF-D1A personal lines residential), one row per FL property policy.",
        columns=FHCF_EXPOSURE_STAGING,
    ),
}


def get_target(name_or_table: str = DEFAULT_TARGET_NAME) -> TargetSchema:
    """Resolve a registered target by registry name or by target table name.

    Table-name resolution keeps the historical call sites working: callers that
    pass "SILVER.TSPR_PREMIUM_STAGING" still get the CIOM contract.
    """
    if name_or_table in TARGETS:
        return TARGETS[name_or_table]
    wanted = name_or_table.strip().upper()
    for t in TARGETS.values():
        table = t.table.upper()
        if table == wanted or table.endswith("." + wanted) or wanted.endswith("." + table):
            return t
    raise KeyError(
        f"'{name_or_table}' is not a registered mapping target. "
        f"Known: {', '.join(TARGETS)}"
    )


def render_target_contract(columns: list[TargetColumn]) -> str:
    """Human/agent-readable rendering of the mappable target contract."""
    lines: list[str] = []
    for c in columns:
        if c.system_populated:
            continue  # not the agent's job
        tags = []
        if c.required:
            tags.append("REQUIRED")
        if c.domain_encoded:
            tags.append("DOMAIN-ENCODED→needs_review")
        tag = f"  [{', '.join(tags)}]" if tags else ""
        lines.append(f"- {c.name} ({c.dtype}){tag}: {c.description}")
    return "\n".join(lines)
