"""Visualization detection logic for chatbot queries."""

import re
from typing import Tuple, Optional, Dict, Any, List
import pandas as pd


# Explicit visualization keywords
EXPLICIT_VIZ_KEYWORDS = [
    "show", "plot", "graph", "chart", "visualize", "display", "draw",
    "create a chart", "create a graph", "make a chart", "make a graph"
]

# Query pattern keywords for implicit detection
COMPARATIVE_KEYWORDS = ["compare", "comparison", "which", "better", "difference", "top", "rank", "highest", "lowest"]
TREND_KEYWORDS = ["over time", "trend", "change", "growth", "over the", "how has", "how did", "monthly", "yearly", "daily"]
DISTRIBUTION_KEYWORDS = ["distribution", "spread", "frequency", "how are", "distributed", "shape"]
RELATIONSHIP_KEYWORDS = ["relationship", "correlation", "related", "vs", "versus", "against", "between"]
AGGREGATION_KEYWORDS = ["group by", "per", "by category", "aggregate", "total", "sum", "average", "mean"]
PART_TO_WHOLE_KEYWORDS = ["percentage", "proportion", "breakdown", "share", "part of"]


def detect_visualization_need(query: str) -> Tuple[bool, Optional[str]]:
    """
    Detect if visualization is needed based on query text.
    
    Args:
        query: User query string
        
    Returns:
        Tuple of (needs_visualization: bool, chart_type: Optional[str])
    """
    query_lower = query.lower()
    
    # Check for explicit visualization requests
    for keyword in EXPLICIT_VIZ_KEYWORDS:
        if keyword in query_lower:
            # Try to infer chart type from context
            chart_type = _infer_chart_type_from_query(query_lower)
            return True, chart_type or "bar"  # Default to bar if can't infer
    
    # Check for implicit patterns
    if any(keyword in query_lower for keyword in COMPARATIVE_KEYWORDS):
        return True, "bar"
    
    if any(keyword in query_lower for keyword in TREND_KEYWORDS):
        return True, "line"
    
    if any(keyword in query_lower for keyword in DISTRIBUTION_KEYWORDS):
        return True, "histogram"  # Will be adjusted based on data type
    
    if any(keyword in query_lower for keyword in RELATIONSHIP_KEYWORDS):
        return True, "scatter"
    
    if any(keyword in query_lower for keyword in AGGREGATION_KEYWORDS):
        return True, "bar"  # Default for aggregation
    
    if any(keyword in query_lower for keyword in PART_TO_WHOLE_KEYWORDS):
        return True, "pie"
    
    # No visualization needed
    return False, None


def _infer_chart_type_from_query(query: str) -> Optional[str]:
    """Try to infer chart type from explicit visualization request."""
    query_lower = query.lower()
    
    if "bar" in query_lower or "column" in query_lower:
        return "bar"
    if "line" in query_lower:
        return "line"
    if "scatter" in query_lower:
        return "scatter"
    if "histogram" in query_lower or "hist" in query_lower:
        return "histogram"
    if "pie" in query_lower:
        return "pie"
    if "box" in query_lower or "boxplot" in query_lower:
        return "box"
    if "heatmap" in query_lower or "heat map" in query_lower:
        return "heatmap"
    if "area" in query_lower:
        return "area"
    
    return None


