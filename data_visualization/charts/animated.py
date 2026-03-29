"""Animated scatter (time / sequence dimension)."""

from __future__ import annotations

import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

from ..core.chart_config import ChartConfig
from ..core.validators import column_or_none
from ..utils import create_error_figure


def generate_animated(df: pd.DataFrame, config: ChartConfig) -> go.Figure:
    x_col = column_or_none(df, config.x_col)
    y_col = column_or_none(df, config.y_col)
    anim = column_or_none(df, config.animation_col)
    color_col = config.color_col if config.color_col and config.color_col in df.columns else None
    if color_col == "None":
        color_col = None
    if not (x_col and y_col):
        return create_error_figure("Animated chart requires X and Y columns.")
    if not anim:
        return create_error_figure("Select an Animation column (More Options).")
    return px.scatter(
        df,
        x=x_col,
        y=y_col,
        animation_frame=anim,
        color=color_col,
        title=config.title_override or f"Animated: {y_col} vs {x_col}",
        color_discrete_sequence=config.color_palette,
    )
