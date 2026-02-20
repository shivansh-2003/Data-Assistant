"""Tools for InsightBot."""

from .simple_charts import (
    bar_chart,
    line_chart,
    scatter_chart,
    histogram,
    area_chart,
    box_chart,
    heatmap_chart,
    correlation_matrix
)
from .complex_charts import combo_chart, dashboard
from .data_tools import insight_tool


def get_all_tools():
    """Get all available tools for LLM binding."""
    return [
        insight_tool,
        bar_chart,
        line_chart,
        scatter_chart,
        histogram,
        area_chart,
        box_chart,
        heatmap_chart,
        correlation_matrix,
        combo_chart,
        dashboard
    ]

__all__ = [
    "bar_chart",
    "line_chart",
    "scatter_chart",
    "histogram",
    "area_chart",
    "box_chart",
    "heatmap_chart",
    "correlation_matrix",
    "combo_chart",
    "dashboard",
    "insight_tool",
    "get_all_tools"
]

