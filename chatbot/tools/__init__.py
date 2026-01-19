"""Tools for InsightBot."""

from .simple_charts import bar_chart, line_chart, scatter_chart, histogram
from .complex_charts import combo_chart, dashboard
from .data_tools import insight_tool
from finance import trading_performance_analyzer

def get_all_tools():
    """Get all available tools for LLM binding."""
    return [
        insight_tool,
        trading_performance_analyzer,
        bar_chart,
        line_chart,
        scatter_chart,
        histogram,
        combo_chart,
        dashboard
    ]

__all__ = [
    "bar_chart",
    "line_chart",
    "scatter_chart",
    "histogram",
    "combo_chart",
    "dashboard",
    "insight_tool",
    "trading_performance_analyzer",
    "get_all_tools"
]

