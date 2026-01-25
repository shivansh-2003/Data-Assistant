#!/usr/bin/env python3
"""
Data Assistant MCP Server - FastMCP Implementation
Contains MCP tools for data manipulation operations including cleaning, transformation, 
aggregation, feature engineering, and multi-table operations.
"""

from typing import Optional, List, Dict, Any
import numpy as np
import pandas as pd
#from mcp.server.transport_security import TransportSecuritySettings
from fastmcp import FastMCP


# # Determine environment - Render automatically sets RENDER=true
# IS_PRODUCTION = bool(os.environ.get("RENDER")) or os.environ.get("ENVIRONMENT") == "production"

# # Get the Render service URL for allowed hosts
# RENDER_EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL", "")
# RENDER_SERVICE_NAME = os.environ.get("RENDER_SERVICE_NAME", "")

# Import data functions
from .data_functions.core import (
    initialize_table,
    get_data_summary,
    list_available_tables,
    undo_last_operation,
    redo_operation as redo_last_operation
)
from .data_functions.cleaning import (
    drop_rows,
    fill_missing,
    drop_missing,
    replace_values,
    clean_strings,
    remove_outliers,
    detect_missing
)
from .data_functions.selection import (
    select_columns,
    filter_rows,
    sample_rows,
    head_rows,
    tail_rows,
    slice_rows
)
from .data_functions.transformation import (
    rename_columns,
    reorder_columns,
    sort_data,
    apply_custom,
    set_index,
    pivot_table,
    melt_unpivot
)
from .data_functions.aggregation import (
    group_by_agg,
    describe_stats
)
from .data_functions.feature_engineering import (
    create_date_features,
    bin_numeric,
    one_hot_encode,
    scale_numeric,
    create_interaction
)
from .data_functions.multi_table import (
    merge_tables,
    concat_tables,
    merge_on_index
)

# # Configure transport security based on environment
# if IS_PRODUCTION:
#     # In production (Render), allow the Render domain
#     allowed_hosts = [
#         "data-analyst-mcp-server.onrender.com",
#         "*.onrender.com"  # Allow any Render subdomain
#     ]
    
#     # Add RENDER_EXTERNAL_URL if available (e.g., https://your-service.onrender.com)
#     if RENDER_EXTERNAL_URL:
#         # Extract hostname from URL
#         from urllib.parse import urlparse
#         parsed = urlparse(RENDER_EXTERNAL_URL)
#         if parsed.hostname:
#             allowed_hosts.append(parsed.hostname)
    
#     transport_security = TransportSecuritySettings(
#         enabled=True,
#         allowed_hosts=allowed_hosts
#     )
#     print(f"🔒 Production mode: Allowed hosts = {allowed_hosts}")
# else:
#     # In local development, restrict to localhost only
#     transport_security = TransportSecuritySettings(
#         enabled=True,
#         allowed_hosts=["localhost", "127.0.0.1", "0.0.0.0", "localhost:8000", "127.0.0.1:8000", "0.0.0.0:8000"]
#     )
#     print("🔒 Development mode: Localhost only")

# Create FastMCP server
mcp = FastMCP(
    name="Data Assistant MCP Server",
    instructions="""
        This server provides data analysis tools.
    """
)


def _to_serializable(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _to_serializable(val) for key, val in value.items()}
    if isinstance(value, list):
        return [_to_serializable(item) for item in value]
    if isinstance(value, tuple):
        return [_to_serializable(item) for item in value]
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if pd.isna(value):
        return None
    return value

# ============================================================================
# Core Operations
# ============================================================================

@mcp.tool()
def initialize_data_table(session_id: str, table_name: str = "current") -> dict:
    """
    Initialize a data table in session. This should be called first to load data into the session.
    
    Args:
        session_id: Unique session identifier
        table_name: Name for the table (default: "current")
    
    Returns:
        Dictionary with success status and initialization details
    
    Note:
        This loads data from the ingestion API. Use the ingestion API to upload files first.
    """
    try:
        result = initialize_table(session_id, table_name)
        return result
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to initialize table: {str(e)}"
        }


@mcp.tool()
def get_table_summary(session_id: str, table_name: str = "current") -> dict:
    """
    Get summary statistics for a table including row count, column info, data types, and missing values.
    
    Args:
        session_id: Unique session identifier
        table_name: Name of the table (default: "current")
    
    Returns:
        Dictionary containing table summary with rows, columns, dtypes, and missing counts
    
    Example:
        get_table_summary("session_123")
    """
    try:
        result = get_data_summary(session_id, table_name)
        return _to_serializable(result)
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to get table summary: {str(e)}"
        }


