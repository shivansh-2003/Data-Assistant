"""
Thin dispatcher: ChartConfig + DataFrame → themed Plotly figure.
"""

from __future__ import annotations

from typing import List, Optional

import pandas as pd
import plotly.graph_objects as go

from ..charts import CHART_REGISTRY
from ..charts.combo import generate_combo_chart
from ..interactivity.cross_filter import apply_cross_filter
from ..theme.plotly_templates import apply_theme
from ..utils import create_error_figure
from .aggregator import apply_aggregation
from .chart_config import ChartConfig
from .sampling import maybe_sample


def generate_from_config(df: pd.DataFrame, config: ChartConfig) -> go.Figure:
    """Full pipeline: cross-filter → aggregate → sample → chart → theme."""
    if df.empty:
        return create_error_figure("No data available—check your manipulations!")

    cfg = config.normalized()

    if cfg.chart_mode == "combo":
        df_c = apply_cross_filter(df)
        x = cfg.x_col
        y1 = cfg.y_col
        y2 = cfg.y2_col
        if not (x and y1 and y2):
            return create_error_figure("Combo chart requires X, Y1, and Y2 columns.")
        fig = generate_combo_chart(
            df_c,
            x,
            y1,
            y2,
            cfg.chart1_type,
            cfg.chart2_type,
            cfg.color_col if cfg.color_col and cfg.color_col != "None" else None,
        )
        return apply_theme(fig)

    df_work = apply_cross_filter(df)
    df_work = apply_aggregation(df_work, cfg)
    df_work, _meta = maybe_sample(df_work, cfg.chart_type)

    fn = CHART_REGISTRY.get(cfg.chart_type)
    if not fn:
        return create_error_figure(f"Chart type not supported: {cfg.chart_type}")

    try:
        fig = fn(df_work, cfg)
        return apply_theme(fig)
    except Exception as e:
        return create_error_figure(f"Error generating chart: {str(e)}")


def generate_chart(
    df: pd.DataFrame,
    chart_type: str,
    x_col: Optional[str],
    y_col: Optional[str],
    agg_func: str = "none",
    color_col: Optional[str] = None,
    heatmap_columns: Optional[list] = None,
    title_override: Optional[str] = None,
    color_palette: Optional[List[str]] = None,
    **kwargs,
) -> go.Figure:
    """
    Backward-compatible API matching the original visualization.generate_chart signature.
    Extra kwargs are passed into ChartConfig (e.g. path_cols, sankey_source).
    """
    c = ChartConfig(
        chart_type=chart_type,
        x_col=x_col,
        y_col=y_col,
        agg_func=agg_func,
        color_col=color_col,
        heatmap_columns=heatmap_columns,
        title_override=title_override,
        color_palette=color_palette,
        path_cols=kwargs.get("path_cols"),
        sankey_source=kwargs.get("sankey_source"),
        sankey_target=kwargs.get("sankey_target"),
        sankey_value=kwargs.get("sankey_value"),
        geo_col=kwargs.get("geo_col"),
        geo_scope=kwargs.get("geo_scope", "world"),
        lat_col=kwargs.get("lat_col"),
        lon_col=kwargs.get("lon_col"),
        animation_col=kwargs.get("animation_col"),
        show_trendline=bool(kwargs.get("show_trendline", False)),
    )
    return generate_from_config(df, c)
