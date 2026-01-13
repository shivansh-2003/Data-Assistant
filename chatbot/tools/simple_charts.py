"""Simple chart tools wrapping existing visualization module."""

from langchain_core.tools import tool
from typing import Optional
import plotly.graph_objects as go


@tool
def bar_chart(x_col: str, y_col: Optional[str] = None, agg_func: str = "count", color_col: Optional[str] = None, table_name: str = "current") -> dict:
    """
    Create a bar chart for categorical comparisons.
    
    Use for:
    - Comparing values across categories (e.g., "average Price by Company")
    - Top N rankings
    - Grouped comparisons
    
    Args:
        x_col: Column name for X-axis (categorical) - REQUIRED
        y_col: Column name for Y-axis (numeric) - optional, defaults to count
        agg_func: Aggregation function (count, sum, mean, median, min, max)
        color_col: Optional column for color grouping
        table_name: Name of the table to use
        
    Returns:
        Dict with chart configuration
        
    Example:
        bar_chart(x_col="Company", y_col="Price", agg_func="mean")
    """
    return {
        "tool": "bar_chart",
        "chart_type": "bar",
        "x_col": x_col,
        "y_col": y_col,
        "agg_func": agg_func,
        "color_col": color_col,
        "table_name": table_name
    }


@tool
def line_chart(x_col: str, y_col: str, agg_func: str = "mean", color_col: Optional[str] = None, table_name: str = "current") -> dict:
    """
    Create a line chart for trends over time.
    
    Use for:
    - Time series analysis
    - Trend visualization
    - Change over time
    
    Args:
        x_col: Column name for X-axis (usually date/time)
        y_col: Column name for Y-axis (numeric)
        agg_func: Aggregation function (mean, sum, median, etc.)
        color_col: Optional column for multiple lines
        table_name: Name of the table to use
        
    Returns:
        Dict with chart configuration
    """
    return {
        "tool": "line_chart",
        "chart_type": "line",
        "x_col": x_col,
        "y_col": y_col,
        "agg_func": agg_func,
        "color_col": color_col,
        "table_name": table_name
    }


@tool
def scatter_chart(x_col: str, y_col: str, color_col: Optional[str] = None, size_col: Optional[str] = None, table_name: str = "current") -> dict:
    """
    Create a scatter plot for relationship analysis.
    
    Use for:
    - Correlation visualization
    - X vs Y relationships
    - Pattern detection
    
    Args:
        x_col: Column name for X-axis (numeric)
        y_col: Column name for Y-axis (numeric)
        color_col: Optional column for color grouping
        size_col: Optional column for bubble size
        table_name: Name of the table to use
        
    Returns:
        Dict with chart configuration
    """
    return {
        "tool": "scatter_chart",
        "chart_type": "scatter",
        "x_col": x_col,
        "y_col": y_col,
        "color_col": color_col,
        "size_col": size_col,
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

