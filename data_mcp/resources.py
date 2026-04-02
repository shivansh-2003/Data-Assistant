"""
MCP resources for read-only session context (registered on the shared FastMCP instance).
Import this module after `data` so decorators attach to the same `mcp`.
"""

from __future__ import annotations

import json
from typing import Any

import pandas as pd

try:
    from data_mcp.data import mcp
    from data_mcp.data_functions.core import (
        get_data_summary,
        get_table_data,
        operation_history,
        list_available_tables,
    )
except ImportError:
    from data import mcp
    from data_functions.core import (
        get_data_summary,
        get_table_data,
        operation_history,
        list_available_tables,
    )

_PREVIEW_ROWS = 10
_MAX_CELL_CHARS = 200
_OPS_PER_TABLE = 20


def _truncate_cell(val: Any) -> str:
    s = str(val)
    if len(s) > _MAX_CELL_CHARS:
        return s[: _MAX_CELL_CHARS] + "…"
    return s


def _df_to_preview_markdown(df: pd.DataFrame, n: int) -> str:
    sub = df.head(n)
    if sub.empty:
        return "_No rows_"
    try:
        return sub.to_markdown(index=False)
    except Exception:
        lines = ["| " + " | ".join(str(c) for c in sub.columns) + " |"]
        lines.append("| " + " | ".join("---" for _ in sub.columns) + " |")
        for _, row in sub.iterrows():
            lines.append(
                "| " + " | ".join(_truncate_cell(row[c]) for c in sub.columns) + " |"
            )
        return "\n".join(lines)


@mcp.resource(
    "session://{session_id}/summary",
    mime_type="text/markdown",
    name="session_summary",
    description="Markdown summary: tables, shape, dtypes, missing counts (use read_resource).",
)
def get_session_summary_resource(session_id: str) -> str:
    summary = get_data_summary(session_id, "current")
    if not summary.get("success"):
        return (
            f"# Session: `{session_id}`\n\n"
            f"**Error:** {summary.get('error', 'Unknown')}\n\n"
            f"Available tables: {', '.join(summary.get('available_tables', []) or [])}"
        )

    tables = list_available_tables(session_id)
    missing = summary.get("missing_values", {})
    return f"""# Session: `{session_id}`

## Tables
{", ".join(tables) if tables else "_none_"}

## Table `{summary.get("table_name")}` (default focus)
- Shape: **{summary["shape"]["rows"]}** rows × **{summary["shape"]["columns"]}** columns
- Memory: **{summary.get("memory_usage_mb", 0)}** MB

## Columns
{", ".join(summary.get("columns", []))}

## Missing values
- Total missing cells: **{missing.get("total_missing", 0)}**
- Columns with gaps: **{len(missing.get("columns_with_missing", []))}**

## Types
- Numeric: {len(summary.get("numeric_columns", []))}
- Categorical/object: {len(summary.get("categorical_columns", []))}
- Date/datetime: {len(summary.get("date_columns", []))}
"""


@mcp.resource(
    "session://{session_id}/tables/{table_name}/preview",
    mime_type="text/markdown",
    name="table_preview",
    description="First rows + dtypes as Markdown (bounded).",
)
def get_table_preview_resource(session_id: str, table_name: str) -> str:
    df = get_table_data(session_id, table_name)
    if df is None:
        avail = list_available_tables(session_id)
        return (
            f"# Table not found\n\n"
            f"`{table_name}` in session `{session_id}`.\n\n"
            f"Available: {', '.join(avail) if avail else '_none_'}"
        )

    preview_md = _df_to_preview_markdown(df, _PREVIEW_ROWS)
    dtype_lines = "\n".join(f"- `{col}`: `{dtype}`" for col, dtype in df.dtypes.items())
    return f"""# Table: `{table_name}`

## Preview (first {_PREVIEW_ROWS} rows)
{preview_md}

## Schema
- Shape: **{len(df)}** × **{len(df.columns)}**

**Column types:**
{dtype_lines}
"""


@mcp.resource(
    "session://{session_id}/operations",
    mime_type="text/markdown",
    name="operations_history",
    description="Recent undo/redo-style operation log per table (bounded).",
)
def get_operations_history_resource(session_id: str) -> str:
    if session_id not in operation_history or not operation_history[session_id]:
        return f"# Operation history\n\nNo operations recorded for session `{session_id}`."

    parts = [f"# Operation history — `{session_id}`\n"]
    for table_name, ops in operation_history[session_id].items():
        parts.append(f"## Table `{table_name}`\n")
        parts.append("| # | Type | Timestamp | Details |")
        parts.append("| --- | --- | --- | --- |")
        recent = ops[-_OPS_PER_TABLE :]
        for idx, op in enumerate(recent, 1):
            otype = op.get("type", "unknown")
            ts = op.get("timestamp", "—")
            details: list[str] = []
            if "dropped_count" in op:
                details.append(f"dropped {op['dropped_count']}")
            if "columns" in op:
                c = op["columns"]
                if isinstance(c, list):
                    details.append("cols: " + ", ".join(str(x) for x in c[:5]))
            if "details" in op and isinstance(op["details"], dict):
                details.append(json.dumps(op["details"])[:120])
            detail_str = ", ".join(details) if details else "—"
            parts.append(f"| {idx} | {otype} | {ts} | {detail_str} |")
        parts.append("")
    return "\n".join(parts)


@mcp.resource(
    "session://{session_id}/data-quality/{table_name}",
    mime_type="text/markdown",
    name="data_quality",
    description="Completeness, duplicate rows, simple IQR outlier counts (bounded).",
)
def get_data_quality_resource(session_id: str, table_name: str) -> str:
    df = get_table_data(session_id, table_name)
    if df is None:
        return f"**Error:** Table `{table_name}` not found in session `{session_id}`."

    n = len(df)
    lines = [f"# Data quality — `{table_name}`\n", f"- Rows: **{n}**\n", "## Completeness\n"]
    missing = df.isnull().sum()
    miss_cols = missing[missing > 0]
    if miss_cols.empty:
        lines.append("No missing values.\n")
    else:
        for col, cnt in miss_cols.items():
            pct = (cnt / n * 100) if n else 0
            lines.append(f"- `{col}`: {int(cnt)} missing ({pct:.2f}%)\n")

    lines.append("\n## Uniqueness\n")
    dup = int(df.duplicated().sum())
    lines.append(f"- Duplicate rows: **{dup}** ({(dup / n * 100) if n else 0:.2f}%)\n")

    lines.append("\n## Numeric outliers (IQR × 1.5)\n")
    num_cols = df.select_dtypes(include=["number"]).columns[:30]
    found = False
    for col in num_cols:
        col_data = df[col].dropna()
        if len(col_data) < 4:
            continue
        q1 = col_data.quantile(0.25)
        q3 = col_data.quantile(0.75)
        iqr = q3 - q1
        if iqr == 0:
            continue
        low, high = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        out = int(((col_data < low) | (col_data > high)).sum())
        if out > 0:
            found = True
            lines.append(f"- `{col}`: {out} rows outside IQR fence ({out / len(col_data) * 100:.2f}% of non-null)\n")
    if not found:
        lines.append("_No IQR outliers detected in sampled numeric columns (or insufficient data)._ \n")

    return "".join(lines)
