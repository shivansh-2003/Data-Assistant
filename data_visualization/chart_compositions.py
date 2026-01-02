"""
Custom Chart Compositions module for Data Assistant Platform.
Provides advanced chart types: combo charts, small multiples, faceted charts, and layered visualizations.
"""

import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from typing import Optional, List, Dict, Any
import streamlit as st


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
        return go.Figure().add_annotation(
            text="Combo chart requires X, Y1, and Y2 columns",
            showarrow=False
        )
    
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


def generate_small_multiples(
    df: pd.DataFrame,
    x_col: str,
    y_col: str,
    facet_col: str,
    chart_type: str = 'bar',
    max_facets: int = 12
) -> go.Figure:
    """
    Generate small multiples (grid of charts) faceted by a category column.
    
    Args:
        df: DataFrame
        x_col: X-axis column
        y_col: Y-axis column
        facet_col: Column to facet by (creates one chart per unique value)
        chart_type: Base chart type (bar, line, scatter, histogram)
        max_facets: Maximum number of facets to show
        
    Returns:
        Plotly figure with subplots
    """
    if df.empty or x_col not in df.columns or y_col not in df.columns or facet_col not in df.columns:
        return go.Figure().add_annotation(
            text="Small multiples requires X, Y, and Facet columns",
            showarrow=False
        )
    
    # Get unique values for faceting
    facet_values = df[facet_col].unique()[:max_facets]
    n_facets = len(facet_values)
    
    if n_facets == 0:
        return go.Figure().add_annotation(
            text="No facet values found",
            showarrow=False
        )
    
    # Calculate grid dimensions
    cols = min(3, n_facets)
    rows = (n_facets + cols - 1) // cols
    
    # Create subplots
    fig = make_subplots(
        rows=rows,
        cols=cols,
        subplot_titles=[str(val) for val in facet_values],
        vertical_spacing=0.15 / rows,
        horizontal_spacing=0.1 / cols
    )
    
    # Generate chart for each facet
    for idx, facet_val in enumerate(facet_values):
        row = (idx // cols) + 1
        col = (idx % cols) + 1
        
        df_facet = df[df[facet_col] == facet_val]
        
        if chart_type == 'bar':
            trace = go.Bar(
                x=df_facet[x_col],
                y=df_facet[y_col],
                name=str(facet_val),
                showlegend=False
            )
        elif chart_type == 'line':
            trace = go.Scatter(
                x=df_facet[x_col],
                y=df_facet[y_col],
                mode='lines+markers',
                name=str(facet_val),
                showlegend=False
            )
        elif chart_type == 'scatter':
            trace = go.Scatter(
                x=df_facet[x_col],
                y=df_facet[y_col],
                mode='markers',
                name=str(facet_val),
                showlegend=False
            )
        elif chart_type == 'histogram':
            trace = go.Histogram(
                x=df_facet[y_col],
                name=str(facet_val),
                showlegend=False
            )
        else:
            trace = go.Bar(x=df_facet[x_col], y=df_facet[y_col], name=str(facet_val), showlegend=False)
        
        fig.add_trace(trace, row=row, col=col)
    
    # Update layout
    fig.update_layout(
        title=f"Small Multiples: {y_col} by {x_col} (Faceted by {facet_col})",
        height=300 * rows,
        showlegend=False
    )
    
    # Update x-axis labels (only bottom row)
    for idx in range(n_facets):
        row = (idx // cols) + 1
        col = (idx % cols) + 1
        if row == rows:  # Bottom row
            fig.update_xaxes(title_text=x_col, row=row, col=col)
        else:
            fig.update_xaxes(title_text="", row=row, col=col)
    
    # Update y-axis labels (only left column)
    for idx in range(n_facets):
        row = (idx // cols) + 1
        col = (idx % cols) + 1
        if col == 1:  # Left column
            fig.update_yaxes(title_text=y_col, row=row, col=col)
        else:
            fig.update_yaxes(title_text="", row=row, col=col)
    
    return fig


def generate_faceted_chart(
    df: pd.DataFrame,
    x_col: str,
    y_col: str,
    facet_col: str,
    chart_type: str = 'scatter',
    max_facets: int = 16
) -> go.Figure:
    """
    Generate faceted chart with automatic subplot creation based on grouping column.
    Similar to small multiples but optimized for larger grids.
    
    Args:
        df: DataFrame
        x_col: X-axis column
        y_col: Y-axis column
        facet_col: Column to facet by
        chart_type: Chart type (scatter, bar, line, box)
        max_facets: Maximum number of facets (up to 4x4 grid)
        
    Returns:
        Plotly figure with faceted subplots
    """
    if df.empty or x_col not in df.columns or y_col not in df.columns or facet_col not in df.columns:
        return go.Figure().add_annotation(
            text="Faceted chart requires X, Y, and Facet columns",
            showarrow=False
        )
    
    # Get unique values for faceting
    facet_values = sorted(df[facet_col].unique())[:max_facets]
    n_facets = len(facet_values)
    
    if n_facets == 0:
        return go.Figure().add_annotation(
            text="No facet values found",
            showarrow=False
        )
    
    # Calculate grid dimensions (up to 4x4)
    max_cols = 4
    cols = min(max_cols, n_facets)
    rows = min(4, (n_facets + cols - 1) // cols)
    
    # Create subplots
    fig = make_subplots(
        rows=rows,
        cols=cols,
        subplot_titles=[str(val) for val in facet_values],
        vertical_spacing=0.12 / rows,
        horizontal_spacing=0.1 / cols
    )
    
    # Generate chart for each facet
    for idx, facet_val in enumerate(facet_values):
        row = (idx // cols) + 1
        col = (idx % cols) + 1
        
        df_facet = df[df[facet_col] == facet_val]
        
        if chart_type == 'scatter':
            trace = go.Scatter(
                x=df_facet[x_col],
                y=df_facet[y_col],
                mode='markers',
                name=str(facet_val),
                showlegend=(idx == 0),  # Only show legend for first trace
                marker=dict(size=6, opacity=0.7)
            )
        elif chart_type == 'bar':
            trace = go.Bar(
                x=df_facet[x_col],
                y=df_facet[y_col],
                name=str(facet_val),
                showlegend=(idx == 0),
                marker=dict(opacity=0.7)
            )
        elif chart_type == 'line':
            trace = go.Scatter(
                x=df_facet[x_col],
                y=df_facet[y_col],
                mode='lines+markers',
                name=str(facet_val),
                showlegend=(idx == 0),
                line=dict(width=2)
            )
        elif chart_type == 'box':
            trace = go.Box(
                y=df_facet[y_col],
                name=str(facet_val),
                showlegend=(idx == 0)
            )
        else:
            trace = go.Scatter(x=df_facet[x_col], y=df_facet[y_col], mode='markers', name=str(facet_val), showlegend=(idx == 0))
        
        fig.add_trace(trace, row=row, col=col)
    
    # Update layout
    fig.update_layout(
        title=f"Faceted Chart: {y_col} vs {x_col} (Grouped by {facet_col})",
        height=250 * rows,
        legend=dict(orientation="h", yanchor="bottom", y=-0.1, xanchor="center", x=0.5)
    )
    
    # Update axes labels
    for idx in range(n_facets):
        row = (idx // cols) + 1
        col = (idx % cols) + 1
        if row == rows:  # Bottom row
            fig.update_xaxes(title_text=x_col, row=row, col=col)
        if col == 1:  # Left column
            fig.update_yaxes(title_text=y_col, row=row, col=col)
    
    return fig


def generate_layered_chart(
    df: pd.DataFrame,
    x_col: str,
    y_cols: List[str],
    layer_types: List[str],
    opacity: float = 0.7,
    color_col: Optional[str] = None
) -> go.Figure:
    """
    Generate layered visualization with multiple traces and transparency controls.
    
    Args:
        df: DataFrame
        x_col: X-axis column
        y_cols: List of Y-axis columns to layer
        layer_types: List of chart types for each layer (bar, line, scatter, area, histogram)
        opacity: Opacity level (0-1) for layers
        color_col: Optional color/grouping column
        
    Returns:
        Plotly figure with layered traces
    """
    if df.empty or x_col not in df.columns:
        return go.Figure().add_annotation(
            text="Layered chart requires X column and at least one Y column",
            showarrow=False
        )
    
    if not y_cols or len(y_cols) == 0:
        return go.Figure().add_annotation(
            text="Please select at least one Y column to layer",
            showarrow=False
        )
    
    if len(layer_types) != len(y_cols):
        # Default layer types
        layer_types = ['line'] * len(y_cols)
    
    fig = go.Figure()
    
    # Color palette for different layers
    colors = px.colors.qualitative.Set3
    
    # Add each layer
    for idx, (y_col, layer_type) in enumerate(zip(y_cols, layer_types)):
        if y_col not in df.columns:
            continue
        
        color = colors[idx % len(colors)]
        
        if layer_type == 'bar':
            trace = go.Bar(
                x=df[x_col],
                y=df[y_col],
                name=y_col,
                marker_color=color,
                opacity=opacity
            )
        elif layer_type == 'line':
            trace = go.Scatter(
                x=df[x_col],
                y=df[y_col],
                name=y_col,
                mode='lines+markers',
                line=dict(color=color, width=2),
                marker=dict(size=6),
                opacity=opacity
            )
        elif layer_type == 'scatter':
            trace = go.Scatter(
                x=df[x_col],
                y=df[y_col],
                name=y_col,
                mode='markers',
                marker=dict(color=color, size=8, opacity=opacity)
            )
        elif layer_type == 'area':
            trace = go.Scatter(
                x=df[x_col],
                y=df[y_col],
                name=y_col,
                mode='lines',
                fill='tozeroy',
                line=dict(color=color),
                opacity=opacity * 0.6
            )
        elif layer_type == 'histogram':
            trace = go.Histogram(
                x=df[y_col],
                name=y_col,
                marker_color=color,
                opacity=opacity,
                nbinsx=30
            )
        else:
            trace = go.Scatter(
                x=df[x_col],
                y=df[y_col],
                name=y_col,
                mode='lines',
                line=dict(color=color),
                opacity=opacity
            )
        
        fig.add_trace(trace)
    
    # Update layout
    fig.update_layout(
        title=f"Layered Chart: Multiple Y columns vs {x_col}",
        xaxis_title=x_col,
        yaxis_title=y_cols[0] if y_cols else "Value",
        hovermode='x unified',
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    
    return fig

