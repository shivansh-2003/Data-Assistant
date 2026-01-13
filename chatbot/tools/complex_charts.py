"""Complex chart tools wrapping advanced visualization features."""

from langchain_core.tools import tool
from typing import List, Optional


@tool
def combo_chart(metrics: List[str], x_col: str, table_name: str = "current") -> dict:
    """
    Create a combination chart with multiple metrics.
    
    Use for:
    - Multi-metric comparison
    - Dual-axis charts
    - Complex visualizations
    
    Args:
        metrics: List of metric column names
        x_col: Column name for X-axis
        table_name: Name of the table to use
        
    Returns:
        Dict with chart configuration
    """
    return {
        "tool": "combo_chart",
        "chart_type": "combo",
        "metrics": metrics,
        "x_col": x_col,
        "table_name": table_name
    }


@tool
def dashboard(charts: List[dict], layout: str = "grid") -> dict:
    """
    Create a multi-chart dashboard.
    
    Use for:
    - Multiple visualizations at once
    - Comprehensive data overview
    - Dashboard-style reports
    
    Args:
        charts: List of chart configurations
        layout: Layout type (grid, rows, columns)
        
    Returns:
        Dict with dashboard configuration
    """
    return {
        "tool": "dashboard",
        "chart_type": "dashboard",
        "charts": charts,
        "layout": layout
    }

