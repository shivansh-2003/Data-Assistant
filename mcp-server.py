#!/usr/bin/env python3
"""
Data Assistant MCP Server - FastMCP Implementation
Contains MCP tools for data manipulation operations including cleaning, transformation, 
aggregation, feature engineering, and multi-table operations.
"""

import os
from typing import Optional, List, Dict, Any
from mcp.server.fastmcp import FastMCP

# Import data-mcp functions
# Handle package import with dash in folder name
import sys
import importlib.util
import types

# Load the data-mcp package
data_mcp_dir = os.path.join(os.path.dirname(__file__), 'data-mcp')
sys.path.insert(0, data_mcp_dir)

# Create package structure
data_mcp_pkg = types.ModuleType('data_mcp')
sys.modules['data_mcp'] = data_mcp_pkg

# Load all modules
module_names = ['core', 'cleaning', 'selection', 'transformation', 'aggregation', 'feature_engineering', 'multi_table']
modules = {}

for module_name in module_names:
    module_file = os.path.join(data_mcp_dir, f'{module_name}.py')
    spec = importlib.util.spec_from_file_location(f'data_mcp.{module_name}', module_file)
    module = importlib.util.module_from_spec(spec)
    module.__package__ = 'data_mcp'
    sys.modules[f'data_mcp.{module_name}'] = module
    setattr(data_mcp_pkg, module_name, module)
    spec.loader.exec_module(module)
    modules[module_name] = module

# Import functions from modules
from data_mcp.core import (
    initialize_table,
    get_data_summary,
    list_available_tables,
    undo_last_operation,
    redo_operation
)
from data_mcp.cleaning import (
    drop_rows,
    fill_missing,
    drop_missing,
    replace_values,
    clean_strings,
    remove_outliers
)
from data_mcp.selection import (
    select_columns,
    filter_rows,
    sample_rows
)
from data_mcp.transformation import (
    rename_columns,
    reorder_columns,
    sort_data,
    set_index,
    pivot_table,
    melt_unpivot,
    apply_custom
)
from data_mcp.aggregation import (
    group_by_agg,
    describe_stats
)
from data_mcp.feature_engineering import (
    create_date_features,
    bin_numeric,
    one_hot_encode,
    scale_numeric,
    create_interaction
)
from data_mcp.multi_table import (
    merge_tables,
    concat_tables
)

