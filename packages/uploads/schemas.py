"""Bronze-table upload schemas.

Phase 2A scopes to ONE table — `bronze.gw_pc_policy` — to prove the
end-to-end upload→medallion pattern. Adding another table is:

  1. Append a TemplateSpec to TEMPLATES below
  2. The /admin/upload UI auto-picks it up (it iterates TEMPLATES)
  3. The Dagster op_load_bronze_from_upload already loops over every
     parquet file in the upload dir, so no Dagster change needed

Why we don't auto-derive from the SQL DDL:
  - DDLs carry CDC bookkeeping columns (_cdc_operation, _cdc_timestamp,
    _ingestion_timestamp, _source_file) that the customer shouldn't
    have to think about. We inject them at conversion time.
  - DDLs use Snowflake types (NUMBER, VARCHAR, TIMESTAMP_NTZ) that
    don't map 1:1 to PyArrow types we want in the Parquet file.
  - Explicit > implicit for a schema users see.
"""

from dataclasses import dataclass, field
from typing import Literal

import pyarrow as pa

# Logical types we expose in the template. Each maps to a PyArrow type
# for Parquet and an Excel cell type for the template header row.
LogicalType = Literal["string", "integer", "decimal", "date", "datetime", "boolean"]


@dataclass(frozen=True)
class ColumnSpec:
    """One column in an upload template."""
    name: str            # exact Snowflake column name — must match Bronze DDL
    logical_type: LogicalType
    description: str
    required: bool = True
    example: str | int | float | None = None  # rendered in row 2 of the template


@dataclass(frozen=True)
class TemplateSpec:
    """One Excel template = one Bronze table = one sheet on upload."""
    bronze_table: str    # e.g. "gw_pc_policy" — schema is always "bronze"
    sheet_name: str      # short name shown in the Excel tab
    description: str
    columns: list[ColumnSpec] = field(default_factory=list)

    @property
    def template_filename(self) -> str:
        """File name the user downloads — stable, predictable."""
        return f"{self.bronze_table}_template.xlsx"


def pyarrow_type_for(lt: LogicalType) -> pa.DataType:
    """Map our logical types → PyArrow types for the Parquet file.

    Conservative choices: int64 not int32, microsecond timestamps,
    Decimal(18, 2) for currency. Customers won't notice; downstream
    Snowflake COPY INTO will cast as needed.
    """
    return {
        "string":   pa.string(),
        "integer":  pa.int64(),
        "decimal":  pa.decimal128(18, 2),
        "date":     pa.date32(),
        "datetime": pa.timestamp("us"),
        "boolean":  pa.bool_(),
    }[lt]


# ───────────────────────────────────────────────────────────────────
# Phase 2A template registry — start narrow on purpose.
#
# pc_policy is the master policy table; uploading just this row set
# already exercises the full Bronze → Silver → Gold pipeline because
# Silver/Gold join against the other Bronze tables that stay populated
# from the synthetic seed loader.
# ───────────────────────────────────────────────────────────────────

TEMPLATES: list[TemplateSpec] = [
    TemplateSpec(
        bronze_table="gw_pc_policy",
        sheet_name="pc_policy",
        description=(
            "Guidewire PolicyCenter — pc_policy. Master policy row "
            "per (account, policy_number). Drives TSPR field cols 7-16 "
            "(POLICY) per Rule 26."
        ),
        columns=[
            ColumnSpec(
                name="id", logical_type="integer",
                description="GW internal policy ID (numeric, unique per row).",
                required=True, example=2000001,
            ),
            ColumnSpec(
                name="publicid", logical_type="string",
                description="GW public GUID (alphanumeric, optional).",
                required=False, example="pc:1234567890",
            ),
            ColumnSpec(
                name="account_id", logical_type="integer",
                description="FK → pc_account.id (the policyholder account).",
                required=True, example=300001,
            ),
            ColumnSpec(
                name="producercode_id", logical_type="integer",
                description="FK → pc_producercode.id (writing agent).",
                required=False, example=500001,
            ),
            ColumnSpec(
                name="policynumber", logical_type="string",
                description="Human-readable policy number — maps to TSPR POLICY cols 7-16.",
                required=True, example="HO-0010001",
            ),
            ColumnSpec(
                name="issuedate", logical_type="datetime",
                description="When the policy was first issued. YYYY-MM-DD or YYYY-MM-DD HH:MM:SS.",
                required=True, example="2025-01-15",
            ),
            ColumnSpec(
                name="originalinceptiondate", logical_type="datetime",
                description="Original inception date (not renewal). Same format as issuedate.",
                required=False, example="2025-01-15",
            ),
            ColumnSpec(
                name="createtime", logical_type="datetime",
                description="Row create timestamp from the source system.",
                required=False, example="2025-01-15 09:30:00",
            ),
            ColumnSpec(
                name="updatetime", logical_type="datetime",
                description="Row last-update timestamp from the source system.",
                required=False, example="2025-01-15 09:30:00",
            ),
            ColumnSpec(
                name="retiredvalue", logical_type="integer",
                description="GW soft-delete marker. 0 = active, non-zero = retired.",
                required=False, example=0,
            ),
        ],
    ),
]


def get_template(bronze_table: str) -> TemplateSpec | None:
    """Find a template by its Bronze table name. Returns None if unknown."""
    for t in TEMPLATES:
        if t.bronze_table == bronze_table:
            return t
    return None
