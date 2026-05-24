"""Upload-driven Bronze ingest (Phase 2A).

End goal: a carrier compliance officer uploads an Excel file via
/admin/upload, the file lands in Snowflake's BRONZE layer, and the
Dagster medallion pipeline runs end-to-end against that data.

Phase 2A scope (this module):
  - Canonical .xlsx templates per Bronze table (start with `pc_policy`)
  - Upload staging in materialized/uploads/<upload_id>/
  - Excel → Parquet conversion matching Bronze DDL types
  - A registry of uploads with status (pending / processing / done / failed)

What's NOT in Phase 2A (deferred to Phase 2B):
  - Multi-table uploads (more sheets, more tables)
  - Direct-to-Snowflake-stage uploads (skipping local Parquet)
  - Per-carrier column-mapping config (today: assume template-exact)
  - Sensor-triggered auto-process (today: admin clicks "Process")
  - SFTP / S3 watch + ingest

Public surface:
  - TEMPLATES — registry of bronze-table → ColumnSpec list
  - UPLOADS_DIR — where files land on disk
  - new_upload_dir(), list_uploads(), get_upload() — IO
  - generate_template_workbook(table) — openpyxl Workbook for download
  - convert_uploaded_xlsx_to_parquet(upload) — does what it says
"""

from packages.uploads.schemas import TEMPLATES, ColumnSpec, TemplateSpec
from packages.uploads.storage import (
    UPLOADS_DIR,
    UploadRecord,
    UploadStatus,
    get_upload,
    list_uploads,
    new_upload_dir,
    new_upload_id,
    parquet_path_for,
    record_upload,
    update_upload_status,
    upload_dir,
)
from packages.uploads.templates import generate_template_workbook
from packages.uploads.xlsx_to_parquet import convert_uploaded_xlsx_to_parquet

__all__ = [
    "TEMPLATES",
    "ColumnSpec",
    "TemplateSpec",
    "UPLOADS_DIR",
    "UploadRecord",
    "UploadStatus",
    "get_upload",
    "list_uploads",
    "new_upload_dir",
    "new_upload_id",
    "parquet_path_for",
    "record_upload",
    "update_upload_status",
    "upload_dir",
    "generate_template_workbook",
    "convert_uploaded_xlsx_to_parquet",
]