# Create FastMCP server
mcp = FastMCP("Data Assistant MCP Server", stateless_http=True)

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
        This is typically called after loading data from a file. Use the ingestion API to upload files first.
    """
    try:
        # This is a placeholder - in practice, you'd load the DataFrame from the ingestion API
        # For now, we'll return an error directing users to upload data first
        return {
            "success": False,
            "error": "Please upload data first using the ingestion API endpoint. This tool is used internally after data upload."
        }
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
        return result
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
        result = redo_operation(session_id, table_name)
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
    table_name: str = "current"
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
    
    Returns:
        Dictionary with operation result and updated table preview
    
    Example:
        drop_rows_from_table("session_123", condition="Price > 1000")
        drop_rows_from_table("session_123", subset=["Company", "Model"], keep="first")
    """
    try:
        result = drop_rows(session_id, indices, condition, subset, keep, table_name)
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
    columns: Optional[List[str]] = None,
    table_name: str = "current"
) -> dict:
    """
    Fill missing (NaN) values in specified columns.
    
    Args:
        session_id: Unique session identifier
        value: Specific value to fill (optional)
        method: Fill method - "ffill", "bfill", "mean", "median", "mode" (optional)
        columns: List of column names to fill (optional, fills all columns if not specified)
        table_name: Name of the table (default: "current")
    
    Returns:
        Dictionary with operation result and number of values filled
    
    Example:
        fill_missing_values("session_123", method="mean", columns=["Price"])
        fill_missing_values("session_123", value=0, columns=["Ram", "SSD"])
    """
    try:
        result = fill_missing(session_id, value, method, columns, table_name)
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
        table_name: Name of the table (default: "current")
    
    Returns:
        Dictionary with operation result
    
    Example:
        replace_table_values("session_123", {"TouchScreen": {0: "No", 1: "Yes"}})
    """
    try:
        result = replace_values(session_id, to_replace, value, regex, table_name)
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
    table_name: str = "current"
) -> dict:
    """
    Clean string columns (strip whitespace, convert case).
    
    Args:
        session_id: Unique session identifier
        columns: List of column names to clean
        operation: Cleaning operation - "strip", "lower", "upper", "title" (default: "strip")
        table_name: Name of the table (default: "current")
    
    Returns:
        Dictionary with operation result
    
    Example:
        clean_string_columns("session_123", ["Company", "TypeName"], operation="lower")
    """
    try:
        result = clean_strings(session_id, columns, operation, table_name)
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
    table_name: str = "current"
) -> dict:
    """
    Remove outliers from numeric columns using IQR or z-score method.
    
    Args:
        session_id: Unique session identifier
        columns: List of numeric column names
        method: Outlier detection method - "iqr" or "zscore" (default: "iqr")
        threshold: Threshold multiplier for IQR or z-score (default: 1.5)
        table_name: Name of the table (default: "current")
    
    Returns:
        Dictionary with operation result and number of rows removed
    
    Example:
        remove_outliers_from_table("session_123", ["Price", "Weight"], method="iqr", threshold=2.0)
    """
    try:
        result = remove_outliers(session_id, columns, method, threshold, table_name)
        return result
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to remove outliers: {str(e)}"
        }


# ============================================================================
# Selection Operations
# ============================================================================

@mcp.tool()
def select_table_columns(
    session_id: str,
    columns: List[str],
    keep: bool = True,
    table_name: str = "current"
) -> dict:
    """
    Select or drop specific columns from a table.
    
    Args:
        session_id: Unique session identifier
        columns: List of column names
        keep: If True, keep these columns; if False, drop these columns (default: True)
        table_name: Name of the table (default: "current")
    
    Returns:
        Dictionary with operation result and updated column count
    
    Example:
        select_table_columns("session_123", ["Company", "Price", "Ram"], keep=True)
    """
    try:
        result = select_columns(session_id, columns, keep, table_name)
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
    table_name: str = "current"
) -> dict:
    """
    Filter rows based on a boolean condition.
    
    Args:
        session_id: Unique session identifier
        condition: Boolean expression string (e.g., "Price > 11.0", "Company == 'Apple'")
        table_name: Name of the table (default: "current")
    
    Returns:
        Dictionary with operation result and filtered row count
    
    Example:
        filter_table_rows("session_123", "Price > 11.0")
        filter_table_rows("session_123", "Company == 'Apple' and Ram >= 8")
    """
    try:
        result = filter_rows(session_id, condition, table_name)
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
    table_name: str = "current"
) -> dict:
    """
    Sample random rows from a table.
    
    Args:
        session_id: Unique session identifier
        n: Number of rows to sample (optional)
        frac: Fraction of rows to sample (0.0 to 1.0) (optional)
        random_state: Random seed for reproducibility (optional)
        table_name: Name of the table (default: "current")
    
    Returns:
        Dictionary with operation result and sampled row count
    
    Example:
        sample_table_rows("session_123", n=100, random_state=42)
        sample_table_rows("session_123", frac=0.1)
    """
    try:
        result = sample_rows(session_id, n, frac, random_state, table_name)
        return result
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to sample rows: {str(e)}"
        }


# ============================================================================
# Transformation Operations
# ============================================================================

@mcp.tool()
def rename_table_columns(
    session_id: str,
    mapping: Dict[str, str],
    table_name: str = "current"
) -> dict:
    """
    Rename one or more columns in a table.
    
    Args:
        session_id: Unique session identifier
        mapping: Dictionary mapping old column names to new names
        table_name: Name of the table (default: "current")
    
    Returns:
        Dictionary with operation result
    
    Example:
        rename_table_columns("session_123", {"Company": "Manufacturer", "Price": "Cost"})
    """
    try:
        result = rename_columns(session_id, mapping, table_name)
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
    table_name: str = "current"
) -> dict:
    """
    Reorder columns in a table.
    
    Args:
        session_id: Unique session identifier
        columns: List of column names in desired order
        table_name: Name of the table (default: "current")
    
    Returns:
        Dictionary with operation result
    
    Example:
        reorder_table_columns("session_123", ["Price", "Company", "TypeName"])
    """
    try:
        result = reorder_columns(session_id, columns, table_name)
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
    ascending: bool = True,
    table_name: str = "current"
) -> dict:
    """
    Sort table by one or more columns.
    
    Args:
        session_id: Unique session identifier
        by: List of column names to sort by
        ascending: Sort in ascending order if True, descending if False (default: True)
        table_name: Name of the table (default: "current")
    
    Returns:
        Dictionary with operation result
    
    Example:
        sort_table_data("session_123", ["Price"], ascending=False)
        sort_table_data("session_123", ["Company", "Price"])
    """
    try:
        result = sort_data(session_id, by, ascending, table_name)
        return result
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to sort data: {str(e)}"
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
    Set or reset index column(s) for a table.
    
    Args:
        session_id: Unique session identifier
        columns: List of column names to set as index (optional, required if reset=False)
        drop: Drop original columns when setting index (default: True)
        reset: If True, reset index instead of setting it (default: False)
        table_name: Name of the table (default: "current")
    
    Returns:
        Dictionary with operation result
    
    Example:
        set_table_index("session_123", columns=["Company", "Model"])
        set_table_index("session_123", reset=True)
    """
    try:
        result = set_index(session_id, columns, drop, reset, table_name)
        return result
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to set index: {str(e)}"
        }


