"""Upload storage + simple metadata registry.

Layout on disk:

  materialized/uploads/
    _registry.json                       # all uploads, newest-first
    upl_20260524_abc12345/
      original/pc_policy_template.xlsx   # exactly what the user uploaded
      parquet/gw_pc_policy.parquet       # converted by xlsx_to_parquet
      meta.json                          # per-upload metadata snapshot

Why a JSON registry vs Snowflake table:
  - The admin UI's list-uploads view shouldn't depend on Snowflake being
    reachable (it pre-dates pipeline execution).
  - 10s of uploads, not millions. JSON is fine.
  - Atomic file writes (tmp + rename) give us safety against half-writes.

Phase 2B will likely move this to a Snowflake table so the admin UI
works across multiple FastAPI replicas. Not now.
"""

import datetime as dt
import json
import secrets
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

UPLOADS_DIR = Path(__file__).resolve().parent.parent.parent / "materialized" / "uploads"
_REGISTRY_PATH = UPLOADS_DIR / "_registry.json"

UploadStatus = Literal[
    "uploaded",       # File written, not yet validated/converted
    "converted",      # xlsx → parquet succeeded, ready for processing
    "processing",     # Dagster job in flight
    "done",           # Dagster job finished SUCCESS
    "failed",         # Validation, conversion, or pipeline failure
]


@dataclass
class UploadRecord:
    """Everything we know about one upload. Persisted in _registry.json
    AND alongside the upload in upl_<id>/meta.json (defense in depth)."""
    upload_id: str
    filename: str                     # original filename the user uploaded
    bronze_table: str                 # template / target table
    bytes_size: int
    row_count: int | None = None      # populated after conversion
    status: UploadStatus = "uploaded"
    uploaded_at: dt.datetime = field(default_factory=lambda: dt.datetime.now(dt.UTC))
    uploaded_by: str = "admin"        # until authn lands
    last_run_id: str | None = None    # Dagster run id (set when "Process" clicked)
    error_message: str | None = None  # for failed status

    def to_dict(self) -> dict:
        return {
            "upload_id": self.upload_id,
            "filename": self.filename,
            "bronze_table": self.bronze_table,
            "bytes_size": self.bytes_size,
            "row_count": self.row_count,
            "status": self.status,
            "uploaded_at": self.uploaded_at.isoformat() if self.uploaded_at else None,
            "uploaded_by": self.uploaded_by,
            "last_run_id": self.last_run_id,
            "error_message": self.error_message,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "UploadRecord":
        d = dict(d)
        if isinstance(d.get("uploaded_at"), str):
            d["uploaded_at"] = dt.datetime.fromisoformat(d["uploaded_at"])
        return cls(**d)


def new_upload_id() -> str:
    """Format: upl_YYYYMMDD_<8 hex> — sortable + collision-resistant."""
    today = dt.datetime.now(dt.UTC).strftime("%Y%m%d")
    return f"upl_{today}_{secrets.token_hex(4)}"


def new_upload_dir(upload_id: str) -> Path:
    """Create the per-upload directory structure. Returns the root."""
    root = UPLOADS_DIR / upload_id
    (root / "original").mkdir(parents=True, exist_ok=True)
    (root / "parquet").mkdir(parents=True, exist_ok=True)
    return root


def upload_dir(upload_id: str) -> Path:
    return UPLOADS_DIR / upload_id


def parquet_path_for(upload_id: str, bronze_table: str) -> Path:
    """Where the converted Parquet lives. Matches the Dagster op's
    expected layout — the op just globs parquet/*.parquet."""
    return upload_dir(upload_id) / "parquet" / f"{bronze_table}.parquet"


# ── Registry IO ────────────────────────────────────────────────────


def _load_registry() -> list[UploadRecord]:
    if not _REGISTRY_PATH.exists():
        return []
    try:
        raw = json.loads(_REGISTRY_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        # Corrupt registry — start fresh rather than crash. Existing
        # upload dirs on disk are still recoverable from their meta.json.
        return []
    return [UploadRecord.from_dict(d) for d in raw]


def _save_registry(records: list[UploadRecord]) -> None:
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    tmp = _REGISTRY_PATH.with_suffix(".tmp")
    tmp.write_text(
        json.dumps([r.to_dict() for r in records], indent=2) + "\n",
        encoding="utf-8",
    )
    tmp.replace(_REGISTRY_PATH)


def record_upload(record: UploadRecord) -> None:
    """Persist a new upload to the registry + write its meta.json sidecar."""
    records = _load_registry()
    # Newest-first; dedup by upload_id (shouldn't happen, but be safe)
    records = [r for r in records if r.upload_id != record.upload_id]
    records.insert(0, record)
    _save_registry(records)
    _write_meta_sidecar(record)


def update_upload_status(
    upload_id: str,
    *,
    status: UploadStatus,
    row_count: int | None = None,
    last_run_id: str | None = None,
    error_message: str | None = None,
) -> UploadRecord | None:
    """Update status (and optionally row_count/run_id/error) on an
    existing upload. Returns the updated record, or None if not found."""
    records = _load_registry()
    updated: UploadRecord | None = None
    for r in records:
        if r.upload_id == upload_id:
            r.status = status
            if row_count is not None:
                r.row_count = row_count
            if last_run_id is not None:
                r.last_run_id = last_run_id
            if error_message is not None:
                r.error_message = error_message
            elif status not in ("failed",):
                # Clear stale error message on a clean transition
                r.error_message = None
            updated = r
            break
    if updated:
        _save_registry(records)
        _write_meta_sidecar(updated)
    return updated


def list_uploads(limit: int = 50) -> list[UploadRecord]:
    """Most recent first."""
    return _load_registry()[:limit]


def get_upload(upload_id: str) -> UploadRecord | None:
    for r in _load_registry():
        if r.upload_id == upload_id:
            return r
    return None


def _write_meta_sidecar(record: UploadRecord) -> None:
    """Defense in depth: every upload dir carries its own metadata copy
    so we can rebuild the registry from disk if it gets corrupted."""
    meta = upload_dir(record.upload_id) / "meta.json"
    if not meta.parent.exists():
        return  # upload dir was cleaned up; skip silently
    tmp = meta.with_suffix(".tmp")
    tmp.write_text(json.dumps(record.to_dict(), indent=2) + "\n", encoding="utf-8")
    tmp.replace(meta)
