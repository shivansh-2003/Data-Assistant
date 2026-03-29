"""
Utility functions for the data_visualization module.
Shared helper functions to avoid code duplication.
"""

import plotly.graph_objects as go

from .theme.plotly_templates import apply_theme


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


# apply_theme re-exported from theme (custom data_assistant_* templates)