@mcp.tool()
def list_tables(session_id: str) -> dict:
    """
    List all available tables in a session.
    
    Args:
        session_id: Unique session identifier
    
    Returns:
        Dictionary containing list of table names
    
    Example:
        list_tables("session_123")
    """
    try:
        tables = list_available_tables(session_id)
        return {
            "success": True,
            "tables": tables,
            "count": len(tables)
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to list tables: {str(e)}"
        }


@mcp.tool()
def undo_operation(session_id: str, table_name: str = "current") -> dict:
    """
    Undo the last operation performed on a table.
    
    Args:
        session_id: Unique session identifier
        table_name: Name of the table (default: "current")
    
    Returns:
        Dictionary with undo result and updated table state
    
    Example:
        undo_operation("session_123")
    """
    try:
        result = undo_last_operation(session_id, table_name)
        return result
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to undo operation: {str(e)}"
        }


@mcp.tool()
def redo_operation(session_id: str, table_name: str = "current") -> dict:
    """
    Redo the last undone operation on a table.
    
    Args:
        session_id: Unique session identifier
        table_name: Name of the table (default: "current")
    
    Returns:
        Dictionary with redo result and updated table state
    
    Example:
        redo_operation("session_123")
    """
    try:
        result = redo_last_operation(session_id, table_name)
        return result
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to redo operation: {str(e)}"
        }


# ============================================================================
# Data Cleaning Operations
# ============================================================================

@mcp.tool()
def drop_rows_from_table(
    session_id: str,
    indices: Optional[List[int]] = None,
    condition: Optional[str] = None,
    subset: Optional[List[str]] = None,
    keep: str = "first",
    table_name: str = "current",
    inplace: bool = True,
    new_table_name: Optional[str] = None
) -> dict:
    """
    Remove rows from a table by index, condition, or duplicates.
    
    Args:
        session_id: Unique session identifier
        indices: List of row indices to drop (optional)
        condition: Boolean condition string (e.g., "Price > 100") (optional)
        subset: Column names for duplicate detection (optional)
        keep: Which duplicates to keep - "first", "last", or False (default: "first")
        table_name: Name of the table (default: "current")
        inplace: If True, overwrite the existing table (default: True)
        new_table_name: Name for the updated table (optional)
    
    Returns:
        Dictionary with operation result and updated table preview
    
    Example:
        drop_rows_from_table("session_123", condition="Price > 1000")
        drop_rows_from_table("session_123", subset=["Company", "Model"], keep="first")
    """
    try:
        result = drop_rows(session_id, indices, condition, subset, keep, table_name, inplace, new_table_name)
        return result
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to drop rows: {str(e)}"
        }


@mcp.tool()
def fill_missing_values(
    session_id: str,
    value: Optional[Any] = None,
    method: Optional[str] = None,
    values: Optional[Dict[str, Any]] = None,
    methods: Optional[Dict[str, str]] = None,
    interpolate_method: Optional[str] = None,
    columns: Optional[List[str]] = None,
    table_name: str = "current"
) -> dict:
    """
    Fill missing (NaN) values in specified columns.
    
    Args:
        session_id: Unique session identifier
        value: Specific value to fill (optional)
        method: Fill method - "ffill", "bfill", "mean", "median", "mode" (optional)
        values: Per-column fill values (optional)
        methods: Per-column fill methods (optional)
        interpolate_method: Interpolation method when using "interpolate" (optional)
        columns: List of column names to fill (optional, fills all columns if not specified)
        table_name: Name of the table (default: "current")
    
    Returns:
        Dictionary with operation result and number of values filled
    
    Example:
        fill_missing_values("session_123", method="mean", columns=["Price"])
        fill_missing_values("session_123", value=0, columns=["Ram", "SSD"])
    """
    try:
        result = fill_missing(
            session_id,
            value,
            method,
            values,
            methods,
            interpolate_method,
            columns,
            table_name
        )
        return result
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to fill missing values: {str(e)}"
        }