@mcp.tool()
def create_pivot_table(
    session_id: str,
    index: List[str],
    columns: Optional[List[str]] = None,
    values: Optional[List[str]] = None,
    aggfunc: str = "sum",
    table_name: str = "current"
) -> dict:
    """
    Create a pivot table summary.
    
    Args:
        session_id: Unique session identifier
        index: Column names for index
        columns: Column names for columns (optional)
        values: Column names for values (optional)
        aggfunc: Aggregation function - "sum", "mean", "count", "min", "max", "std", "median" (default: "sum")
        table_name: Name of the table (default: "current")
    
    Returns:
        Dictionary with operation result and pivot table
    
    Example:
        create_pivot_table("session_123", index=["Company"], values=["Price"], aggfunc="mean")
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
    Unpivot (melt) wide data to long format.
    
    Args:
        session_id: Unique session identifier
        id_vars: Column names to keep as identifiers
        value_vars: Column names to unpivot (optional, unpivots all non-id columns if not specified)
        var_name: Name for the new variable column (default: "variable")
        value_name: Name for the new value column (default: "value")
        table_name: Name of the table (default: "current")
    
    Returns:
        Dictionary with operation result and unpivoted table
    
    Example:
        melt_unpivot_table("session_123", id_vars=["Company"], value_vars=["Price", "Ram"])
    """
    try:
        result = melt_unpivot(session_id, id_vars, value_vars, var_name, value_name, table_name)
        return result
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to melt/unpivot table: {str(e)}"
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
        function: Lambda function string (e.g., "lambda x: x * 2", "lambda x: abs(x)")
        new_column: Name for new column (optional, overwrites original if not specified)
        table_name: Name of the table (default: "current")
    
    Returns:
        Dictionary with operation result
    
    Example:
        apply_custom_function("session_123", "Price", "lambda x: x * 1.1", "PriceWithTax")
    """
    try:
        result = apply_custom(session_id, column, function, new_column, table_name)
        return result
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to apply custom function: {str(e)}"
        }


# ============================================================================
# Aggregation Operations
# ============================================================================

@mcp.tool()
def group_by_aggregate(
    session_id: str,
    by: List[str],
    agg: Dict[str, str],
    table_name: str = "current"
) -> dict:
    """
    Group table by columns and compute aggregations.
    
    Args:
        session_id: Unique session identifier
        by: Column names to group by
        agg: Dictionary mapping column names to aggregation functions
             (e.g., {"Price": "mean", "Ram": "sum"})
             Supported functions: "sum", "mean", "count", "min", "max", "std", "median"
        table_name: Name of the table (default: "current")
    
    Returns:
        Dictionary with operation result and aggregated table
    
    Example:
        group_by_aggregate("session_123", by=["Company"], agg={"Price": "mean", "Ram": "mean"})
    """
    try:
        result = group_by_agg(session_id, by, agg, table_name)
        return result
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to group by and aggregate: {str(e)}"
        }


@mcp.tool()
def describe_table_statistics(
    session_id: str,
    group_by: Optional[List[str]] = None,
    table_name: str = "current"
) -> dict:
    """
    Get descriptive statistics for numeric columns, optionally grouped.
    
    Args:
        session_id: Unique session identifier
        group_by: Column names to group by (optional)
        table_name: Name of the table (default: "current")
    
    Returns:
        Dictionary with operation result and statistics table
    
    Example:
        describe_table_statistics("session_123")
        describe_table_statistics("session_123", group_by=["Company"])
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
def create_date_features_from_column(
    session_id: str,
    date_column: str,
    features: Optional[List[str]] = None,
    table_name: str = "current"
) -> dict:
    """
    Extract date features (year, month, day, weekday, quarter, is_weekend) from a date column.
    
    Args:
        session_id: Unique session identifier
        date_column: Name of the date column
        features: List of features to extract - "year", "month", "day", "weekday", "quarter", "is_weekend"
                  (optional, extracts all if not specified)
        table_name: Name of the table (default: "current")
    
    Returns:
        Dictionary with operation result and new feature columns
    
    Example:
        create_date_features_from_column("session_123", "Date", ["year", "month", "quarter"])
    """
    try:
        result = create_date_features(session_id, date_column, features, table_name)
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
    
    Args:
        session_id: Unique session identifier
        column: Name of the numeric column
        bins: Number of bins (default: 4)
        labels: List of labels for bins (optional, must match number of bins)
        qcut: Use quantile-based binning if True, equal-width if False (default: False)
        table_name: Name of the table (default: "current")
    
    Returns:
        Dictionary with operation result and new binned column
    
    Example:
        bin_numeric_column("session_123", "Price", bins=5, labels=["Low", "Med-Low", "Medium", "Med-High", "High"])
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
    
    Args:
        session_id: Unique session identifier
        columns: List of categorical column names
        drop_first: Drop first category to avoid multicollinearity (default: False)
        table_name: Name of the table (default: "current")
    
    Returns:
        Dictionary with operation result and new binary columns
    
    Example:
        one_hot_encode_columns("session_123", ["Os", "Company"], drop_first=True)
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
    Scale numeric columns (standardization or min-max scaling).
    
    Args:
        session_id: Unique session identifier
        columns: List of numeric column names
        method: Scaling method - "standard" (z-score) or "minmax" (0-1 range) (default: "standard")
        table_name: Name of the table (default: "current")
    
    Returns:
        Dictionary with operation result and scaled columns
    
    Example:
        scale_numeric_columns("session_123", ["Price", "Weight"], method="standard")
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
def create_column_interaction(
    session_id: str,
    col1: str,
    col2: str,
    new_name: str,
    operation: str = "multiply",
    table_name: str = "current"
) -> dict:
    """
    Create interaction feature from two columns.
    
    Args:
        session_id: Unique session identifier
        col1: First column name
        col2: Second column name
        new_name: Name for the new interaction column
        operation: Interaction operation - "multiply", "divide", "add", "subtract" (default: "multiply")
        table_name: Name of the table (default: "current")
    
    Returns:
        Dictionary with operation result and new interaction column
    
    Example:
        create_column_interaction("session_123", "Ram", "SSD", "Ram_SSD", operation="multiply")
    """
    try:
        result = create_interaction(session_id, col1, col2, new_name, operation, table_name)
        return result
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to create interaction: {str(e)}"
        }


