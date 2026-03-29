"""Pie, sunburst, treemap, funnel."""

from __future__ import annotations

import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

from ..core.chart_config import ChartConfig
from ..core.validators import column_or_none
from ..utils import create_error_figure


def generate_pie(df: pd.DataFrame, config: ChartConfig) -> go.Figure:
    x_col = column_or_none(df, config.x_col)
    y_col = column_or_none(df, config.y_col)
    palette = config.color_palette

    if y_col:
        df_pie = df.groupby(y_col).size().reset_index(name="count")
        return px.pie(
            df_pie,
            values="count",
            names=y_col,
            title=config.title_override or f"Pie: Distribution of {y_col}",
            color_discrete_sequence=palette,
        )
    if x_col:
        value_counts = df[x_col].value_counts()
        return px.pie(
            values=value_counts.values,
            names=value_counts.index,
            title=config.title_override or f"Pie: Distribution of {x_col}",
            color_discrete_sequence=palette,
        )
    return create_error_figure("Pie chart requires at least one column")


def generate_sunburst(df: pd.DataFrame, config: ChartConfig) -> go.Figure:
    path_cols = config.path_cols or []
    path_cols = [c for c in path_cols if c and c in df.columns]
    value_col = column_or_none(df, config.y_col)
    if len(path_cols) < 2:
        return create_error_figure("Sunburst requires at least 2 path columns (set Path columns in More Options).")
    kwargs = dict(path=path_cols, title=config.title_override or f"Sunburst: {' → '.join(path_cols)}")
    if value_col:
        kwargs["values"] = value_col
    return px.sunburst(df, **kwargs)


def generate_treemap(df: pd.DataFrame, config: ChartConfig) -> go.Figure:
    path_cols = config.path_cols or []
    path_cols = [c for c in path_cols if c and c in df.columns]
    value_col = column_or_none(df, config.y_col)
    if len(path_cols) < 1:
        return create_error_figure("Treemap requires at least one path column.")
    kwargs = dict(path=path_cols, title=config.title_override or f"Treemap: {' → '.join(path_cols)}")
    if value_col:
        kwargs["values"] = value_col
    return px.treemap(df, **kwargs)


def generate_funnel(df: pd.DataFrame, config: ChartConfig) -> go.Figure:
    x_col = column_or_none(df, config.x_col)
    y_col = column_or_none(df, config.y_col)
    if not x_col:
        return create_error_figure("Funnel requires X (stage) column.")
    if y_col:
        stage = df.groupby(x_col, dropna=False)[y_col].sum().reset_index()
        # Plotly Express: x = numeric amount, y = stage label
        return px.funnel(
            stage,
            x=y_col,
            y=x_col,
            title=config.title_override or f"Funnel: {y_col} by {x_col}",
        )
    counts = df[x_col].value_counts().reset_index()
    counts.columns = [x_col, "count"]
    return px.funnel(
        counts,
        x="count",
        y=x_col,
        title=config.title_override or f"Funnel: count by {x_col}",
    )
