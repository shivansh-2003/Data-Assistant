"""Smart auto-chart selection based on data characteristics."""

import logging
from typing import Dict, Any, Optional, List, Tuple
import pandas as pd

logger = logging.getLogger(__name__)


def detect_column_type(df: pd.DataFrame, col: str) -> str:
    """
    Detect column type: 'datetime', 'numeric', 'categorical', 'boolean'.
    
    Args:
        df: DataFrame
        col: Column name
        
    Returns:
        Column type string
    """
    if col not in df.columns:
        return "unknown"
    
    dtype = df[col].dtype
    
    if pd.api.types.is_datetime64_any_dtype(dtype):
        return "datetime"
    elif pd.api.types.is_numeric_dtype(dtype):
        return "numeric"
    elif pd.api.types.is_bool_dtype(dtype):
        return "boolean"
    else:
        return "categorical"


def get_cardinality(df: pd.DataFrame, col: str) -> int:
    """Get number of unique values in a column."""
    if col not in df.columns:
        return 0
    return df[col].nunique()


def auto_select_chart(
    df: pd.DataFrame,
    x_col: Optional[str] = None,
    y_col: Optional[str] = None,
    query_intent: Optional[str] = None,
    data_profile: Optional[Dict[str, Any]] = None
) -> Tuple[str, Dict[str, Any]]:
    """
    Automatically select the best chart type based on data characteristics.
    
    Rules:
    - If time column → line chart
    - If categorical with low cardinality (< 25) → bar chart
    - If numeric vs numeric → scatter chart
    - If single numeric → histogram or box plot
    - If correlation query → correlation matrix or scatter
    
    Args:
        df: DataFrame to analyze
        x_col: Optional X column name
        y_col: Optional Y column name
        query_intent: Query intent (e.g., "correlate", "trend", "compare")
        data_profile: Optional data profile with n_unique, dtype per column
        
    Returns:
        Tuple of (chart_type, config_dict)
    """
    if df is None or df.empty:
        return "bar", {"x_col": x_col, "y_col": y_col}
    
    # Use data_profile if available, otherwise compute on-the-fly
    def get_col_info(col: str) -> Dict[str, Any]:
        if data_profile and col:
            tables = data_profile.get("tables", {})
            for table_data in tables.values():
                cols = table_data.get("columns", {})
                if col in cols:
                    return cols[col]
        # Fallback: compute from DataFrame
        if col and col in df.columns:
            s = df[col]
            n_unique = get_cardinality(df, col)
            return {
                "dtype": str(s.dtype),
                "n_unique": n_unique,
                "is_numeric": pd.api.types.is_numeric_dtype(s),
                "is_categorical": pd.api.types.is_categorical_dtype(s) or (
                    not pd.api.types.is_numeric_dtype(s) and 
                    not pd.api.types.is_datetime64_any_dtype(s)
                ),
                "cardinality": "low" if n_unique < 10 else ("medium" if n_unique < 100 else "high"),
            }
        return {}
    
    # Rule 1: Correlation intent → correlation matrix or scatter
    if query_intent == "correlate":
        if x_col and y_col:
            x_info = get_col_info(x_col)
            y_info = get_col_info(y_col)
            if x_info.get("dtype", "").startswith(("int", "float")) and \
               y_info.get("dtype", "").startswith(("int", "float")):
                return "scatter", {"x_col": x_col, "y_col": y_col}
        # No specific columns → correlation matrix
        return "correlation_matrix", {}
    
    # Rule 2: Trend intent or datetime X → line chart
    if query_intent == "trend" or (x_col and detect_column_type(df, x_col) == "datetime"):
        if y_col:
            return "line", {"x_col": x_col, "y_col": y_col, "agg_func": "mean"}
        return "line", {"x_col": x_col, "y_col": df.select_dtypes(include=['number']).columns[0] if len(df.select_dtypes(include=['number']).columns) > 0 else None}
    
    # Rule 3: Compare intent or categorical X with low cardinality → bar chart
    if query_intent == "compare" or (x_col and detect_column_type(df, x_col) == "categorical"):
        x_info = get_col_info(x_col)
        n_unique = x_info.get("n_unique", get_cardinality(df, x_col))
        if n_unique <= 25:
            if y_col:
                return "bar", {"x_col": x_col, "y_col": y_col, "agg_func": "mean"}
            return "bar", {"x_col": x_col, "agg_func": "count"}
    
    # Rule 4: Distribution intent or single numeric → histogram or box
    if query_intent == "distribution" or (y_col and not x_col):
        y_info = get_col_info(y_col)
        if y_info.get("dtype", "").startswith(("int", "float")):
            # Use box if we have a grouping column, histogram otherwise
            if x_col:
                return "box", {"x_col": x_col, "y_col": y_col}
            return "histogram", {"column": y_col}
    
    # Rule 5: Numeric vs numeric → scatter
    if x_col and y_col:
        x_info = get_col_info(x_col)
        y_info = get_col_info(y_col)
        if x_info.get("dtype", "").startswith(("int", "float")) and \
           y_info.get("dtype", "").startswith(("int", "float")):
            return "scatter", {"x_col": x_col, "y_col": y_col}
    
    # Rule 6: Categorical X with high cardinality (> 25) → histogram of Y or box plot
    if x_col:
        x_info = get_col_info(x_col)
        n_unique = x_info.get("n_unique", get_cardinality(df, x_col))
        if n_unique > 25 and y_col:
            return "box", {"x_col": x_col, "y_col": y_col}
    
    # Default fallback
    if x_col and y_col:
        return "bar", {"x_col": x_col, "y_col": y_col, "agg_func": "mean"}
    elif x_col:
        return "bar", {"x_col": x_col, "agg_func": "count"}
    elif y_col:
        return "histogram", {"column": y_col}
    else:
        # No columns specified → bar chart of first categorical or histogram of first numeric
        numeric_cols = df.select_dtypes(include=['number']).columns
        if len(numeric_cols) > 0:
            return "histogram", {"column": numeric_cols[0]}
        return "bar", {"x_col": df.columns[0] if len(df.columns) > 0 else None, "agg_func": "count"}


