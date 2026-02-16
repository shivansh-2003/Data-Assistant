"""Format data profile for prompt injection and chart selection."""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def format_profile_for_prompt(data_profile: Dict[str, Any], max_columns: int = 20) -> str:
    """
    Format data profile into compressed string for prompt injection.
    
    Format: "Table: col1 (numeric, 100 unique, 5% missing, mean=10.5); col2 (categorical, 5 unique, low cardinality, top: A=50, B=30)"
    
    Args:
        data_profile: Full profile dict from get_session_profile
        max_columns: Maximum columns per table to include
        
    Returns:
        Compressed string representation
    """
    if not data_profile or not data_profile.get("tables"):
        return "No data profile available."
    
    lines = []
    tables = data_profile.get("tables", {})
    
    for table_name, table_data in tables.items():
        columns = table_data.get("columns", {})
        if not columns:
            continue
        
        table_lines = [f"Table '{table_name}':"]
        
        # Limit columns to prevent prompt bloat
        col_items = list(columns.items())[:max_columns]
        
        for col_name, col_info in col_items:
            parts = [col_name]
            
            # Type and basic stats
            dtype = col_info.get("dtype", "unknown")
            n_unique = col_info.get("n_unique", 0)
            missing_pct = col_info.get("missing_pct", 0.0)
            
            type_label = "numeric" if col_info.get("is_numeric") else "categorical" if col_info.get("is_categorical") else dtype
            parts.append(f"({type_label}, {n_unique} unique, {missing_pct}% missing")
            
            # Cardinality
            cardinality = col_info.get("cardinality", "unknown")
            if cardinality != "unknown":
                parts.append(f", {cardinality} cardinality")
            
            # Numeric stats (compressed)
            if col_info.get("is_numeric") and col_info.get("numeric_stats"):
                stats = col_info["numeric_stats"]
                parts.append(f", mean={stats.get('mean', 0):.2f}, range=[{stats.get('min', 0):.2f}-{stats.get('max', 0):.2f}]")
            
            # Top categories (compressed)
            if col_info.get("is_categorical") and col_info.get("top_categories"):
                top_cats = col_info["top_categories"]
                top_3 = list(top_cats.items())[:3]
                cat_str = ", ".join([f"{k}={v}" for k, v in top_3])
                parts.append(f", top: {cat_str}")
            
            parts.append(")")
            table_lines.append(" ".join(parts))
        
        if len(columns) > max_columns:
            table_lines.append(f"... ({len(columns) - max_columns} more columns)")
        
        lines.extend(table_lines)
    
    return "\n".join(lines)


def get_column_profile(
    data_profile: Dict[str, Any],
    table_name: str,
    column_name: str
) -> Optional[Dict[str, Any]]:
    """
    Get profile for a specific column.
    
    Args:
        data_profile: Full profile dict
        table_name: Table name
        column_name: Column name
        
    Returns:
        Column profile dict or None
    """
    if not data_profile or not data_profile.get("tables"):
        return None
    
    tables = data_profile.get("tables", {})
    if table_name not in tables:
        return None
    
    columns = tables[table_name].get("columns", {})
    return columns.get(column_name)


def is_suitable_for_chart(
    data_profile: Dict[str, Any],
    table_name: str,
    column_name: str,
    chart_type: str
) -> tuple[bool, Optional[str]]:
    """
    Check if column is suitable for specific chart type based on profile.
    
    Args:
        data_profile: Full profile dict
        table_name: Table name
        column_name: Column name
        chart_type: Chart type (bar, pie, line, scatter, histogram, etc.)
        
    Returns:
        Tuple of (is_suitable, reason)
    """
    col_profile = get_column_profile(data_profile, table_name, column_name)
    if not col_profile:
        return True, None  # Can't validate, allow
    
    cardinality = col_profile.get("cardinality", "high")
    n_unique = col_profile.get("n_unique", 0)
    is_numeric = col_profile.get("is_numeric", False)
    is_categorical = col_profile.get("is_categorical", False)
    
    # Bar chart: low-medium cardinality categorical
    if chart_type in ("bar", "bar_chart"):
        if not is_categorical:
            return False, f"Bar chart requires categorical data, but {column_name} is numeric"
        if cardinality == "high" and n_unique > 25:
            return False, f"Bar chart unsuitable: {column_name} has {n_unique} unique values (max 25 recommended)"
        return True, None
    
    # Pie chart: low cardinality categorical
    if chart_type in ("pie", "pie_chart"):
        if not is_categorical:
            return False, f"Pie chart requires categorical data, but {column_name} is numeric"
        if n_unique > 10:
            return False, f"Pie chart unsuitable: {column_name} has {n_unique} unique values (max 10 recommended)"
        return True, None
    
    # Line chart: time series or numeric with order
    if chart_type in ("line", "line_chart"):
        if is_categorical and cardinality == "high":
            return False, f"Line chart unsuitable: {column_name} is high-cardinality categorical"
        return True, None
    
    # Histogram: numeric
    if chart_type in ("histogram", "hist"):
        if not is_numeric:
            return False, f"Histogram requires numeric data, but {column_name} is categorical"
        return True, None
    
    # Scatter: numeric vs numeric
    if chart_type in ("scatter", "scatter_chart"):
        if not is_numeric:
            return False, f"Scatter chart requires numeric data, but {column_name} is categorical"
        return True, None
    
    # Box plot: numeric
    if chart_type in ("box", "box_chart"):
        if not is_numeric:
            return False, f"Box plot requires numeric data, but {column_name} is categorical"
        return True, None
    
    return True, None
