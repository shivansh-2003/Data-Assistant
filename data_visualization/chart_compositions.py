"""
Custom Chart Compositions module for Data Assistant Platform.
Provides combo charts with dual y-axes with color grouping and enhanced styling.
"""

import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import plotly.express as px
from typing import Optional
from .utils import create_error_figure, apply_theme


def _get_color_palette(color_scheme: str = 'plotly', n_colors: int = 10):
    """
    Get color palette from Plotly color schemes.
    
    Args:
        color_scheme: Color scheme name (plotly, set3, pastel, etc.)
        n_colors: Number of colors needed
        
    Returns:
        List of color hex codes
    """
    try:
        # Use Plotly Express color sequences
        if hasattr(px.colors.qualitative, color_scheme.upper()):
            palette = getattr(px.colors.qualitative, color_scheme.upper())
        elif hasattr(px.colors.sequential, color_scheme.upper()):
            palette = getattr(px.colors.sequential, color_scheme.upper())
        else:
            # Default to Plotly palette
            palette = px.colors.qualitative.Plotly
        
        # Cycle through palette if needed
        if n_colors > len(palette):
            palette = (palette * ((n_colors // len(palette)) + 1))[:n_colors]
        else:
            palette = palette[:n_colors]
        
        return palette
    except:
        # Fallback to default Plotly colors
        return px.colors.qualitative.Plotly[:n_colors]


def _format_number(value):
    """Format number for tooltip display."""
    if pd.isna(value):
        return "N/A"
    try:
        if abs(value) >= 1e6:
            return f"{value/1e6:.2f}M"
        elif abs(value) >= 1e3:
            return f"{value/1e3:.2f}K"
        else:
            return f"{value:,.2f}" if isinstance(value, (int, float)) else str(value)
    except:
        return str(value)


def generate_combo_chart(
    df: pd.DataFrame,
    x_col: str,
    y1_col: str,
    y2_col: str,
    chart1_type: str = 'bar',
    chart2_type: str = 'line',
    color_col: Optional[str] = None,
    color_scheme: str = 'plotly',
    opacity1: float = 0.8,
    opacity2: float = 0.8
) -> go.Figure:
    """
    Generate combo chart with dual y-axes.
    Combines two different chart types (e.g., bar + line) on the same plot.
    Supports color grouping and enhanced styling.
    
    Args:
        df: DataFrame
        x_col: X-axis column
        y1_col: First Y-axis column (left axis)
        y2_col: Second Y-axis column (right axis)
        chart1_type: Type for first chart (bar, line, scatter, area)
        chart2_type: Type for second chart (bar, line, scatter, area)
        color_col: Optional color/grouping column
        color_scheme: Color scheme name (plotly, set3, pastel, etc.)
        opacity1: Opacity for first chart (0-1)
        opacity2: Opacity for second chart (0-1)
        
    Returns:
        Plotly figure with dual y-axes
    """
    # Validation
    if df.empty:
        return create_error_figure("No data available for combo chart")
    
    if x_col not in df.columns:
        return create_error_figure(f"X column '{x_col}' not found in data")
    
    if y1_col not in df.columns:
        return create_error_figure(f"Y1 column '{y1_col}' not found in data")
    
    if y2_col not in df.columns:
        return create_error_figure(f"Y2 column '{y2_col}' not found in data")
    
    if color_col and color_col not in df.columns:
        return create_error_figure(f"Color column '{color_col}' not found in data")
    
    # Clamp opacity values
    opacity1 = max(0.1, min(1.0, opacity1))
    opacity2 = max(0.1, min(1.0, opacity2))
    
    # Create subplot with secondary y-axis
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    
    # Get color palette
    if color_col:
        unique_groups = df[color_col].nunique()
        colors = _get_color_palette(color_scheme, unique_groups)
        group_values = sorted(df[color_col].dropna().unique())
    else:
        colors = _get_color_palette(color_scheme, 2)
        group_values = [None]
    
    # Prepare data for grouping
    if color_col:
        grouped_data = df.groupby([x_col, color_col], dropna=False)
    else:
        grouped_data = None
    
    # First trace (left y-axis) - with or without grouping
    if color_col and grouped_data is not None:
        # Create multiple traces for each group
        for idx, group_val in enumerate(group_values):
            if pd.isna(group_val):
                group_df = df[df[color_col].isna()]
            else:
                group_df = df[df[color_col] == group_val]
            
            if group_df.empty:
                continue
            
            color = colors[idx % len(colors)]
            trace_name = f"{y1_col} ({group_val})" if group_val is not None else f"{y1_col} (N/A)"
            
            if chart1_type == 'bar':
                trace1 = go.Bar(
                    x=group_df[x_col],
                    y=group_df[y1_col],
                    name=trace_name,
                    marker_color=color,
                    opacity=opacity1,
                    hovertemplate=f"<b>{x_col}</b>: %{{x}}<br>" +
                                 f"<b>{y1_col}</b>: %{{y:,.2f}}<br>" +
                                 f"<b>{color_col}</b>: {group_val}<br>" +
                                 "<extra></extra>"
                )
            elif chart1_type == 'line':
                trace1 = go.Scatter(
                    x=group_df[x_col],
                    y=group_df[y1_col],
                    name=trace_name,
                    mode='lines+markers',
                    line=dict(color=color, width=2.5),
                    marker=dict(size=7, color=color, opacity=opacity1),
                    hovertemplate=f"<b>{x_col}</b>: %{{x}}<br>" +
                                 f"<b>{y1_col}</b>: %{{y:,.2f}}<br>" +
                                 f"<b>{color_col}</b>: {group_val}<br>" +
                                 "<extra></extra>"
                )
            elif chart1_type == 'scatter':
                trace1 = go.Scatter(
                    x=group_df[x_col],
                    y=group_df[y1_col],
                    name=trace_name,
                    mode='markers',
                    marker=dict(color=color, size=9, opacity=opacity1, line=dict(width=1, color='white')),
                    hovertemplate=f"<b>{x_col}</b>: %{{x}}<br>" +
                                 f"<b>{y1_col}</b>: %{{y:,.2f}}<br>" +
                                 f"<b>{color_col}</b>: {group_val}<br>" +
                                 "<extra></extra>"
                )
            elif chart1_type == 'area':
                trace1 = go.Scatter(
                    x=group_df[x_col],
                    y=group_df[y1_col],
                    name=trace_name,
                    mode='lines',
                    fill='tozeroy',
                    line=dict(color=color, width=2),
                    opacity=opacity1 * 0.7,  # Area charts need lower opacity
                    hovertemplate=f"<b>{x_col}</b>: %{{x}}<br>" +
                                 f"<b>{y1_col}</b>: %{{y:,.2f}}<br>" +
                                 f"<b>{color_col}</b>: {group_val}<br>" +
                                 "<extra></extra>"
                )
            else:
                trace1 = go.Bar(x=group_df[x_col], y=group_df[y1_col], name=trace_name, marker_color=color)
            
            fig.add_trace(trace1, secondary_y=False)
    else:
        # Single trace without grouping
        color1 = colors[0] if len(colors) > 0 else '#1f77b4'
        
    if chart1_type == 'bar':
        trace1 = go.Bar(
            x=df[x_col],
            y=df[y1_col],
            name=y1_col,
                marker_color=color1,
                opacity=opacity1,
                hovertemplate=f"<b>{x_col}</b>: %{{x}}<br>" +
                             f"<b>{y1_col}</b>: %{{y:,.2f}}<br>" +
                             "<extra></extra>"
        )
    elif chart1_type == 'line':
        trace1 = go.Scatter(
            x=df[x_col],
            y=df[y1_col],
            name=y1_col,
            mode='lines+markers',
                line=dict(color=color1, width=3),
                marker=dict(size=8, color=color1, opacity=opacity1),
                hovertemplate=f"<b>{x_col}</b>: %{{x}}<br>" +
                             f"<b>{y1_col}</b>: %{{y:,.2f}}<br>" +
                             "<extra></extra>"
        )
    elif chart1_type == 'scatter':
        trace1 = go.Scatter(
            x=df[x_col],
            y=df[y1_col],
            name=y1_col,
            mode='markers',
                marker=dict(color=color1, size=10, opacity=opacity1, line=dict(width=1.5, color='white')),
                hovertemplate=f"<b>{x_col}</b>: %{{x}}<br>" +
                             f"<b>{y1_col}</b>: %{{y:,.2f}}<br>" +
                             "<extra></extra>"
        )
    elif chart1_type == 'area':
        trace1 = go.Scatter(
            x=df[x_col],
            y=df[y1_col],
            name=y1_col,
            mode='lines',
            fill='tozeroy',
                line=dict(color=color1, width=2.5),
                opacity=opacity1 * 0.7,
                hovertemplate=f"<b>{x_col}</b>: %{{x}}<br>" +
                             f"<b>{y1_col}</b>: %{{y:,.2f}}<br>" +
                             "<extra></extra>"
        )
    else:
            trace1 = go.Bar(x=df[x_col], y=df[y1_col], name=y1_col, marker_color=color1, opacity=opacity1)
    
    fig.add_trace(trace1, secondary_y=False)
    
    # Second trace (right y-axis) - with or without grouping
    if color_col and grouped_data is not None:
        # Create multiple traces for each group
        for idx, group_val in enumerate(group_values):
            if pd.isna(group_val):
                group_df = df[df[color_col].isna()]
            else:
                group_df = df[df[color_col] == group_val]
            
            if group_df.empty:
                continue
            
            # Use different color scheme or offset for second axis
            color = colors[(idx + len(colors) // 2) % len(colors)] if len(colors) > 1 else colors[0]
            trace_name = f"{y2_col} ({group_val})" if group_val is not None else f"{y2_col} (N/A)"
            
            if chart2_type == 'bar':
                trace2 = go.Bar(
                    x=group_df[x_col],
                    y=group_df[y2_col],
                    name=trace_name,
                    marker_color=color,
                    opacity=opacity2,
                    hovertemplate=f"<b>{x_col}</b>: %{{x}}<br>" +
                                 f"<b>{y2_col}</b>: %{{y:,.2f}}<br>" +
                                 f"<b>{color_col}</b>: {group_val}<br>" +
                                 "<extra></extra>"
                )
            elif chart2_type == 'line':
                trace2 = go.Scatter(
                    x=group_df[x_col],
                    y=group_df[y2_col],
                    name=trace_name,
                    mode='lines+markers',
                    line=dict(color=color, width=2.5, dash='dash'),
                    marker=dict(size=7, color=color, opacity=opacity2, symbol='diamond'),
                    hovertemplate=f"<b>{x_col}</b>: %{{x}}<br>" +
                                 f"<b>{y2_col}</b>: %{{y:,.2f}}<br>" +
                                 f"<b>{color_col}</b>: {group_val}<br>" +
                                 "<extra></extra>"
                )
            elif chart2_type == 'scatter':
                trace2 = go.Scatter(
                    x=group_df[x_col],
                    y=group_df[y2_col],
                    name=trace_name,
                    mode='markers',
                    marker=dict(color=color, size=9, opacity=opacity2, symbol='diamond', 
                              line=dict(width=1, color='white')),
                    hovertemplate=f"<b>{x_col}</b>: %{{x}}<br>" +
                                 f"<b>{y2_col}</b>: %{{y:,.2f}}<br>" +
                                 f"<b>{color_col}</b>: {group_val}<br>" +
                                 "<extra></extra>"
                )
            elif chart2_type == 'area':
                trace2 = go.Scatter(
                    x=group_df[x_col],
                    y=group_df[y2_col],
                    name=trace_name,
                    mode='lines',
                    fill='tozeroy',
                    line=dict(color=color, width=2, dash='dot'),
                    opacity=opacity2 * 0.7,
                    hovertemplate=f"<b>{x_col}</b>: %{{x}}<br>" +
                                 f"<b>{y2_col}</b>: %{{y:,.2f}}<br>" +
                                 f"<b>{color_col}</b>: {group_val}<br>" +
                                 "<extra></extra>"
                )
            else:
                trace2 = go.Scatter(x=group_df[x_col], y=group_df[y2_col], name=trace_name, 
                                  mode='lines', line=dict(color=color, dash='dash'))
            
            fig.add_trace(trace2, secondary_y=True)
    else:
        # Single trace without grouping
        color2 = colors[1] if len(colors) > 1 else '#ff7f0e'
        
    if chart2_type == 'bar':
        trace2 = go.Bar(
            x=df[x_col],
            y=df[y2_col],
            name=y2_col,
                marker_color=color2,
                opacity=opacity2,
                hovertemplate=f"<b>{x_col}</b>: %{{x}}<br>" +
                             f"<b>{y2_col}</b>: %{{y:,.2f}}<br>" +
                             "<extra></extra>"
        )
    elif chart2_type == 'line':
        trace2 = go.Scatter(
            x=df[x_col],
            y=df[y2_col],
            name=y2_col,
            mode='lines+markers',
            line=dict(color=color2, width=3, dash='dash'),
            marker=dict(size=8, color=color2, opacity=opacity2, symbol='diamond'),
            hovertemplate=f"<b>{x_col}</b>: %{{x}}<br>" +
                         f"<b>{y2_col}</b>: %{{y:,.2f}}<br>" +
                         "<extra></extra>"
        )
    elif chart2_type == 'scatter':
        trace2 = go.Scatter(
            x=df[x_col],
            y=df[y2_col],
            name=y2_col,
            mode='markers',
            marker=dict(color=color2, size=10, opacity=opacity2, symbol='diamond',
                      line=dict(width=1.5, color='white')),
            hovertemplate=f"<b>{x_col}</b>: %{{x}}<br>" +
                         f"<b>{y2_col}</b>: %{{y:,.2f}}<br>" +
                         "<extra></extra>"
        )
    elif chart2_type == 'area':
        trace2 = go.Scatter(
            x=df[x_col],
            y=df[y2_col],
            name=y2_col,
            mode='lines',
            fill='tozeroy',
            line=dict(color=color2, width=2.5, dash='dot'),
            opacity=opacity2 * 0.7,
            hovertemplate=f"<b>{x_col}</b>: %{{x}}<br>" +
                         f"<b>{y2_col}</b>: %{{y:,.2f}}<br>" +
                         "<extra></extra>"
        )
    else:
        trace2 = go.Scatter(
            x=df[x_col],
            y=df[y2_col],
            name=y2_col,
            mode='lines',
            line=dict(color=color2, dash='dash')
        )
    
    fig.add_trace(trace2, secondary_y=True)
    
    # Update axes with better formatting
    fig.update_xaxes(
        title_text=x_col,
        title_font=dict(size=14, color='#2c3e50'),
        showgrid=True,
        gridcolor='rgba(128, 128, 128, 0.2)',
        zeroline=False
    )
    
    fig.update_yaxes(
        title_text=y1_col,
        title_font=dict(size=14, color='#2c3e50'),
        secondary_y=False,
        showgrid=True,
        gridcolor='rgba(128, 128, 128, 0.2)',
        zeroline=False
    )
    
    fig.update_yaxes(
        title_text=y2_col,
        title_font=dict(size=14, color='#2c3e50'),
        secondary_y=True,
        showgrid=False,  # Avoid double grid lines
        zeroline=False
    )
    
    # Enhanced layout with better styling
    title_text = f"Combo Chart: {y1_col} ({chart1_type}) + {y2_col} ({chart2_type})"
    if color_col:
        title_text += f" by {color_col}"
    
    fig.update_layout(
        title=dict(
            text=title_text,
            font=dict(size=18, color='#1f77b4'),
            x=0.5,
            xanchor='center'
        ),
        hovermode='x unified',
        hoverlabel=dict(
            bgcolor='rgba(255, 255, 255, 0.95)',
            bordercolor='#1f77b4',
            font_size=12,
            font_family="Arial"
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(size=11),
            bgcolor='rgba(255, 255, 255, 0.8)',
            bordercolor='rgba(0, 0, 0, 0.2)',
            borderwidth=1
        ),
        margin=dict(l=60, r=60, t=80, b=60),
        plot_bgcolor='rgba(255, 255, 255, 0.8)',
        paper_bgcolor='rgba(255, 255, 255, 0.95)'
    )
    
    # Apply theme (light/dark mode support)
    fig = apply_theme(fig)
    
    return fig