def suggest_chart_for_query(
    query: str,
    schema: Dict[str, Any],
    data_profile: Optional[Dict[str, Any]] = None,
    mentioned_columns: Optional[List[str]] = None
) -> Optional[Dict[str, Any]]:
    """
    Suggest a chart configuration based on query text and schema.
    
    This is a rule-based fallback when LLM tool selection fails or needs validation.
    
    Args:
        query: User query text
        schema: Schema dictionary
        data_profile: Optional data profile
        mentioned_columns: List of column names mentioned in query
        
    Returns:
        Chart config dict or None if no suggestion
    """
    query_lower = query.lower()
    
    # Extract column names from schema
    all_columns = []
    tables = schema.get("tables", {})
    for table_data in tables.values():
        if isinstance(table_data, dict) and "columns" in table_data:
            all_columns.extend(table_data["columns"])
    
    if not all_columns:
        return None
    
    # Match mentioned columns
    x_col = None
    y_col = None
    
    if mentioned_columns:
        # Try to find columns matching mentions
        for mention in mentioned_columns[:2]:
            matches = [c for c in all_columns if mention.lower() in c.lower() or c.lower() in mention.lower()]
            if matches:
                if not x_col:
                    x_col = matches[0]
                elif not y_col:
                    y_col = matches[0]
    
    # Intent detection from query keywords
    intent = None
    if any(word in query_lower for word in ["correlat", "relationship", "relationship between"]):
        intent = "correlate"
    elif any(word in query_lower for word in ["trend", "over time", "time series"]):
        intent = "trend"
    elif any(word in query_lower for word in ["compare", "comparison", "difference"]):
        intent = "compare"
    elif any(word in query_lower for word in ["distribut", "spread", "range"]):
        intent = "distribution"
    
    # If we have columns, use auto-select logic (would need DataFrame, but we can infer from profile)
    if x_col and y_col and data_profile:
        # Infer chart type from profile
        tables = data_profile.get("tables", {})
        for table_data in tables.values():
            cols = table_data.get("columns", {})
            if x_col in cols and y_col in cols:
                x_info = cols[x_col]
                y_info = cols[y_col]
                
                # Numeric vs numeric → scatter
                if "int" in x_info.get("dtype", "") or "float" in x_info.get("dtype", ""):
                    if "int" in y_info.get("dtype", "") or "float" in y_info.get("dtype", ""):
                        return {"chart_type": "scatter", "x_col": x_col, "y_col": y_col}
                
                # Categorical X, numeric Y → bar
                if x_info.get("n_unique", 100) <= 25:
                    return {"chart_type": "bar", "x_col": x_col, "y_col": y_col, "agg_func": "mean"}
    
    # Correlation query without columns → correlation matrix
    if intent == "correlate" and not x_col:
        return {"chart_type": "correlation_matrix"}
    
    # Trend query → line
    if intent == "trend" and x_col and y_col:
        return {"chart_type": "line", "x_col": x_col, "y_col": y_col}
    
    # Compare query → bar
    if intent == "compare" and x_col:
        return {"chart_type": "bar", "x_col": x_col, "y_col": y_col, "agg_func": "mean"}
    
    return None
