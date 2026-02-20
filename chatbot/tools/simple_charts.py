"""Simple chart tools following LangChain's @tool pattern.

These tools follow LangChain's tool-calling pattern:
https://docs.langchain.com/oss/python/langchain/tools

Key design decisions:
- Tools **only** return a small, JSON-serializable dict that describes the chart
  (type, x/y columns, aggregation, etc.), NOT Plotly figures.
- The actual Plotly figure is built later in the Streamlit UI layer using
  `data_visualization.visualization.generate_chart` so that:
  - The LangGraph checkpoint state stays lightweight and serializable.
  - Frontend code fully controls how charts are rendered and themed.

Execution flow:
  1. Analyzer node binds tools to LLM using `llm.bind_tools(tools)`
  2. LLM selects chart tool based on query (e.g., bar_chart, line_chart)
  3. Tool returns config dict (executed in analyzer via LLM function calling)
  4. `viz_node` validates and stores config in state["viz_config"]
  5. Streamlit UI renders Plotly figure from config

As a developer: think of these as \"intent + config\" tools, not direct Plotly
wrappers. Unlike LangChain's ToolNode (which auto-executes), we use specialized
execution in `viz_node` for validation and state management.
"""

from langchain_core.tools import tool
from typing import Optional


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
        Dict with chart configuration (JSON-serializable). The actual Plotly
        figure is created later in the Streamlit UI from this config.
        
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
        Dict with chart configuration (JSON-serializable). The actual Plotly
        figure is created later in the Streamlit UI from this config.
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
        Dict with chart configuration (JSON-serializable). The actual Plotly
        figure is created later in the Streamlit UI from this config.
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
        Dict with chart configuration (JSON-serializable). The actual Plotly
        figure is created later in the Streamlit UI from this config.
    """
    return {
        "tool": "histogram",
        "chart_type": "histogram",
        "x_col": column,
        "y_col": None,
        "bins": bins,
        "table_name": table_name
    }


@tool
def area_chart(x_col: str, y_col: str, agg_func: str = "sum", color_col: Optional[str] = None, table_name: str = "current") -> dict:
    """
    Create an area chart for cumulative values and trends.
    
    Use for:
    - Cumulative values over time
    - Stacked area comparisons
    - Trend visualization with filled areas
    
    Args:
        x_col: Column name for X-axis (usually time/date)
        y_col: Column name for Y-axis (numeric)
        agg_func: Aggregation function (sum, mean, median, etc.)
        color_col: Optional column for stacked areas
        table_name: Name of the table to use
        
    Returns:
        Dict with chart configuration (JSON-serializable). The actual Plotly
        figure is created later in the Streamlit UI from this config.
    """
    return {
        "tool": "area_chart",
        "chart_type": "area",
        "x_col": x_col,
        "y_col": y_col,
        "agg_func": agg_func,
        "color_col": color_col,
        "table_name": table_name
    }


@tool
def box_chart(y_col: str, x_col: Optional[str] = None, color_col: Optional[str] = None, table_name: str = "current") -> dict:
    """
    Create a box plot for distribution analysis and outlier detection.
    
    Use for:
    - Distribution comparison across categories
    - Outlier detection
    - Statistical summary visualization
    - Comparing distributions
    
    Args:
        y_col: Column name for Y-axis (numeric) - REQUIRED
        x_col: Optional categorical column for grouping
        color_col: Optional column for color grouping
        table_name: Name of the table to use
        
    Returns:
        Dict with chart configuration (JSON-serializable). The actual Plotly
        figure is created later in the Streamlit UI from this config.
    """
    return {
        "tool": "box_chart",
        "chart_type": "box",
        "x_col": x_col,
        "y_col": y_col,
        "color_col": color_col,
        "table_name": table_name
    }


@tool
def heatmap_chart(columns: list, table_name: str = "current") -> dict:
    """
    Create a heatmap for correlation matrices or pivot tables.
    
    Use for:
    - Correlation matrix visualization
    - Pivot table heatmaps
    - Multi-column relationship analysis
    
    Args:
        columns: List of column names (2+ required, numeric for correlation matrix)
        table_name: Name of the table to use
        
    Returns:
        Dict with chart configuration (JSON-serializable). The actual Plotly
        figure is created later in the Streamlit UI from this config.
    """
    return {
        "tool": "heatmap_chart",
        "chart_type": "heatmap",
        "heatmap_columns": columns,
        "table_name": table_name
    }


@tool
def correlation_matrix(table_name: str = "current") -> dict:
    """
    Create a correlation matrix heatmap for all numeric columns.
    
    Use for:
    - Quick correlation overview
    - Finding relationships between numeric variables
    - Data exploration
    
    Args:
        table_name: Name of the table to use
        
    Returns:
        Dict with chart configuration (auto-selects all numeric columns).
        The actual correlation heatmap is generated later in the UI using
        `df.corr()` and Plotly based on this config.
    """
    return {
        "tool": "correlation_matrix",
        "chart_type": "heatmap",
        "heatmap_columns": "auto",  # Special marker for auto-selection
        "table_name": table_name
    }

