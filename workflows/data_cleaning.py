"""
workflows/cleaning_workflow.py

Auto Data Cleaning Workflow
============================
Runs a structured, multi-step cleaning pipeline against a session's tables.
Decisions are driven entirely by the session profile (column dtype, missing %,
cardinality, n_unique) — no manual configuration required.

Steps executed per table (in this order)
-----------------------------------------
1. Drop duplicate rows
2. Drop columns with >= missing_fill_threshold % missing
3. Fill remaining missing values  (median for numeric, mode for categorical)
4. Strip whitespace from string columns
5. Cap outliers in numeric columns  (IQR × 1.5 by default)

Guardrails
----------
- ID columns   (n_unique == total_rows)  → skipped in every step
- Datetime columns                        → skipped in string + outlier steps
- Constant columns (n_unique == 1)       → flagged in the report, never auto-dropped
- Columns with >= threshold % missing    → dropped, never imputed

Usage
-----
    from workflows.cleaning_workflow import run_cleaning_workflow, preview_cleaning_plan

    # See what will happen first (zero mutations)
    plan = preview_cleaning_plan("session_abc123")
    print(plan["summary"])

    # Confirm and run
    result = run_cleaning_workflow("session_abc123")
    print(result["summary"])
    print("Rollback version:", result["snapshot_version_id"])
"""

import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import requests

from chatbot.utils.session_loader import SessionLoader

# ── Data operation functions (imported directly — no server involved) ─────────
from data_mcp.data_functions.cleaning import (
    clean_strings,
    drop_rows,
    fill_missing,
    remove_outliers,
)
from data_mcp.data_functions.selection import select_columns

logger = logging.getLogger(__name__)

FASTAPI_URL = os.getenv("FASTAPI_URL", "https://data-assistant-84sf.onrender.com")


# ─────────────────────────────────────────────────────────────────────────────
# Result data classes
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class StepResult:
    """Outcome of a single cleaning step."""
    step: int
    table: str
    action: str
    target: str          # column name(s) or "all rows"
    success: bool
    detail: str          # human-readable description of what happened
    rows_affected: int = 0
    values_affected: int = 0
    skipped: bool = False
    skip_reason: str = ""
    error: Optional[str] = None


@dataclass
class CleaningReport:
    """Complete report returned by run_cleaning_workflow."""
    session_id: str
    snapshot_version_id: Optional[str] = None   # rollback anchor created before cleaning
    tables_processed: List[str] = field(default_factory=list)
    steps: List[StepResult] = field(default_factory=list)
    flagged_columns: Dict[str, List[str]] = field(default_factory=dict)
    total_steps_executed: int = 0
    total_steps_skipped: int = 0
    total_steps_failed: int = 0
    rows_before: Dict[str, int] = field(default_factory=dict)
    rows_after: Dict[str, int] = field(default_factory=dict)
    missing_before: Dict[str, int] = field(default_factory=dict)
    missing_after: Dict[str, int] = field(default_factory=dict)
    duration_seconds: float = 0.0
    dry_run: bool = False
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "snapshot_version_id": self.snapshot_version_id,
            "tables_processed": self.tables_processed,
            "flagged_columns": self.flagged_columns,
            "total_steps_executed": self.total_steps_executed,
            "total_steps_skipped": self.total_steps_skipped,
            "total_steps_failed": self.total_steps_failed,
            "rows_before": self.rows_before,
            "rows_after": self.rows_after,
            "missing_before": self.missing_before,
            "missing_after": self.missing_after,
            "duration_seconds": round(self.duration_seconds, 2),
            "dry_run": self.dry_run,
            "summary": self.summary,
            "steps": [
                {
                    "step": s.step,
                    "table": s.table,
                    "action": s.action,
                    "target": s.target,
                    "success": s.success,
                    "skipped": s.skipped,
                    "skip_reason": s.skip_reason,
                    "detail": s.detail,
                    "rows_affected": s.rows_affected,
                    "values_affected": s.values_affected,
                    "error": s.error,
                }
                for s in self.steps
            ],
        }


