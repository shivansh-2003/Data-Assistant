"""
Utility functions for the data_visualization module.
Shared helper functions to avoid code duplication.
"""

import streamlit as st
import plotly.graph_objects as go


def create_error_figure(message: str) -> go.Figure:
    """
    Create a standardized error figure.
    
    Args:
        message: Error message to display
        
    Returns:
        Plotly figure with error annotation
    """
    return go.Figure().add_annotation(
        text=message,
        showarrow=False
    )


def apply_theme(fig: go.Figure) -> go.Figure:
    """
    Apply Streamlit theme to Plotly figure.
    
    Args:
        fig: Plotly figure to apply theme to
        
    Returns:
        Figure with theme applied
    """
    try:
        theme = st.get_option("theme.base")
        if theme == "dark":
            fig.update_layout(template='plotly_dark')
        else:
            fig.update_layout(template='plotly_white')
    except:
        # Default to white theme
        fig.update_layout(template='plotly_white')
    
    return fig

