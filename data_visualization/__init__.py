"""
Data Visualization module for Data Assistant Platform.
"""

from .core.chart_generator import generate_chart, generate_from_config
from .core.data_fetcher import get_dataframe_from_session
from .dashboard_builder import DashboardBuilder
from .smart_recommendations import ChartRecommendation, get_chart_recommendations
from .visualization import render_visualization_tab

# Backward compatibility
from .chart_compositions import generate_combo_chart

__all__ = [
    "render_visualization_tab",
    "get_dataframe_from_session",
    "generate_chart",
    "generate_from_config",
    "ChartRecommendation",
    "get_chart_recommendations",
    "generate_combo_chart",
    "DashboardBuilder",
]