def extract_chart_parameters(
    query: str, 
    df: pd.DataFrame, 
    schema: Dict[str, Any],
    chart_type: Optional[str] = None
) -> Dict[str, Any]:
    """
    Extract chart parameters (X, Y, aggregation) from query and data.
    
    Args:
        query: User query
        df: DataFrame to visualize
        schema: Schema information for the DataFrame
        chart_type: Detected or suggested chart type
        
    Returns:
        Dictionary with chart configuration:
        {
            "chart_type": str,
            "x_col": Optional[str],
            "y_col": Optional[str],
            "agg_func": str,
            "color_col": Optional[str]
        }
    """
    query_lower = query.lower()
    columns = list(df.columns)
    column_lower = {col.lower(): col for col in columns}
    
    config = {
        "chart_type": chart_type or "bar",
        "x_col": None,
        "y_col": None,
        "agg_func": "none",
        "color_col": None
    }
    
    # Extract column names mentioned in query
    mentioned_columns = []
    for col_name, original_col in column_lower.items():
        if col_name in query_lower:
            mentioned_columns.append(original_col)
    
    # Get column types from schema
    numeric_cols = schema.get("numeric_columns", [])
    categorical_cols = schema.get("categorical_columns", [])
    datetime_cols = schema.get("datetime_columns", [])
    
    # Extract aggregation function
    if "sum" in query_lower or "total" in query_lower:
        config["agg_func"] = "sum"
    elif "average" in query_lower or "avg" in query_lower or "mean" in query_lower:
        config["agg_func"] = "mean"
    elif "count" in query_lower:
        config["agg_func"] = "count"
    elif "min" in query_lower or "minimum" in query_lower:
        config["agg_func"] = "min"
    elif "max" in query_lower or "maximum" in query_lower:
        config["agg_func"] = "max"
    
    # Determine X and Y based on chart type and data
    if config["chart_type"] == "histogram":
        # Histogram needs one numeric column
        numeric_mentioned = [c for c in mentioned_columns if c in numeric_cols]
        if numeric_mentioned:
            config["x_col"] = numeric_mentioned[0]
        elif numeric_cols:
            config["x_col"] = numeric_cols[0]
    elif config["chart_type"] == "line":
        # Line chart: X should be time/sequence, Y should be numeric
        if datetime_cols:
            config["x_col"] = datetime_cols[0]
        elif mentioned_columns:
            # Use first mentioned column as X
            config["x_col"] = mentioned_columns[0]
        
        numeric_mentioned = [c for c in mentioned_columns if c in numeric_cols]
        if numeric_mentioned:
            config["y_col"] = numeric_mentioned[0]
        elif numeric_cols:
            config["y_col"] = numeric_cols[0]
    elif config["chart_type"] == "scatter":
        # Scatter: both should be numeric
        numeric_mentioned = [c for c in mentioned_columns if c in numeric_cols]
        if len(numeric_mentioned) >= 2:
            config["x_col"] = numeric_mentioned[0]
            config["y_col"] = numeric_mentioned[1]
        elif len(numeric_mentioned) == 1 and len(numeric_cols) >= 2:
            config["x_col"] = numeric_mentioned[0]
            config["y_col"] = numeric_cols[1] if numeric_cols[1] != numeric_mentioned[0] else numeric_cols[0]
        elif len(numeric_cols) >= 2:
            config["x_col"] = numeric_cols[0]
            config["y_col"] = numeric_cols[1]
    elif config["chart_type"] == "pie":
        # Pie chart: categorical column
        categorical_mentioned = [c for c in mentioned_columns if c in categorical_cols]
        if categorical_mentioned:
            config["y_col"] = categorical_mentioned[0]
        elif categorical_cols:
            config["y_col"] = categorical_cols[0]
    else:
        # Bar chart (default): X categorical, Y numeric
        categorical_mentioned = [c for c in mentioned_columns if c in categorical_cols]
        numeric_mentioned = [c for c in mentioned_columns if c in numeric_cols]
        
        if categorical_mentioned:
            config["x_col"] = categorical_mentioned[0]
        elif categorical_cols:
            config["x_col"] = categorical_cols[0]
        elif mentioned_columns:
            config["x_col"] = mentioned_columns[0]
        
        if numeric_mentioned:
            config["y_col"] = numeric_mentioned[0]
        elif numeric_cols:
            config["y_col"] = numeric_cols[0]
    
    return config


def get_chart_type_recommendation(query: str, column_types: Dict[str, str]) -> str:
    """
    Recommend chart type based on query and column types.
    
    Args:
        query: User query
        column_types: Dictionary mapping column names to their types
        
    Returns:
        Recommended chart type string
    """
    needs_viz, suggested_type = detect_visualization_need(query)
    
    if suggested_type:
        return suggested_type
    
    # Default recommendation based on data types
    has_numeric = any("numeric" in str(v).lower() or "float" in str(v).lower() or "int" in str(v).lower() 
                     for v in column_types.values())
    has_categorical = any("object" in str(v).lower() or "category" in str(v).lower() 
                         for v in column_types.values())
    has_datetime = any("datetime" in str(v).lower() or "date" in str(v).lower() 
                      for v in column_types.values())
    
    if has_datetime and has_numeric:
        return "line"
    elif has_categorical and has_numeric:
        return "bar"
    elif has_numeric:
        return "histogram"
    else:
        return "bar"  # Default fallback

