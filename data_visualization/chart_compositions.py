"""
Custom Chart Compositions module for Data Assistant Platform.
Provides combo charts with dual y-axes.
"""

import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
from typing import Optional
from .utils import create_error_figure


def generate_combo_chart(
    df: pd.DataFrame,
    x_col: str,
    y1_col: str,
    y2_col: str,
    chart1_type: str = 'bar',
    chart2_type: str = 'line',
    color_col: Optional[str] = None
) -> go.Figure:
    """
    Generate combo chart with dual y-axes.
    Combines two different chart types (e.g., bar + line) on the same plot.
    
    Args:
        df: DataFrame
        x_col: X-axis column
        y1_col: First Y-axis column (left axis)
        y2_col: Second Y-axis column (right axis)
        chart1_type: Type for first chart (bar, line, scatter, area)
        chart2_type: Type for second chart (bar, line, scatter, area)
        color_col: Optional color/grouping column
        
    Returns:
        Plotly figure with dual y-axes
    """
    if df.empty or x_col not in df.columns or y1_col not in df.columns or y2_col not in df.columns:
        return create_error_figure("Combo chart requires X, Y1, and Y2 columns")
    
    # Create subplot with secondary y-axis
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    
    # First trace (left y-axis)
    if chart1_type == 'bar':
        trace1 = go.Bar(
            x=df[x_col],
            y=df[y1_col],
            name=y1_col,
            marker_color='steelblue',
            opacity=0.7
        )
    elif chart1_type == 'line':
        trace1 = go.Scatter(
            x=df[x_col],
            y=df[y1_col],
            name=y1_col,
            mode='lines+markers',
            line=dict(color='steelblue', width=2),
            marker=dict(size=6)
        )
    elif chart1_type == 'scatter':
        trace1 = go.Scatter(
            x=df[x_col],
            y=df[y1_col],
            name=y1_col,
            mode='markers',
            marker=dict(color='steelblue', size=8, opacity=0.7)
        )
    elif chart1_type == 'area':
        trace1 = go.Scatter(
            x=df[x_col],
            y=df[y1_col],
            name=y1_col,
            mode='lines',
            fill='tozeroy',
            line=dict(color='steelblue'),
            opacity=0.6
        )
    else:
        trace1 = go.Bar(x=df[x_col], y=df[y1_col], name=y1_col)
    
    fig.add_trace(trace1, secondary_y=False)
    
    # Second trace (right y-axis)
    if chart2_type == 'bar':
        trace2 = go.Bar(
            x=df[x_col],
            y=df[y2_col],
            name=y2_col,
            marker_color='coral',
            opacity=0.7
        )
    elif chart2_type == 'line':
        trace2 = go.Scatter(
            x=df[x_col],
            y=df[y2_col],
            name=y2_col,
            mode='lines+markers',
            line=dict(color='coral', width=2, dash='dash'),
            marker=dict(size=6)
        )
    elif chart2_type == 'scatter':
        trace2 = go.Scatter(
            x=df[x_col],
            y=df[y2_col],
            name=y2_col,
            mode='markers',
            marker=dict(color='coral', size=8, opacity=0.7, symbol='diamond')
        )
    elif chart2_type == 'area':
        trace2 = go.Scatter(
            x=df[x_col],
            y=df[y2_col],
            name=y2_col,
            mode='lines',
            fill='tozeroy',
            line=dict(color='coral'),
            opacity=0.6
        )
    else:
        trace2 = go.Scatter(x=df[x_col], y=df[y2_col], name=y2_col, mode='lines')
    
    fig.add_trace(trace2, secondary_y=True)
    
    # Update axes
    fig.update_xaxes(title_text=x_col)
    fig.update_yaxes(title_text=y1_col, secondary_y=False)
    fig.update_yaxes(title_text=y2_col, secondary_y=True)
    
    # Update layout
    fig.update_layout(
        title=f"Combo Chart: {y1_col} ({chart1_type}) + {y2_col} ({chart2_type})",
        hovermode='x unified',
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    
    return fig
