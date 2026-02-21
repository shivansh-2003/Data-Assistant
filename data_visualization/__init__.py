"""
Data Visualization module for Data Assistant Platform.
Provides chart generation and smart recommendations.
"""

from .core.chart_generator import generate_chart
from .core.data_fetcher import get_dataframe_from_session
from .visualization import render_visualization_tab
from .charts.combo import generate_combo_chart
from .intelligence.recommender import ChartRecommendation, get_chart_recommendations
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
