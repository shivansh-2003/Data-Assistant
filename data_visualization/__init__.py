"""
Data Visualization module for Data Assistant Platform.
Provides chart generation and smart recommendations.
"""

from .visualization import render_visualization_tab, get_dataframe_from_session, generate_chart
from .smart_recommendations import get_chart_recommendations

__all__ = [
    'render_visualization_tab',
    'get_dataframe_from_session',
    'generate_chart',
    'get_chart_recommendations'
]