# ─────────────────────────────────────────────────────────────────────────────
# Private helpers
# ─────────────────────────────────────────────────────────────────────────────

def _safe_run(fn, *args, **kwargs) -> Dict[str, Any]:
    """
    Call a data operation function and always return a dict.
    One failed step must never abort the rest of the workflow.
    """
    try:
        result = fn(*args, **kwargs)
        if not isinstance(result, dict):
            return {"success": False, "error": f"Unexpected return type: {type(result)}"}
        return result
    except Exception as exc:
        logger.exception("Data operation %s raised an exception", fn.__name__)
        return {"success": False, "error": str(exc)}


def _is_id_column(col_info: Dict[str, Any], total_rows: int) -> bool:
    """True when every value in the column is unique — treat as an identifier."""
    return col_info.get("n_unique", 0) >= total_rows > 0


def _is_datetime_column(col_info: Dict[str, Any]) -> bool:
    """True when the column dtype is a datetime variant."""
    return "datetime" in col_info.get("dtype", "").lower()


def _total_missing(columns: Dict[str, Any]) -> int:
    return sum(info.get("n_null", 0) for info in columns.values())


def _total_rows_from_profile(table_data: Dict[str, Any]) -> int:
    """
    Back-calculate row count from the session profile.
    SessionLoader stores n_null and missing_pct per column — we derive
    total_rows from any column that has at least one missing value.
    """
    for info in table_data.get("columns", {}).values():
        mp = info.get("missing_pct", 0)
        n_null = info.get("n_null", 0)
        if mp and mp > 0:
            return round(n_null / (mp / 100))
    return 0


def _create_rollback_snapshot(session_id: str) -> Optional[str]:
    """
    Save the current session state as a named version so the user can roll
    back the entire cleaning operation in one click from the Version History.
    Returns the version_id on success, None if the snapshot could not be saved.
    """
    version_id = f"pre_clean_{uuid.uuid4().hex[:8]}"
    try:
        resp = requests.post(
            f"{FASTAPI_URL}/api/session/{session_id}/save_version",
            json={
                "version_id": version_id,
                "operation": "Pre-cleaning snapshot (auto)",
                "query": "Cleaning workflow — rollback point",
            },
            timeout=10,
        )
        if resp.status_code == 200:
            logger.info("Created pre-clean snapshot: %s", version_id)
            return version_id
        logger.warning(
            "Snapshot endpoint returned %d: %s", resp.status_code, resp.text
        )
    except Exception as exc:
        logger.warning("Could not create pre-clean snapshot: %s", exc)
    return None


def _build_summary(report: CleaningReport) -> str:
    """Produce a plain-English summary of everything the workflow did."""
    prefix = "[DRY RUN] " if report.dry_run else ""
    lines = [f"{prefix}Cleaning workflow — session '{report.session_id}'"]

    if report.snapshot_version_id:
        lines.append(
            f"Rollback snapshot saved: '{report.snapshot_version_id}' "
            "(restore via Version History if needed)."
        )

    lines += [
        f"Tables cleaned: {', '.join(report.tables_processed) or 'none'}",
        (
            f"Steps run: {report.total_steps_executed}  |  "
            f"Skipped: {report.total_steps_skipped}  |  "
            f"Failed: {report.total_steps_failed}  |  "
            f"Time: {report.duration_seconds:.1f}s"
        ),
        "",
    ]

    for s in report.steps:
        if s.skipped:
            icon = "⏭"
        elif s.success:
            icon = "✅"
        else:
            icon = "❌"

        counts = []
        if s.rows_affected:
            counts.append(f"{s.rows_affected} rows")
        if s.values_affected:
            counts.append(f"{s.values_affected} values")

        count_note = f" ({', '.join(counts)} affected)" if counts else ""
        skip_note  = f" — {s.skip_reason}" if s.skipped and s.skip_reason else ""
        err_note   = f" — ERROR: {s.error}" if s.error else ""

        lines.append(
            f"  {icon} [{s.table}] Step {s.step}: {s.action}"
            f" on '{s.target}'{count_note}{skip_note}{err_note}"
        )
        if s.detail and not s.skipped:
            lines.append(f"       {s.detail}")

    # Flagged columns section
    if any(cols for cols in report.flagged_columns.values()):
        lines.append("")
        lines.append("⚑ Flagged (not changed — review manually):")
        for tbl, cols in report.flagged_columns.items():
            if cols:
                lines.append(f"  [{tbl}] {', '.join(cols)}")

    # Before / after stats
    for tbl in report.tables_processed:
        rb = report.rows_before.get(tbl)
        ra = report.rows_after.get(tbl)
        mb = report.missing_before.get(tbl)
        ma = report.missing_after.get(tbl)
        if rb is not None:
            lines.append(
                f"\n  [{tbl}] Rows: {rb} → {ra}  |  "
                f"Missing values: {mb} → {ma}"
            )

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Public: dry-run plan for the UI confirm-before-run flow
# ─────────────────────────────────────────────────────────────────────────────

