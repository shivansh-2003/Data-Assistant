"""
Data Visualization module for Data Assistant Platform.
"""

from .cache_invalidation import on_data_changed
from .chart_compositions import generate_combo_chart
from .core.chart_generator import generate_chart, generate_from_config
from .core.data_fetcher import (
    get_dataframe_from_session,
    get_tables_from_session,
    invalidate_viz_cache,
)
from .dashboard_builder import DashboardBuilder
from .intelligence.recommender import ChartRecommendation, get_chart_recommendations
from .visualization import render_visualization_tab

__all__ = [
    "render_visualization_tab",
    "get_dataframe_from_session",
    "get_tables_from_session",
    "invalidate_viz_cache",
    "on_data_changed",
    "generate_chart",
    "generate_from_config",
    "ChartRecommendation",
    "get_chart_recommendations",
    "generate_combo_chart",
    "DashboardBuilder",
]
