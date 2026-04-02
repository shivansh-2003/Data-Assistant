"""
Parameterized MCP prompts for guided data workflows (registered on shared `mcp`).
"""

from __future__ import annotations

try:
    from data_mcp.data import mcp
except ImportError:
    from data import mcp


@mcp.prompt(
    name="data_cleaning_workflow",
    description="Step-by-step data cleaning checklist for a session table.",
    tags={"workflow", "cleaning"},
)
def data_cleaning_workflow(session_id: str, table_name: str = "current") -> str:
    return f"""Perform comprehensive data cleaning on session `{session_id}`, table `{table_name}`.

**Phase 1: Assessment**
1. Read resource `session://{session_id}/summary` or call `get_table_summary`.
2. Use `detect_missing_values` for gaps.
3. Identify duplicate rows where relevant.
4. Note numeric columns for outlier review.

**Phase 2: Missing values** — choose strategies per column (mean/median/mode/ffill/drop).

**Phase 3: Duplicates** — `drop_rows_from_table` with subset and keep strategy.

**Phase 4: Quality** — string cleaning, outliers (`remove_outliers_from_table`), replacements.

**Phase 5: Summary** — before/after, operations list, next steps.

Explain decisions after each phase."""


@mcp.prompt(
    name="exploratory_analysis",
    description="EDA workflow focused on one target column.",
    tags={"workflow", "eda"},
)
def exploratory_analysis(session_id: str, target_column: str, table_name: str = "current") -> str:
    return f"""Exploratory analysis for column `{target_column}` in session `{session_id}`, table `{table_name}`.

1. Summary stats: `describe_table_stats` / aggregates for `{target_column}`.
2. Missing and distribution for `{target_column}`.
3. If numeric: groupby categoricals, correlations; if categorical: value counts and crosstabs.
4. Data quality anomalies.
5. Insights, transforms, viz ideas, next steps.

Support claims with tool results."""


@mcp.prompt(
    name="feature_engineering_workflow",
    description="Feature engineering checklist toward a target column.",
    tags={"workflow", "features"},
)
def feature_engineering_workflow(
    session_id: str, target_column: str, table_name: str = "current"
) -> str:
    return f"""Engineer features to predict `{target_column}` in session `{session_id}`, table `{table_name}`.

1. Inventory columns (numeric, categorical, datetime, text).
2. Datetime: `create_date_features_for_column` / date tools.
3. Numeric: binning, scaling, interactions.
4. Categorical: one-hot / high-cardinality strategy.
5. Domain ratios, flags, aggregations.
6. Rank features; suggest keep/drop.

Explain each created feature."""


@mcp.prompt(
    name="data_quality_report",
    description="Structured data quality report request.",
    tags={"workflow", "quality"},
)
def data_quality_report(session_id: str, table_name: str = "current") -> str:
    return f"""Generate a data quality report for session `{session_id}`, table `{table_name}`.

Use `session://{session_id}/data-quality/{table_name}` plus tools as needed.

Cover: completeness, validity (types/ranges), uniqueness/keys, outliers, consistency between columns, prioritized action plan with impact."""


@mcp.prompt(
    name="prepare_for_analysis",
    description="Prepare data for regression, classification, clustering, etc.",
    tags={"workflow", "modeling"},
)
def prepare_for_analysis(
    session_id: str, analysis_type: str, table_name: str = "current"
) -> str:
    return f"""Prepare session `{session_id}`, table `{table_name}` for **{analysis_type}** analysis.

1. Requirements and pitfalls for {analysis_type}.
2. Assess missing values, types, sample size.
3. Clean: missing, outliers, duplicates, strings.
4. Encode categoricals, scale numerics, derived features as needed.
5. Validate ready state (no leaking NaNs in key columns, variance checks).
6. Suggest train/test split and export/next steps.

Be precise and tool-driven."""


@mcp.prompt(
    name="merge_datasets_workflow",
    description="Join two tables with validation steps.",
    tags={"workflow", "multi-table"},
)
def merge_datasets_workflow(session_id: str, left_table: str, right_table: str) -> str:
    return f"""Merge `{left_table}` and `{right_table}` in session `{session_id}`.

1. Summarize both tables; list candidate keys.
2. Choose join type and keys; justify.
3. Validate key duplicates and dtypes; estimate row counts.
4. Run `merge_data_tables` (or index merge if appropriate).
5. Post-check row counts, nulls from join.
6. Cleanup columns and suggest next steps.

Walk through carefully with explanations."""
