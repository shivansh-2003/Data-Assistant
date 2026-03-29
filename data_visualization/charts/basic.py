"""Bar, line, scatter, area charts."""

from __future__ import annotations

import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

from ..core.chart_config import ChartConfig
from ..core.validators import column_or_none
from ..utils import create_error_figure


def generate_bar(df: pd.DataFrame, config: ChartConfig) -> go.Figure:
    x_col = column_or_none(df, config.x_col)
    y_col = column_or_none(df, config.y_col)
    color_col = config.color_col if config.color_col and config.color_col in df.columns else None
    if color_col == "None":
        color_col = None
    palette = config.color_palette

    if y_col and x_col:
        return px.bar(
            df,
            x=x_col,
            y=y_col,
            color=color_col,
            title=config.title_override or f"Bar Chart: {y_col} by {x_col}",
            color_discrete_sequence=palette,
        )
    if x_col:
        value_counts = df[x_col].value_counts().head(20)
        return px.bar(
            x=value_counts.index,
            y=value_counts.values,
            title=config.title_override or f"Bar Chart: Count by {x_col}",
            color_discrete_sequence=palette,
        )
    return create_error_figure(f"Bar chart requires at least X column. Available columns: {list(df.columns)}")


def generate_line(df: pd.DataFrame, config: ChartConfig) -> go.Figure:
    x_col = column_or_none(df, config.x_col)
    y_col = column_or_none(df, config.y_col)
    color_col = config.color_col if config.color_col and config.color_col in df.columns else None
    if color_col == "None":
        color_col = None
    if y_col and x_col:
        return px.line(
            df,
            x=x_col,
            y=y_col,
            color=color_col,
            title=config.title_override or f"Line Chart: {y_col} over {x_col}",
            color_discrete_sequence=config.color_palette,
        )
    return create_error_figure("Line chart requires both X and Y columns")


def generate_scatter(df: pd.DataFrame, config: ChartConfig) -> go.Figure:
    x_col = column_or_none(df, config.x_col)
    y_col = column_or_none(df, config.y_col)
    color_col = config.color_col if config.color_col and config.color_col in df.columns else None
    if color_col == "None":
        color_col = None
    if not (y_col and x_col):
        return create_error_figure(
            f"Scatter chart requires both X and Y columns. Available columns: {list(df.columns)}"
        )
    kw = dict(
        x=x_col,
        y=y_col,
        color=color_col,
        title=config.title_override or f"Scatter: {y_col} vs {x_col}",
        color_discrete_sequence=config.color_palette,
    )
    if config.show_trendline:
        kw["trendline"] = "ols"
    return px.scatter(df, **kw)


def generate_area(df: pd.DataFrame, config: ChartConfig) -> go.Figure:
    x_col = column_or_none(df, config.x_col)
    y_col = column_or_none(df, config.y_col)
    color_col = config.color_col if config.color_col and config.color_col in df.columns else None
    if color_col == "None":
        color_col = None
    if y_col and x_col:
        return px.area(
            df,
            x=x_col,
            y=y_col,
            color=color_col,
            title=config.title_override or f"Area Chart: {y_col} over {x_col}",
            color_discrete_sequence=config.color_palette,
        )
    return create_error_figure("Area chart requires both X and Y columns")
