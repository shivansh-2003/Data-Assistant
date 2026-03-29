"""Choropleth and scatter_geo."""

from __future__ import annotations

import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

from ..core.chart_config import ChartConfig
from ..core.validators import column_or_none
from ..utils import create_error_figure


def generate_choropleth(df: pd.DataFrame, config: ChartConfig) -> go.Figure:
    loc = column_or_none(df, config.geo_col) or column_or_none(df, config.x_col)
    val = column_or_none(df, config.y_col)
    if not loc:
        return create_error_figure("Choropleth requires a location column (Geo / X).")
    if not val:
        return create_error_figure("Choropleth requires a numeric values column (Y).")
    return px.choropleth(
        df,
        locations=loc,
        color=val,
        title=config.title_override or f"Choropleth: {val}",
        scope=config.geo_scope or "world",
    )


def generate_scatter_geo(df: pd.DataFrame, config: ChartConfig) -> go.Figure:
    lat = column_or_none(df, config.lat_col)
    lon = column_or_none(df, config.lon_col)
    if not lat or not lon:
        return create_error_figure("Scatter geo requires Latitude and Longitude columns (More Options).")
    color = config.color_col if config.color_col and config.color_col in df.columns else None
    if color == "None":
        color = None
    return px.scatter_geo(
        df,
        lat=lat,
        lon=lon,
        color=color,
        title=config.title_override or "Scatter Geo",
    )