@mcp.tool()
def drop_missing_values(
    session_id: str,
    how: str = "any",
    thresh: Optional[int] = None,
    axis: int = 0,
    subset: Optional[List[str]] = None,
    table_name: str = "current"
) -> dict:
    """
    Drop rows or columns with missing values.
    
    Args:
        session_id: Unique session identifier
        how: Drop rows/cols with "any" or "all" missing values (default: "any")
        thresh: Minimum number of non-NA values required (optional)
        axis: 0 for rows, 1 for columns (default: 0)
        subset: Column names to consider (optional)
        table_name: Name of the table (default: "current")
    
    Returns:
        Dictionary with operation result and number of rows/columns dropped
    
    Example:
        drop_missing_values("session_123", how="any")
        drop_missing_values("session_123", thresh=5, subset=["Price", "Ram"])
    """
    try:
        result = drop_missing(session_id, how, thresh, axis, subset, table_name)
        return result
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to drop missing values: {str(e)}"
        }


@mcp.tool()
def replace_table_values(
    session_id: str,
    to_replace: Dict[str, Dict[str, Any]],
    value: Optional[Any] = None,
    regex: bool = False,
    case_insensitive: bool = False,
    table_name: str = "current"
) -> dict:
    """
    Replace specific values in the table.
    
    Args:
        session_id: Unique session identifier
        to_replace: Dictionary mapping column names to replacement dictionaries
                   (e.g., {"Status": {"old": "new"}, "Type": {0: "No", 1: "Yes"}})
        value: Replacement value for all matches (optional)
        regex: Whether to_replace contains regex patterns (default: False)
        case_insensitive: Case-insensitive replacement for string patterns (default: False)
        table_name: Name of the table (default: "current")
    
    Returns:
        Dictionary with operation result
    
    Example:
        replace_table_values("session_123", {"TouchScreen": {0: "No", 1: "Yes"}})
    """
    try:
        result = replace_values(session_id, to_replace, value, regex, case_insensitive, table_name)
        return result
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to replace values: {str(e)}"
        }


@mcp.tool()
def clean_string_columns(
    session_id: str,
    columns: List[str],
    operation: str = "strip",
    operations: Optional[List[str]] = None,
    pattern: Optional[str] = None,
    replacement: str = "",
    case_insensitive: bool = False,
    replace_regex: bool = True,
    table_name: str = "current"
) -> dict:
    """
    Clean string columns (strip whitespace, convert case).
    
    Args:
        session_id: Unique session identifier
        columns: List of column names to clean
        operation: Cleaning operation - "strip", "lower", "upper", "title" (default: "strip")
        operations: Optional list of cleaning operations to apply in order
        pattern: Pattern to replace when using "replace" operation
        replacement: Replacement string for "replace" (default: "")
        case_insensitive: Case-insensitive replace when using "replace" (default: False)
        replace_regex: Treat pattern as regex when using "replace" (default: True)
        table_name: Name of the table (default: "current")
    
    Returns:
        Dictionary with operation result
    
    Example:
        clean_string_columns("session_123", ["Company", "TypeName"], operation="lower")
    """
    try:
        result = clean_strings(
            session_id,
            columns,
            operation,
            operations,
            pattern,
            replacement,
            case_insensitive,
            replace_regex,
            table_name
        )
        return result
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to clean strings: {str(e)}"
        }


@mcp.tool()
def remove_outliers_from_table(
    session_id: str,
    columns: List[str],
    method: str = "iqr",
    threshold: float = 1.5,
    table_name: str = "current",
    handle_method: str = "remove",
    include_boxplot: bool = False
) -> dict:
    """
    Remove outliers from numeric columns using IQR or z-score method.
    
    Args:
        session_id: Unique session identifier
        columns: List of numeric column names
        method: Outlier detection method - "iqr" or "zscore" (default: "iqr")
        threshold: Threshold multiplier for IQR or z-score (default: 1.5)
        table_name: Name of the table (default: "current")
        handle_method: "remove" to drop rows, "cap" or "winsorize" to clamp values (default: "remove")
        include_boxplot: Include boxplot stats in response (default: False)
    
    Returns:
        Dictionary with operation result and number of rows removed
    
    Example:
        remove_outliers_from_table("session_123", ["Price", "Weight"], method="iqr", threshold=2.0)
    """
    try:
        result = remove_outliers(
            session_id,
            columns,
            method,
            threshold,
            table_name,
            handle_method,
            include_boxplot
        )
        return result
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to remove outliers: {str(e)}"
        }