# ============================================================================
# Multi-table Operations
# ============================================================================

@mcp.tool()
def merge_tables_tool(
    session_id: str,
    right_table: str,
    on: Optional[List[str]] = None,
    left_on: Optional[str] = None,
    right_on: Optional[str] = None,
    how: str = "inner",
    table_name: str = "current"
) -> dict:
    """
    Merge current table with another table in the session.
    
    Args:
        session_id: Unique session identifier
        right_table: Name of the table to merge with
        on: Column names to join on (both tables must have these) (optional)
        left_on: Left table join key (optional, required if right_on specified)
        right_on: Right table join key (optional, required if left_on specified)
        how: Join type - "inner", "left", "right", "outer" (default: "inner")
        table_name: Name of the left table (default: "current")
    
    Returns:
        Dictionary with operation result and merged table
    
    Example:
        merge_tables_tool("session_123", "lookup_table", on=["Company"])
        merge_tables_tool("session_123", "prices", left_on="ProductID", right_on="ID", how="left")
    """
    try:
        result = merge_tables(session_id, right_table, on, left_on, right_on, how, table_name)
        return result
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to merge tables: {str(e)}"
        }


@mcp.tool()
def concatenate_tables(
    session_id: str,
    tables: List[str],
    axis: int = 0,
    ignore_index: bool = True,
    table_name: str = "current"
) -> dict:
    """
    Concatenate (stack) multiple tables vertically or horizontally.
    
    Args:
        session_id: Unique session identifier
        tables: List of table names to concatenate with the current table
        axis: 0 for vertical (stack rows), 1 for horizontal (stack columns) (default: 0)
        ignore_index: Reset index after concatenation (default: True)
        table_name: Name of the base table (default: "current")
    
    Returns:
        Dictionary with operation result and concatenated table
    
    Example:
        concatenate_tables("session_123", ["table2", "table3"], axis=0)
    """
    try:
        result = concat_tables(session_id, tables, axis, ignore_index, table_name)
        return result
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to concatenate tables: {str(e)}"
        }


if __name__ == "__main__":
    # Run the FastMCP server
    mcp.run()

