"""Histogram, box, violin."""

from __future__ import annotations

import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

from ..core.chart_config import ChartConfig
from ..core.validators import column_or_none
from ..utils import create_error_figure


def generate_histogram(df: pd.DataFrame, config: ChartConfig) -> go.Figure:
    x_col = column_or_none(df, config.x_col)
    color_col = config.color_col if config.color_col and config.color_col in df.columns else None
    if color_col == "None":
        color_col = None
    if x_col:
        return px.histogram(
            df,
            x=x_col,
            color=color_col,
            title=config.title_override or f"Histogram: Distribution of {x_col}",
            color_discrete_sequence=config.color_palette,
        )
    return create_error_figure(f"Histogram requires X column. Available columns: {list(df.columns)}")


def generate_box(df: pd.DataFrame, config: ChartConfig) -> go.Figure:
    x_col = column_or_none(df, config.x_col)
    y_col = column_or_none(df, config.y_col)
    color_col = config.color_col if config.color_col and config.color_col in df.columns else None
    if color_col == "None":
        color_col = None
    if y_col:
        return px.box(
            df,
            x=x_col,
            y=y_col,
            color=color_col,
            title=config.title_override
            or (f"Box Plot: {y_col}" + (f" by {x_col}" if x_col else "")),
            color_discrete_sequence=config.color_palette,
        )
    return create_error_figure("Box plot requires Y column")


def generate_violin(df: pd.DataFrame, config: ChartConfig) -> go.Figure:
    x_col = column_or_none(df, config.x_col)
    y_col = column_or_none(df, config.y_col)
    color_col = config.color_col if config.color_col and config.color_col in df.columns else None
    if color_col == "None":
        color_col = None
    if not y_col:
        return create_error_figure("Violin plot requires Y column")
    return px.violin(
        df,
        x=x_col,
        y=y_col,
        color=color_col,
        box=True,
        points="outliers",
        title=config.title_override or f"Violin: {y_col}" + (f" by {x_col}" if x_col else ""),
        color_discrete_sequence=config.color_palette,
    )