@mcp.tool()
def detect_missing_values(
    session_id: str,
    table_name: str = "current"
) -> dict:
    """
    Summarize missing values per column.
    
    Args:
        session_id: Unique session identifier
        table_name: Name of the table (default: "current")
    
    Returns:
        Dictionary with missing value summary
    """
    try:
        result = detect_missing(session_id, table_name)
        return result
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to detect missing values: {str(e)}"
        }


# ============================================================================
# Selection Operations
# ============================================================================

@mcp.tool()
def select_table_columns(
    session_id: str,
    columns: List[str],
    keep: bool = True,
    table_name: str = "current",
    pattern: Optional[str] = None,
    dtypes: Optional[List[str]] = None,
    case_insensitive: bool = False
) -> dict:
    """
    Select or drop specific columns from a table.
    
    Args:
        session_id: Unique session identifier
        columns: List of column names
        keep: If True, keep these columns; if False, drop these columns (default: True)
        table_name: Name of the table (default: "current")
        pattern: Regex pattern to match columns (optional)
        dtypes: List of dtypes to include (optional, e.g., ["number", "bool", "datetime"])
        case_insensitive: Case-insensitive regex matching (default: False)
    
    Returns:
        Dictionary with operation result and updated column count
    
    Example:
        select_table_columns("session_123", ["Company", "Price", "Ram"], keep=True)
    """
    try:
        result = select_columns(session_id, columns, keep, table_name, pattern, dtypes, case_insensitive)
        return result
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to select columns: {str(e)}"
        }


@mcp.tool()
def filter_table_rows(
    session_id: str,
    condition: str,
    table_name: str = "current",
    variables: Optional[Dict[str, Any]] = None,
    use_query: bool = True
) -> dict:
    """
    Filter rows based on a boolean condition.
    
    Args:
        session_id: Unique session identifier
        condition: Boolean expression string (e.g., "Price > 11.0", "Company == 'Apple'")
        table_name: Name of the table (default: "current")
        variables: Optional variables for query evaluation
        use_query: Use pandas DataFrame.query when True (default: True)
    
    Returns:
        Dictionary with operation result and filtered row count
    
    Example:
        filter_table_rows("session_123", "Price > 11.0")
        filter_table_rows("session_123", "Company == 'Apple' and Ram >= 8")
    """
    try:
        result = filter_rows(session_id, condition, table_name, variables, use_query)
        return result
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to filter rows: {str(e)}"
        }


@mcp.tool()
def sample_table_rows(
    session_id: str,
    n: Optional[int] = None,
    frac: Optional[float] = None,
    random_state: Optional[int] = None,
    table_name: str = "current",
    by: Optional[str] = None,
    replace: bool = False
) -> dict:
    """
    Sample random rows from a table.
    
    Args:
        session_id: Unique session identifier
        n: Number of rows to sample (optional)
        frac: Fraction of rows to sample (0.0 to 1.0) (optional)
        random_state: Random seed for reproducibility (optional)
        table_name: Name of the table (default: "current")
        by: Column name for stratified sampling (optional)
        replace: Sample with replacement (default: False)
    
    Returns:
        Dictionary with operation result and sampled row count
    
    Example:
        sample_table_rows("session_123", n=100, random_state=42)
        sample_table_rows("session_123", frac=0.1)
    """
    try:
        result = sample_rows(session_id, n, frac, random_state, table_name, by, replace)
        return result
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to sample rows: {str(e)}"
        }


@mcp.tool()
def head_table_rows(session_id: str, n: int = 5, table_name: str = "current") -> dict:
    """
    Return the first n rows of a table without modifying it.
    """
    try:
        result = head_rows(session_id, n, table_name)
        return result
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to retrieve head rows: {str(e)}"
        }


@mcp.tool()
def tail_table_rows(session_id: str, n: int = 5, table_name: str = "current") -> dict:
    """
    Return the last n rows of a table without modifying it.
    """
    try:
        result = tail_rows(session_id, n, table_name)
        return result
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to retrieve tail rows: {str(e)}"
        }


@mcp.tool()
def slice_table_rows(
    session_id: str,
    start: int,
    end: Optional[int] = None,
    step: Optional[int] = None,
    table_name: str = "current"
) -> dict:
    """
    Return a slice of rows using iloc without modifying the table.
    """
    try:
        result = slice_rows(session_id, start, end, step, table_name)
        return result
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to slice rows: {str(e)}"
        }


# ============================================================================
# Transformation Operations
# ============================================================================

