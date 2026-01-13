"""Simple chart tools wrapping existing visualization module."""

from langchain_core.tools import tool
from typing import Optional
import plotly.graph_objects as go


@tool
def bar_chart(x: str, y: str, agg: str = "count", color: Optional[str] = None, table_name: str = "current") -> dict:
    """
    Create a bar chart for categorical comparisons.
    
    Use for:
    - Comparing values across categories
    - Top N rankings
    - Grouped comparisons
    
    Args:
        x: Column name for X-axis (categorical)
        y: Column name for Y-axis (numeric)
        agg: Aggregation function (count, sum, mean, median, min, max)
        color: Optional column for color grouping
        table_name: Name of the table to use
        
    Returns:
        Dict with chart configuration
    """
    return {
        "tool": "bar_chart",
        "chart_type": "bar",
        "x_col": x,
        "y_col": y,
        "agg_func": agg,
        "color_col": color,
        "table_name": table_name
    }


@tool
def line_chart(x: str, y: str, color: Optional[str] = None, table_name: str = "current") -> dict:
    """
    Create a line chart for trends over time.
    
    Use for:
    - Time series analysis
    - Trend visualization
    - Change over time
    
    Args:
        x: Column name for X-axis (usually date/time)
        y: Column name for Y-axis (numeric)
        color: Optional column for multiple lines
        table_name: Name of the table to use
        
    Returns:
        Dict with chart configuration
    """
    return {
        "tool": "line_chart",
        "chart_type": "line",
        "x_col": x,
        "y_col": y,
        "color_col": color,
        "table_name": table_name
    }


@tool
def scatter_chart(x: str, y: str, color: Optional[str] = None, table_name: str = "current") -> dict:
    """
    Create a scatter plot for relationship analysis.
    
    Use for:
    - Correlation visualization
    - X vs Y relationships
    - Pattern detection
    
    Args:
        x: Column name for X-axis (numeric)
        y: Column name for Y-axis (numeric)
        color: Optional column for color grouping
        table_name: Name of the table to use
        
    Returns:
        Dict with chart configuration
    """
    return {
        "tool": "scatter_chart",
        "chart_type": "scatter",
        "x_col": x,
        "y_col": y,
        "color_col": color,
        "table_name": table_name
    }


@tool
def histogram(column: str, bins: int = 30, table_name: str = "current") -> dict:
    """
    Create a histogram for distribution analysis.
    
    Use for:
    - Distribution visualization
    - Frequency analysis
    - Data spread
    
    Args:
        column: Column name to analyze
        bins: Number of bins (default 30)
        table_name: Name of the table to use
        
    Returns:
        Dict with chart configuration
    """
    return {
        "tool": "histogram",
        "chart_type": "histogram",
        "x_col": column,
        "y_col": None,
        "bins": bins,
        "table_name": table_name
    }

