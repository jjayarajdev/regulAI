"""Deterministic source profiler — stage 1 of agentic ETL.

Reads a CSV or Parquet file and produces a `SourceProfile`: per-column type,
null rate, cardinality and a few sample values. No LLM — this is the cheap,
reproducible input the mapping agent reasons over (never the raw rows, which
keeps token cost bounded and the data plane deterministic).
"""

from __future__ import annotations

from pathlib import Path

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.csv as pacsv
import pyarrow.parquet as pq

from packages.rhs.mapper.schema import ColumnProfile, SourceProfile

# Cap the rows inspected for per-column stats. Row count is still reported in
# full; only the profiling scan is bounded so a huge file stays cheap.
_SAMPLE_ROWS = 5000
_SAMPLE_VALUES = 5


def _read_table(path: Path) -> pa.Table:
    suffix = path.suffix.lower()
    if suffix == ".parquet":
        return pq.read_table(path)
    if suffix in (".csv", ".txt"):
        return pacsv.read_csv(path)
    raise ValueError(f"Unsupported source type '{suffix}'. Use .csv or .parquet.")


def profile_file(path: str | Path, source_label: str | None = None) -> SourceProfile:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)

    table = _read_table(path)
    total = table.num_rows
    sample = table.slice(0, _SAMPLE_ROWS) if total > _SAMPLE_ROWS else table
    n = sample.num_rows

    columns: list[ColumnProfile] = []
    for name in table.column_names:
        col = sample.column(name)
        non_null = col.drop_null()
        distinct = pc.count_distinct(col).as_py() if n else 0
        samples = [str(v) for v in non_null.slice(0, _SAMPLE_VALUES).to_pylist()]
        columns.append(ColumnProfile(
            name=name,
            inferred_type=str(col.type),
            null_rate=round(col.null_count / n, 4) if n else 0.0,
            distinct_count=int(distinct or 0),
            sample_values=samples,
        ))

    return SourceProfile(
        source_label=source_label or path.stem,
        row_count=total,
        sampled_rows=n,
        columns=columns,
    )