@mcp.tool()
def rename_table_columns(
    session_id: str,
    mapping: Dict[str, str],
    table_name: str = "current",
    inplace: bool = False,
    new_table_name: Optional[str] = None
) -> dict:
    """
    Rename one or more columns in a table.
    
    Args:
        session_id: Unique session identifier
        mapping: Dictionary mapping old column names to new names
        table_name: Name of the table (default: "current")
        inplace: If True, overwrite the existing table (default: False)
        new_table_name: Name for the renamed table (optional)
    
    Returns:
        Dictionary with operation result
    
    Example:
        rename_table_columns("session_123", {"Company": "Manufacturer", "Price": "Cost"})
    """
    try:
        result = rename_columns(session_id, mapping, table_name, inplace, new_table_name)
        return result
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to rename columns: {str(e)}"
        }


@mcp.tool()
def reorder_table_columns(
    session_id: str,
    columns: List[str],
    table_name: str = "current",
    case_insensitive: bool = False
) -> dict:
    """
    Reorder columns in a table.
    
    Args:
        session_id: Unique session identifier
        columns: List of column names in desired order
        table_name: Name of the table (default: "current")
        case_insensitive: Match column names without case sensitivity (default: False)
    
    Returns:
        Dictionary with operation result
    
    Example:
        reorder_table_columns("session_123", ["Price", "Company", "TypeName"])
    """
    try:
        result = reorder_columns(session_id, columns, table_name, case_insensitive)
        return result
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to reorder columns: {str(e)}"
        }


@mcp.tool()
def sort_table_data(
    session_id: str,
    by: List[str],
    ascending: Any = True,
    table_name: str = "current",
    na_position: str = "last",
    reset_index: bool = False
) -> dict:
    """
    Sort table by one or more columns.
    
    Args:
        session_id: Unique session identifier
        by: List of column names to sort by
        ascending: Sort in ascending order if True, descending if False (default: True)
        table_name: Name of the table (default: "current")
        na_position: Position of NaNs - "first" or "last" (default: "last")
        reset_index: Reset index after sorting (default: False)
    
    Returns:
        Dictionary with operation result
    
    Example:
        sort_table_data("session_123", ["Price"], ascending=False)
        sort_table_data("session_123", ["Company", "Price"])
    """
    try:
        result = sort_data(session_id, by, ascending, table_name, na_position, reset_index)
        return result
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to sort data: {str(e)}"
        }


@mcp.tool()
def apply_custom_function(
    session_id: str,
    column: str,
    function: str,
    new_column: Optional[str] = None,
    table_name: str = "current"
) -> dict:
    """
    Apply a custom function to a column (whitelisted safe operations only).
    
    Args:
        session_id: Unique session identifier
        column: Column name to apply function to
        function: Allowed function name (e.g., "double", "strip", "lower")
        new_column: Name for new column (optional, overwrites original if not specified)
        table_name: Name of the table (default: "current")
    
    Returns:
        Dictionary with operation result
    
    Example:
        apply_custom_function("session_123", "Price", "double", "PriceWithTax")
    """
    try:
        result = apply_custom(session_id, column, function, new_column, table_name)
        return result
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to apply custom function: {str(e)}"
        }


@mcp.tool()
def set_table_index(
    session_id: str,
    columns: Optional[List[str]] = None,
    drop: bool = True,
    reset: bool = False,
    table_name: str = "current"
) -> dict:
    """
    Set or reset the index of a table.
    """
    try:
        result = set_index(session_id, columns, drop, reset, table_name)
        return result
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to update index: {str(e)}"
        }


@mcp.tool()
def pivot_table_data(
    session_id: str,
    index: List[str],
    columns: List[str],
    values: Optional[List[str]] = None,
    aggfunc: str = "mean",
    table_name: str = "current"
) -> dict:
    """
    Create a pivot table from a DataFrame.
    """
    try:
        result = pivot_table(session_id, index, columns, values, aggfunc, table_name)
        return result
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to create pivot table: {str(e)}"
        }


@mcp.tool()
def melt_unpivot_table(
    session_id: str,
    id_vars: List[str],
    value_vars: Optional[List[str]] = None,
    var_name: str = "variable",
    value_name: str = "value",
    table_name: str = "current"
) -> dict:
    """
    Unpivot a table from wide to long format.
    """
    try:
        result = melt_unpivot(session_id, id_vars, value_vars, var_name, value_name, table_name)
        return result
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to unpivot table: {str(e)}"
        }


# ============================================================================
# Aggregation Operations
# ============================================================================

