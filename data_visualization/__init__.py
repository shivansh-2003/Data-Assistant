"""
Data Visualization module for Data Assistant Platform.
Provides chart generation and smart recommendations.
"""

from .visualization import render_visualization_tab, get_dataframe_from_session, generate_chart
from .smart_recommendations import ChartRecommendation, get_chart_recommendations
from .chart_compositions import generate_combo_chart
from .dashboard_builder import DashboardBuilder

__all__ = [
    'render_visualization_tab',
    'get_dataframe_from_session',
    'generate_chart',
    'ChartRecommendation',
    'get_chart_recommendations',
    'generate_combo_chart',
    'DashboardBuilder'
]

