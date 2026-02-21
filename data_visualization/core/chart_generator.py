"""
Thin dispatcher for chart generation. No Streamlit UI; delegates to charts.* and applies theme.
"""

import pandas as pd
import plotly.graph_objects as go
from typing import Optional

from ..utils import create_error_figure, apply_theme
from ..charts.basic import generate_basic_chart
from ..charts.heatmap import generate_heatmap


def generate_chart(
    df: pd.DataFrame,
    chart_type: str,
    x_col: Optional[str],
    y_col: Optional[str],
    agg_func: str = 'none',
    color_col: Optional[str] = None,
    heatmap_columns: Optional[list] = None,
    title_override: Optional[str] = None,
    color_palette: Optional[list] = None
) -> go.Figure:
    """
    Generate Plotly figure based on user selections.
    Supports: bar, line, scatter, area, box, histogram, pie, heatmap.
    """
    if df.empty:
        return create_error_figure("No data available—check your manipulations!")

    if agg_func != 'none' and y_col and y_col in df.columns:
        if chart_type in ['bar', 'line', 'area']:
            if x_col and x_col in df.columns:
                df_agg = df.groupby(x_col)[y_col].agg(agg_func).reset_index()
            else:
                df_agg = df
        else:
            df_agg = df
    else:
        df_agg = df

    if color_col and color_col != 'None' and color_col not in df_agg.columns:
        color_col = None
    if x_col and x_col not in df_agg.columns:
        x_col = None
    if y_col and y_col not in df_agg.columns:
        y_col = None

    try:
        if chart_type == 'heatmap':
            fig = generate_heatmap(df_agg, heatmap_columns, x_col, y_col)
        else:
            fig = generate_basic_chart(
                df_agg,
                chart_type,
                x_col,
                y_col,
                color_col,
                title_override,
                color_palette,
            )
        fig = apply_theme(fig)
        return fig
    except Exception as e:
        return create_error_figure(f"Error generating chart: {str(e)}")
