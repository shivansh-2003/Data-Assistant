"""Column presence, dtype helpers, and chart configuration validation."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import pandas as pd


def column_or_none(df: pd.DataFrame, col: Optional[str]) -> Optional[str]:
    if not col or col == "None" or col not in df.columns:
        return None
    return col


def is_datetime_series(s: pd.Series) -> bool:
    return pd.api.types.is_datetime64_any_dtype(s)


def unique_count(s: pd.Series) -> int:
    return int(s.nunique(dropna=True))


def get_validation_result(
    chart_mode: str,
    chart_type: str,
    x_col: str,
    y_col: str,
    heatmap_columns: Optional[List[str]] = None,
    composition_params: Optional[Dict[str, Any]] = None,
) -> Tuple[bool, Optional[str]]:
    """
    Determine if the current chart configuration can be rendered and optional message.

    Returns:
        (can_render, validation_message). validation_message is set when can_render is False.
    """
    composition_params = composition_params or {}

    if chart_mode == "combo":
        if (
            x_col != "None"
            and y_col != "None"
            and composition_params.get("y2_col")
            and composition_params.get("y2_col") != "None"
        ):
            return (True, None)
        return (False, "⚠️ Combo chart requires X, Y1, and Y2 columns.")

    if chart_type in ["line", "scatter", "area"]:
        if x_col != "None" and y_col != "None":
            return (True, None)
        return (
            False,
            "⚠️ This chart type requires both X and Y columns. Please select both.",
        )
    if chart_type == "box":
        if y_col != "None":
            return (True, None)
        return (False, "⚠️ Box plot requires Y column. Please select a Y-axis column.")
    if chart_type == "histogram":
        if x_col != "None":
            return (True, None)
        return (False, "⚠️ Histogram requires X column. Please select an X-axis column.")
    if chart_type == "pie":
        if x_col != "None" or y_col != "None":
            return (True, None)
        return (
            False,
            "⚠️ Pie chart requires at least one column. Please select X or Y column.",
        )
    if chart_type == "heatmap":
        if heatmap_columns and len(heatmap_columns) >= 2:
            return (True, None)
        if x_col != "None" and y_col != "None":
            return (True, None)
        return (
            False,
            "⚠️ Heatmap requires at least 2 columns. Use the multi-select above or select X and Y columns.",
        )
    if x_col != "None" or y_col != "None":
        return (True, None)
    return (False, "⚠️ Please select at least one column (X or Y).")