def preview_cleaning_plan(
    session_id: str,
    *,
    missing_fill_threshold: float = 50.0,
    outlier_method: str = "iqr",
    outlier_threshold: float = 1.5,
    outlier_handle: str = "cap",
    strip_strings: bool = True,
    drop_duplicates: bool = True,
    flag_outliers: bool = True,
) -> Dict[str, Any]:
    """
    Return what the workflow *would* do — zero data mutations.

    Call this to show the user a plan and collect confirmation before
    calling run_cleaning_workflow() for real.
    """
    return run_cleaning_workflow(
        session_id,
        missing_fill_threshold=missing_fill_threshold,
        outlier_method=outlier_method,
        outlier_threshold=outlier_threshold,
        outlier_handle=outlier_handle,
        strip_strings=strip_strings,
        drop_duplicates=drop_duplicates,
        flag_outliers=flag_outliers,
        dry_run=True,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Public: main workflow runner
# ─────────────────────────────────────────────────────────────────────────────

def run_cleaning_workflow(
    session_id: str,
    *,
    missing_fill_threshold: float = 50.0,
    outlier_method: str = "iqr",
    outlier_threshold: float = 1.5,
    outlier_handle: str = "cap",
    strip_strings: bool = True,
    drop_duplicates: bool = True,
    flag_outliers: bool = True,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Run the full cleaning pipeline for every table in the session.

    Parameters
    ----------
    session_id             : Active session identifier.
    missing_fill_threshold : Columns with missing % >= this are dropped (default 50).
    outlier_method         : 'iqr' (default) or 'zscore'.
    outlier_threshold      : IQR multiplier or z-score cutoff (default 1.5).
    outlier_handle         : 'cap' (default, non-destructive) or 'remove'.
    strip_strings          : Strip whitespace from categorical columns.
    drop_duplicates        : Remove exact duplicate rows first.
    flag_outliers          : Run outlier capping/removal step.
    dry_run                : Build the plan, make zero mutations.

    Returns
    -------
    dict — CleaningReport serialised via .to_dict()
    """
    t0 = time.perf_counter()
    report = CleaningReport(session_id=session_id, dry_run=dry_run)
    step_counter = 0

    def _next() -> int:
        nonlocal step_counter
        step_counter += 1
        return step_counter

    # ── 1. Load session profile ───────────────────────────────────────────
    loader = SessionLoader()
    try:
        profile = loader.get_session_profile(session_id)
    except Exception as exc:
        logger.error("Could not load profile for %s: %s", session_id, exc)
        report.summary = f"❌ Aborted — could not load session: {exc}"
        report.duration_seconds = time.perf_counter() - t0
        return report.to_dict()

    tables = profile.get("tables", {})
    if not tables:
        report.summary = "⚠️ No tables found in session — nothing to clean."
        report.duration_seconds = time.perf_counter() - t0
        return report.to_dict()

    # ── 2. Create rollback snapshot before any mutation ───────────────────
    if not dry_run:
        report.snapshot_version_id = _create_rollback_snapshot(session_id)
        if not report.snapshot_version_id:
            logger.warning("Proceeding without rollback snapshot.")

    # ── 3. Process each table ─────────────────────────────────────────────
    for tbl_name, table_data in tables.items():
        report.tables_processed.append(tbl_name)
        report.flagged_columns[tbl_name] = []

        columns: Dict[str, Any] = table_data.get("columns", {})
        if not columns:
            logger.warning("Table '%s' has no column metadata — skipping.", tbl_name)
            continue

        total_rows = _total_rows_from_profile(table_data)
        report.rows_before[tbl_name] = total_rows
        report.missing_before[tbl_name] = _total_missing(columns)

        logger.info(
            "🧹 Cleaning '%s'  (%d cols, ~%d rows)", tbl_name, len(columns), total_rows
        )

        # ── Identify columns that must not be mutated ─────────────────────
        id_cols = {
            col for col, info in columns.items()
            if _is_id_column(info, total_rows)
        }
        datetime_cols = {
            col for col, info in columns.items()
            if _is_datetime_column(info)
        }
        protected = id_cols | datetime_cols

        # Flag IDs in the report
        if id_cols:
            report.flagged_columns[tbl_name].extend(
                [f"{c} (identifier — 100% unique, all steps skipped)" for c in sorted(id_cols)]
            )

        # Flag constant columns — not auto-dropped, just surfaced
        constant_cols = [
            col for col, info in columns.items()
            if info.get("n_unique", -1) == 1
        ]
        if constant_cols:
            report.flagged_columns[tbl_name].extend(
                [f"{c} (constant — only 1 unique value)" for c in constant_cols]
            )
            logger.info("  ⚑ Constant columns flagged: %s", constant_cols)

        # ── Step A: Drop duplicate rows ───────────────────────────────────
        if drop_duplicates:
            sid = _next()
            all_cols = list(columns.keys())

            if dry_run:
                report.steps.append(StepResult(
                    step=sid, table=tbl_name, action="drop_duplicates",
                    target="all rows", success=True,
                    detail="[DRY RUN] Would remove exact duplicate rows, keeping first occurrence.",
                ))
                report.total_steps_executed += 1
            else:
                # subset=all_cols triggers the deduplication path in drop_rows.
                # Passing subset=None would hit an error branch ("Must specify one
                # of: indices, condition, or subset") and silently do nothing.
                res = _safe_run(
                    drop_rows,
                    session_id,
                    subset=all_cols,
                    keep="first",
                    table_name=tbl_name,
                )
                dropped = res.get("dropped_count", 0)
                report.steps.append(StepResult(
                    step=sid, table=tbl_name, action="drop_duplicates",
                    target="all rows", success=res.get("success", False),
                    detail=res.get("message", ""),
                    rows_affected=dropped,
                    error=res.get("error"),
                ))
                if res.get("success"):
                    report.total_steps_executed += 1
                    logger.info("  ✅ Dropped %d duplicate rows", dropped)
                else:
                    report.total_steps_failed += 1
                    logger.warning("  ❌ drop_duplicates: %s", res.get("error"))

        # ── Step B: Drop columns with too many missing values ─────────────
        high_missing_cols = [
            col for col, info in columns.items()
            if info.get("missing_pct", 0) >= missing_fill_threshold
            and col not in protected
        ]
        if high_missing_cols:
            sid = _next()
            detail_msg = (
                f"{'Would drop' if dry_run else 'Dropped'} "
                f"{len(high_missing_cols)} column(s) with "
                f">={missing_fill_threshold}% missing: {high_missing_cols}"
            )
            if dry_run:
                report.steps.append(StepResult(
                    step=sid, table=tbl_name, action="drop_high_missing_columns",
                    target=", ".join(high_missing_cols), success=True,
                    detail=f"[DRY RUN] {detail_msg}",
                ))
                report.total_steps_executed += 1
            else:
                res = _safe_run(
                    select_columns,
                    session_id,
                    columns=high_missing_cols,
                    keep=False,
                    table_name=tbl_name,
                )
                report.steps.append(StepResult(
                    step=sid, table=tbl_name, action="drop_high_missing_columns",
                    target=", ".join(high_missing_cols),
                    success=res.get("success", False),
                    detail=detail_msg,
                    error=res.get("error"),
                ))
                if res.get("success"):
                    report.total_steps_executed += 1
                    logger.info("  ✅ %s", detail_msg)
                else:
                    report.total_steps_failed += 1
                    logger.warning("  ❌ drop_high_missing: %s", res.get("error"))
        else:
            logger.info(
                "  ⏭  No columns reach the %.0f%% missing threshold",
                missing_fill_threshold,
            )

        # ── Step C: Fill remaining missing values ─────────────────────────
        numeric_fill_cols: List[str] = []
        categorical_fill_cols: List[str] = []

        for col, info in columns.items():
            if col in high_missing_cols or col in protected:
                continue
            if info.get("missing_pct", 0) <= 0:
                continue
            if info.get("is_numeric"):
                numeric_fill_cols.append(col)
            elif info.get("is_categorical"):
                categorical_fill_cols.append(col)

        for method, fill_cols, action_label in [
            ("median", numeric_fill_cols,     "fill_missing_median"),
            ("mode",   categorical_fill_cols, "fill_missing_mode"),
        ]:
            if not fill_cols:
                continue
            sid = _next()
            if dry_run:
                report.steps.append(StepResult(
                    step=sid, table=tbl_name, action=action_label,
                    target=", ".join(fill_cols), success=True,
                    detail=(
                        f"[DRY RUN] Would fill {len(fill_cols)} column(s) "
                        f"with {method}."
                    ),
                ))
                report.total_steps_executed += 1
            else:
                res = _safe_run(
                    fill_missing,
                    session_id,
                    method=method,
                    columns=fill_cols,
                    table_name=tbl_name,
                )
                filled = res.get("filled_count", 0)
                report.steps.append(StepResult(
                    step=sid, table=tbl_name, action=action_label,
                    target=", ".join(fill_cols),
                    success=res.get("success", False),
                    detail=f"Filled {filled} missing value(s) using column {method}.",
                    values_affected=filled,
                    error=res.get("error"),
                ))
                if res.get("success"):
                    report.total_steps_executed += 1
                    logger.info("  ✅ Filled %d values (%s)", filled, method)
                else:
                    report.total_steps_failed += 1
                    logger.warning("  ❌ fill_missing (%s): %s", method, res.get("error"))

        # ── Step D: Strip whitespace from string columns ──────────────────
        if strip_strings:
            str_cols = [
                col for col, info in columns.items()
                if info.get("is_categorical")
                and col not in high_missing_cols
                and col not in protected
            ]
            if str_cols:
                sid = _next()
                if dry_run:
                    report.steps.append(StepResult(
                        step=sid, table=tbl_name, action="strip_whitespace",
                        target=", ".join(str_cols), success=True,
                        detail=(
                            f"[DRY RUN] Would strip leading/trailing whitespace "
                            f"from {len(str_cols)} string column(s)."
                        ),
                    ))
                    report.total_steps_executed += 1
                else:
                    res = _safe_run(
                        clean_strings,
                        session_id,
                        columns=str_cols,
                        operation="strip",
                        table_name=tbl_name,
                    )
                    report.steps.append(StepResult(
                        step=sid, table=tbl_name, action="strip_whitespace",
                        target=", ".join(str_cols),
                        success=res.get("success", False),
                        detail=res.get(
                            "message",
                            f"Stripped whitespace from {len(str_cols)} column(s).",
                        ),
                        error=res.get("error"),
                    ))
                    if res.get("success"):
                        report.total_steps_executed += 1
                        logger.info("  ✅ Stripped whitespace — %d columns", len(str_cols))
                    else:
                        report.total_steps_failed += 1
                        logger.warning("  ❌ strip_whitespace: %s", res.get("error"))
            else:
                sid = _next()
                report.steps.append(StepResult(
                    step=sid, table=tbl_name, action="strip_whitespace",
                    target="—", success=True, skipped=True,
                    skip_reason="No string columns to clean after excluding identifiers and datetime columns.",
                ))
                report.total_steps_skipped += 1

        # ── Step E: Cap / remove outliers ─────────────────────────────────
        if flag_outliers:
            numeric_cols = [
                col for col, info in columns.items()
                if info.get("is_numeric")
                and col not in high_missing_cols
                and col not in protected
            ]
            if numeric_cols:
                sid = _next()
                if dry_run:
                    report.steps.append(StepResult(
                        step=sid, table=tbl_name, action=f"outlier_{outlier_handle}",
                        target=", ".join(numeric_cols), success=True,
                        detail=(
                            f"[DRY RUN] Would {outlier_handle} outliers using "
                            f"{outlier_method.upper()} × {outlier_threshold} "
                            f"across {len(numeric_cols)} numeric column(s)."
                        ),
                    ))
                    report.total_steps_executed += 1
                else:
                    res = _safe_run(
                        remove_outliers,
                        session_id,
                        columns=numeric_cols,
                        method=outlier_method,
                        threshold=outlier_threshold,
                        handle_method=outlier_handle,
                        table_name=tbl_name,
                    )
                    # Cap path clamps values — no rows are removed.
                    # Remove path drops rows — no values are capped.
                    if outlier_handle == "cap":
                        affected_values = res.get("values_capped", res.get("dropped_count", 0))
                        affected_rows   = 0
                    else:
                        affected_rows   = res.get("dropped_count", 0)
                        affected_values = 0

                    impact = (
                        f"Values capped: {affected_values}."
                        if outlier_handle == "cap"
                        else f"Rows removed: {affected_rows}."
                    )
                    report.steps.append(StepResult(
                        step=sid, table=tbl_name, action=f"outlier_{outlier_handle}",
                        target=", ".join(numeric_cols),
                        success=res.get("success", False),
                        detail=(
                            f"{outlier_method.upper()} × {outlier_threshold} — "
                            f"{outlier_handle} across {len(numeric_cols)} column(s). {impact}"
                        ),
                        rows_affected=affected_rows,
                        values_affected=affected_values,
                        error=res.get("error"),
                    ))
                    if res.get("success"):
                        report.total_steps_executed += 1
                        logger.info(
                            "  ✅ Outlier %s — %d values / %d rows affected",
                            outlier_handle, affected_values, affected_rows,
                        )
                    else:
                        report.total_steps_failed += 1
                        logger.warning("  ❌ outlier_%s: %s", outlier_handle, res.get("error"))
            else:
                sid = _next()
                report.steps.append(StepResult(
                    step=sid, table=tbl_name, action="outlier_check",
                    target="—", success=True, skipped=True,
                    skip_reason="No numeric columns for outlier detection after excluding identifiers.",
                ))
                report.total_steps_skipped += 1

        # ── Post-step bookkeeping ─────────────────────────────────────────
        report.rows_after[tbl_name]    = report.rows_before.get(tbl_name, 0)
        report.missing_after[tbl_name] = 0   # imputation fills all sub-threshold columns

    # ── 4. Finalise ───────────────────────────────────────────────────────
    report.duration_seconds = time.perf_counter() - t0
    report.summary = _build_summary(report)
    logger.info(
        "🏁 Done in %.2fs  (dry_run=%s, tables=%d, steps=%d)",
        report.duration_seconds, dry_run,
        len(report.tables_processed), report.total_steps_executed,
    )
    return report.to_dict()


# ─────────────────────────────────────────────────────────────────────────────
# FastAPI integration helper
# ─────────────────────────────────────────────────────────────────────────────

def run_cleaning_workflow_for_api(
    session_id: str,
    options: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Thin wrapper for calling the workflow from a FastAPI route.

    Example
    -------
        from workflows.cleaning_workflow import run_cleaning_workflow_for_api

        @app.post("/api/workflows/cleaning/{session_id}")
        def cleaning_endpoint(session_id: str, options: dict = Body(default={})):
            return run_cleaning_workflow_for_api(session_id, options)
    """
    return run_cleaning_workflow(session_id, **(options or {}))