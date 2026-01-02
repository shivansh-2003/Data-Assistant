"""
Data Visualization module for Data Assistant Platform.
Provides chart generation and smart recommendations.
"""

from .visualization import render_visualization_tab, get_dataframe_from_session, generate_chart
from .smart_recommendations import get_chart_recommendations
from .chart_compositions import (
    generate_combo_chart,
    generate_small_multiples,
    generate_faceted_chart,
    generate_layered_chart
)
from .dashboard_builder import (
    render_dashboard_tab,
    pin_chart_to_dashboard,
    get_current_chart_config,
    initialize_dashboard_state
)

__all__ = [
    'render_visualization_tab',
    'get_dataframe_from_session',
    'generate_chart',
    'get_chart_recommendations',
    'generate_combo_chart',
    'generate_small_multiples',
    'generate_faceted_chart',
    'generate_layered_chart',
    'render_dashboard_tab',
    'pin_chart_to_dashboard',
    'get_current_chart_config',
    'initialize_dashboard_state'
]

