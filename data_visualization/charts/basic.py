"""
Basic chart types: bar, line, scatter, area, box, histogram, pie.
"""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from typing import Optional

from ..utils import create_error_figure


def generate_basic_chart(
    df_agg: pd.DataFrame,
    chart_type: str,
    x_col: Optional[str],
    y_col: Optional[str],
    color_col: Optional[str],
    title_override: Optional[str],
    color_palette: Optional[list],
) -> go.Figure:
    """
    Generate a basic Plotly chart (bar, line, scatter, area, box, histogram, pie).
    Caller is responsible for aggregation and apply_theme.
    """
    # Normalize 'None' string from UI
    color_opt = color_col if color_col and color_col != 'None' else None

    if chart_type == 'bar':
        if y_col and y_col in df_agg.columns and x_col and x_col in df_agg.columns:
            fig = px.bar(
                df_agg,
                x=x_col,
                y=y_col,
                color=color_opt,
                title=title_override or f"Bar Chart: {y_col} by {x_col}",
                color_discrete_sequence=color_palette
            )
        elif x_col and x_col in df_agg.columns:
            value_counts = df_agg[x_col].value_counts().head(20)
            fig = px.bar(
                x=value_counts.index,
                y=value_counts.values,
                title=title_override or f"Bar Chart: Count by {x_col}",
                color_discrete_sequence=color_palette
            )
        else:
            fig = create_error_figure(
                f"Bar chart requires at least X column. Available columns: {list(df_agg.columns)}"
            )

    elif chart_type == 'line':
        if y_col and y_col in df_agg.columns and x_col and x_col in df_agg.columns:
            fig = px.line(
                df_agg,
                x=x_col,
                y=y_col,
                color=color_opt,
                title=title_override or f"Line Chart: {y_col} over {x_col}",
                color_discrete_sequence=color_palette
            )
        else:
            fig = create_error_figure("Line chart requires both X and Y columns")

    elif chart_type == 'scatter':
        if y_col and y_col in df_agg.columns and x_col and x_col in df_agg.columns:
            fig = px.scatter(
                df_agg,
                x=x_col,
                y=y_col,
                color=color_opt,
                title=title_override or f"Scatter: {y_col} vs {x_col}",
                color_discrete_sequence=color_palette
            )
        else:
            fig = create_error_figure(
                f"Scatter chart requires both X and Y columns. Available columns: {list(df_agg.columns)}"
            )

    elif chart_type == 'area':
        if y_col and y_col in df_agg.columns and x_col and x_col in df_agg.columns:
            fig = px.area(
                df_agg,
                x=x_col,
                y=y_col,
                color=color_opt,
                title=title_override or f"Area Chart: {y_col} over {x_col}",
                color_discrete_sequence=color_palette
            )
        else:
            fig = create_error_figure("Area chart requires both X and Y columns")

    elif chart_type == 'box':
        if y_col and y_col in df_agg.columns:
            fig = px.box(
                df_agg,
                x=x_col if x_col and x_col != 'None' else None,
                y=y_col,
                color=color_opt,
                title=title_override or (
                    f"Box Plot: {y_col}" + (f" by {x_col}" if x_col and x_col != 'None' else "")
                ),
                color_discrete_sequence=color_palette
            )
        else:
            fig = create_error_figure("Box plot requires Y column")

    elif chart_type == 'histogram':
        if x_col and x_col in df_agg.columns:
            fig = px.histogram(
                df_agg,
                x=x_col,
                color=color_opt,
                title=title_override or f"Histogram: Distribution of {x_col}",
                color_discrete_sequence=color_palette
            )
        else:
            fig = create_error_figure(
                f"Histogram requires X column. Available columns: {list(df_agg.columns)}"
            )

    elif chart_type == 'pie':
        if y_col and y_col in df_agg.columns:
            df_pie = df_agg.groupby(y_col).size().reset_index(name='count')
            fig = px.pie(
                df_pie,
                values='count',
                names=y_col,
                title=title_override or f"Pie: Distribution of {y_col}",
                color_discrete_sequence=color_palette
            )
        elif x_col and x_col in df_agg.columns:
            value_counts = df_agg[x_col].value_counts()
            fig = px.pie(
                values=value_counts.values,
                names=value_counts.index,
                title=title_override or f"Pie: Distribution of {x_col}",
                color_discrete_sequence=color_palette
            )
        else:
            fig = create_error_figure("Pie chart requires at least one column")

    else:
        fig = create_error_figure("Chart type not supported yet—coming soon!")

    return fig
