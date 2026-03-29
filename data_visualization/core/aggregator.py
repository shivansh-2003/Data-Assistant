"""Group-by aggregation for bar/line/area charts."""

from __future__ import annotations

import pandas as pd

from .chart_config import ChartConfig


def apply_aggregation(df: pd.DataFrame, config: ChartConfig) -> pd.DataFrame:
    """Mirror legacy generate_chart aggregation rules."""
    if df.empty:
        return df
    agg_func = config.agg_func or "none"
    y_col = config.y_col
    x_col = config.x_col
    chart_type = config.chart_type

    if agg_func != "none" and y_col and y_col in df.columns:
        if chart_type in ("bar", "line", "area"):
            if x_col and x_col in df.columns:
                return df.groupby(x_col)[y_col].agg(agg_func).reset_index()
            return df
        return df
    return df