@mcp.tool()
def group_by_aggregate(
    session_id: str,
    by: List[str],
    agg: Dict[str, Any],
    table_name: str = "current",
    as_index: bool = False
) -> dict:
    """
    Group table by columns and compute aggregations.
    """
    try:
        result = group_by_agg(session_id, by, agg, table_name, as_index)
        return result
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to group and aggregate: {str(e)}"
        }


@mcp.tool()
def describe_table_stats(
    session_id: str,
    group_by: Optional[List[str]] = None,
    table_name: str = "current"
) -> dict:
    """
    Get descriptive statistics for columns, optionally grouped.
    """
    try:
        result = describe_stats(session_id, group_by, table_name)
        return result
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to describe statistics: {str(e)}"
        }


# ============================================================================
# Feature Engineering Operations
# ============================================================================

@mcp.tool()
def create_date_features_for_column(
    session_id: str,
    date_column: str,
    features: Optional[List[str]] = None,
    table_name: str = "current",
    date_format: Optional[str] = None
) -> dict:
    """
    Extract date features (year, month, day, weekday, quarter, is_weekend) from a date column.
    """
    try:
        result = create_date_features(session_id, date_column, features, table_name, date_format)
        return result
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to create date features: {str(e)}"
        }


@mcp.tool()
def bin_numeric_column(
    session_id: str,
    column: str,
    bins: int = 4,
    labels: Optional[List[str]] = None,
    qcut: bool = False,
    table_name: str = "current"
) -> dict:
    """
    Bin a numeric column into categories.
    """
    try:
        result = bin_numeric(session_id, column, bins, labels, qcut, table_name)
        return result
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to bin numeric column: {str(e)}"
        }


@mcp.tool()
def one_hot_encode_columns(
    session_id: str,
    columns: List[str],
    drop_first: bool = False,
    table_name: str = "current"
) -> dict:
    """
    One-hot encode categorical columns into binary columns.
    """
    try:
        result = one_hot_encode(session_id, columns, drop_first, table_name)
        return result
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to one-hot encode: {str(e)}"
        }


@mcp.tool()
def scale_numeric_columns(
    session_id: str,
    columns: List[str],
    method: str = "standard",
    table_name: str = "current"
) -> dict:
    """
    Scale numeric columns using a specified method.
    """
    try:
        result = scale_numeric(session_id, columns, method, table_name)
        return result
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to scale numeric columns: {str(e)}"
        }


@mcp.tool()
def create_interaction_column(
    session_id: str,
    col1: str,
    col2: str,
    new_name: str,
    operation: str = "multiply",
    table_name: str = "current"
) -> dict:
    """
    Create interaction feature from two columns.
    """
    try:
        result = create_interaction(session_id, col1, col2, new_name, operation, table_name)
        return result
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to create interaction feature: {str(e)}"
        }


# ============================================================================
# Multi-table Operations
# ============================================================================

@mcp.tool()
def merge_data_tables(
    session_id: str,
    left_table: str,
    right_table: str,
    how: str = "inner",
    left_on: Optional[str] = None,
    right_on: Optional[str] = None,
    on: Optional[str] = None,
    new_table_name: Optional[str] = None,
    suffixes: tuple = ("_left", "_right")
) -> dict:
    """
    Merge two tables using database-style join operation.
    """
    try:
        result = merge_tables(
            session_id,
            left_table,
            right_table,
            how,
            left_on,
            right_on,
            on,
            new_table_name,
            suffixes
        )
        return result
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to merge tables: {str(e)}"
        }


@mcp.tool()
def concat_data_tables(
    session_id: str,
    tables: List[str],
    axis: int = 0,
    join: str = "outer",
    ignore_index: bool = False,
    new_table_name: Optional[str] = None,
    keys: Optional[List[str]] = None
) -> dict:
    """
    Concatenate multiple tables along a particular axis.
    """
    try:
        result = concat_tables(session_id, tables, axis, join, ignore_index, new_table_name, keys)
        return result
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to concatenate tables: {str(e)}"
        }


@mcp.tool()
def merge_tables_on_index(
    session_id: str,
    left_table: str,
    right_table: str,
    how: str = "inner",
    new_table_name: Optional[str] = None,
    suffixes: tuple = ("_left", "_right")
) -> dict:
    """
    Merge two tables using their index values.
    """
    try:
        result = merge_on_index(session_id, left_table, right_table, how, new_table_name, suffixes)
        return result
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to merge tables on index: {str(e)}"
        }

