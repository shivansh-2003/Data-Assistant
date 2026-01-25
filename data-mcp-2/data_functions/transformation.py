"""
Data transformation operations module for MCP Server.
Handles column renaming, reordering, sorting, and basic transformations.
"""

import logging
from typing import List, Dict, Optional, Any, Union
import pandas as pd

from .core import get_table_data, commit_dataframe, _record_operation

logger = logging.getLogger(__name__)


def rename_columns(
    session_id: str,
    mapping: Dict[str, str],
    table_name: str = "current",
    inplace: bool = False,
    new_table_name: Optional[str] = None
) -> Dict[str, Any]:
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
    """
    try:
        df = get_table_data(session_id, table_name)
        if df is None:
            return {
                "success": False,
                "error": f"Table '{table_name}' not found in session {session_id}"
            }
        
        original_columns = list(df.columns)
        rows_before = len(df)
        
        # Validate mapping
        invalid_cols = [old for old in mapping.keys() if old not in df.columns]
        if invalid_cols:
            return {
                "success": False,
                "error": f"Columns not found: {', '.join(invalid_cols)}"
            }
        
        new_names = list(mapping.values())
        if len(set(new_names)) != len(new_names):
            return {
                "success": False,
                "error": "Duplicate new column names are not allowed"
            }

        existing_columns = set(df.columns) - set(mapping.keys())
        conflicts = [name for name in new_names if name in existing_columns]
        if conflicts:
            return {
                "success": False,
                "error": f"New column names conflict with existing columns: {', '.join(conflicts)}"
            }

        # Rename columns
        renamed_df = df.rename(columns=mapping)
        target_table = table_name if inplace else (new_table_name or f"{table_name}_renamed")
        
        # Commit changes
        if commit_dataframe(session_id, target_table, renamed_df):
            # Record operation
            _record_operation(session_id, target_table, {
                "type": "rename_columns",
                "mapping": mapping,
                "original_columns": original_columns,
                "new_columns": list(renamed_df.columns),
                "target_table": target_table,
                "rows_before": rows_before,
                "rows_after": len(renamed_df)
            })
            
            return {
                "success": True,
                "message": f"Renamed {len(mapping)} columns",
                "session_id": session_id,
                "table_name": target_table,
                "renamed_columns": mapping,
                "new_columns": list(renamed_df.columns),
                "preview": renamed_df.head(5).to_dict(orient="records")
            }
        else:
            return {
                "success": False,
                "error": "Failed to save changes to session"
            }
            
    except Exception as e:
        logger.error(f"Failed to rename columns: {e}")
        return {
            "success": False,
            "error": f"Failed to rename columns: {str(e)}"
        }


def reorder_columns(
    session_id: str,
    columns: List[str],
    table_name: str = "current",
    case_insensitive: bool = False
) -> Dict[str, Any]:
    """
    Reorder columns in a table.
    
    Args:
        session_id: Unique session identifier
        columns: List of column names in desired order
        table_name: Name of the table (default: "current")
        case_insensitive: Match column names without case sensitivity (default: False)
    
    Returns:
        Dictionary with operation result
    """
    try:
        df = get_table_data(session_id, table_name)
        if df is None:
            return {
                "success": False,
                "error": f"Table '{table_name}' not found in session {session_id}"
            }
        
        original_columns = list(df.columns)
        rows_before = len(df)
        
        if not columns:
            return {
                "success": False,
                "error": "Columns list cannot be empty"
            }

        if case_insensitive:
            lower_map = {}
            for col in df.columns:
                lower_col = col.lower()
                if lower_col in lower_map:
                    return {
                        "success": False,
                        "error": "Case-insensitive match is ambiguous for existing columns"
                    }
                lower_map[lower_col] = col
            resolved_columns = []
            for col in columns:
                key = col.lower()
                if key not in lower_map:
                    return {
                        "success": False,
                        "error": f"Columns not found: {col}"
                    }
                resolved_columns.append(lower_map[key])
        else:
            resolved_columns = columns
            missing_cols = [col for col in resolved_columns if col not in df.columns]
            if missing_cols:
                return {
                    "success": False,
                    "error": f"Columns not found: {', '.join(missing_cols)}"
                }

        if len(set(resolved_columns)) != len(resolved_columns):
            return {
                "success": False,
                "error": "Duplicate columns in reorder list are not allowed"
            }

        # Allow partial reordering: append remaining columns at the end
        remaining_columns = [col for col in df.columns if col not in resolved_columns]
        new_order = resolved_columns + remaining_columns
        df = df[new_order]
        
        # Commit changes
        if commit_dataframe(session_id, table_name, df):
            # Record operation
            _record_operation(session_id, table_name, {
                "type": "reorder_columns",
                "original_order": original_columns,
                "new_order": new_order,
                "rows_before": rows_before,
                "rows_after": len(df)
            })
            
            return {
                "success": True,
                "message": f"Reordered {len(resolved_columns)} columns",
                "session_id": session_id,
                "table_name": table_name,
                "new_column_order": new_order,
                "preview": df.head(5).to_dict(orient="records")
            }
        else:
            return {
                "success": False,
                "error": "Failed to save changes to session"
            }
            
    except Exception as e:
        logger.error(f"Failed to reorder columns: {e}")
        return {
            "success": False,
            "error": f"Failed to reorder columns: {str(e)}"
        }


def sort_data(
    session_id: str,
    by: List[str],
    ascending: Union[bool, List[bool]] = True,
    table_name: str = "current",
    na_position: str = "last",
    reset_index: bool = False
) -> Dict[str, Any]:
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
    """
    try:
        df = get_table_data(session_id, table_name)
        if df is None:
            return {
                "success": False,
                "error": f"Table '{table_name}' not found in session {session_id}"
            }
        
        # Validate columns exist
        invalid_cols = [col for col in by if col not in df.columns]
        if invalid_cols:
            return {
                "success": False,
                "error": f"Columns not found: {', '.join(invalid_cols)}"
            }
        
        if not by:
            return {
                "success": False,
                "error": "Sort columns cannot be empty"
            }
        if isinstance(ascending, list) and len(ascending) != len(by):
            return {
                "success": False,
                "error": "Ascending list length must match sort columns"
            }
        if na_position not in {"first", "last"}:
            return {
                "success": False,
                "error": "na_position must be 'first' or 'last'"
            }

        rows_before = len(df)
        # Sort the dataframe
        df = df.sort_values(by=by, ascending=ascending, na_position=na_position)
        if reset_index:
            df = df.reset_index(drop=True)
        
        # Commit changes
        if commit_dataframe(session_id, table_name, df):
            # Record operation
            _record_operation(session_id, table_name, {
                "type": "sort_data",
                "sort_columns": by,
                "ascending": ascending,
                "na_position": na_position,
                "reset_index": reset_index,
                "rows_before": rows_before,
                "rows_after": len(df)
            })
            
            return {
                "success": True,
                "message": f"Sorted by {', '.join(by)}",
                "session_id": session_id,
                "table_name": table_name,
                "sort_columns": by,
                "ascending": ascending,
                "na_position": na_position,
                "reset_index": reset_index,
                "preview": df.head(5).to_dict(orient="records")
            }
        else:
            return {
                "success": False,
                "error": "Failed to save changes to session"
            }
            
    except Exception as e:
        logger.error(f"Failed to sort data: {e}")
        return {
            "success": False,
            "error": f"Failed to sort data: {str(e)}"
        }


def apply_custom(
    session_id: str,
    column: str,
    function: str,
    new_column: Optional[str] = None,
    table_name: str = "current"
) -> Dict[str, Any]:
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
    """
    try:
        df = get_table_data(session_id, table_name)
        if df is None:
            return {
                "success": False,
                "error": f"Table '{table_name}' not found in session {session_id}"
            }
        
        if column not in df.columns:
            return {
                "success": False,
                "error": f"Column '{column}' not found in table"
            }
        
        allowed_functions = {
            "double": {"type": "numeric", "func": lambda s: s * 2},
            "square": {"type": "numeric", "func": lambda s: s ** 2},
            "abs": {"type": "numeric", "func": lambda s: s.abs()},
            "round": {"type": "numeric", "func": lambda s: s.round()},
            "strip": {"type": "string", "func": lambda s: s.astype(str).str.strip()},
            "lower": {"type": "string", "func": lambda s: s.astype(str).str.lower()},
            "upper": {"type": "string", "func": lambda s: s.astype(str).str.upper()},
            "title": {"type": "string", "func": lambda s: s.astype(str).str.title()},
            "to_string": {"type": "any", "func": lambda s: s.astype(str)}
        }

        if function not in allowed_functions:
            return {
                "success": False,
                "error": f"Unsupported function. Allowed: {', '.join(sorted(allowed_functions.keys()))}"
            }

        func_spec = allowed_functions[function]
        if func_spec["type"] == "numeric" and not pd.api.types.is_numeric_dtype(df[column]):
            return {
                "success": False,
                "error": f"Function '{function}' requires a numeric column"
            }
        if func_spec["type"] == "string" and not pd.api.types.is_string_dtype(df[column]):
            return {
                "success": False,
                "error": f"Function '{function}' requires a string column"
            }

        rows_before = len(df)
        try:
            result_series = func_spec["func"](df[column])
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to apply function: {str(e)}"
            }

        if new_column:
            df[new_column] = result_series
            result_column = new_column
        else:
            df[column] = result_series
            result_column = column
        
        # Commit changes
        if commit_dataframe(session_id, table_name, df):
            # Record operation
            _record_operation(session_id, table_name, {
                "type": "apply_custom",
                "column": column,
                "function": function,
                "new_column": new_column,
                "result_column": result_column,
                "rows_before": rows_before,
                "rows_after": len(df)
            })
            
            return {
                "success": True,
                "message": f"Applied custom function to create column '{result_column}'",
                "session_id": session_id,
                "table_name": table_name,
                "source_column": column,
                "result_column": result_column,
                "function": function,
                "preview": df.head(5).to_dict(orient="records")
            }
        else:
            return {
                "success": False,
                "error": "Failed to save changes to session"
            }
            
    except Exception as e:
        logger.error(f"Failed to apply custom function: {e}")
        return {
            "success": False,
            "error": f"Failed to apply custom function: {str(e)}"
        }


def set_index(
    session_id: str,
    columns: Optional[List[str]] = None,
    drop: bool = True,
    reset: bool = False,
    table_name: str = "current"
) -> Dict[str, Any]:
    """
    Set or reset the index of a table.

    Args:
        session_id: Unique session identifier
        columns: List of column names to set as index (optional)
        drop: Drop columns used for index if True (default: True)
        reset: If True, reset index instead of setting (default: False)
        table_name: Name of the table (default: "current")

    Returns:
        Dictionary with operation result
    """
    try:
        df = get_table_data(session_id, table_name)
        if df is None:
            return {
                "success": False,
                "error": f"Table '{table_name}' not found in session {session_id}"
            }

        rows_before = len(df)
        if reset:
            updated_df = df.reset_index(drop=drop)
            operation = "reset_index"
        else:
            if not columns:
                return {
                    "success": False,
                    "error": "Columns must be provided when setting index"
                }
            missing_cols = [col for col in columns if col not in df.columns]
            if missing_cols:
                return {
                    "success": False,
                    "error": f"Columns not found: {', '.join(missing_cols)}"
                }
            updated_df = df.set_index(columns, drop=drop)
            operation = "set_index"

        if commit_dataframe(session_id, table_name, updated_df):
            _record_operation(session_id, table_name, {
                "type": operation,
                "columns": columns,
                "drop": drop,
                "rows_before": rows_before,
                "rows_after": len(updated_df)
            })
            return {
                "success": True,
                "message": "Index updated",
                "session_id": session_id,
                "table_name": table_name,
                "preview": updated_df.head(5).to_dict(orient="records")
            }
        return {
            "success": False,
            "error": "Failed to save changes to session"
        }
    except Exception as e:
        logger.error(f"Failed to update index: {e}")
        return {
            "success": False,
            "error": f"Failed to update index: {str(e)}"
        }


def pivot_table(
    session_id: str,
    index: List[str],
    columns: List[str],
    values: Optional[List[str]] = None,
    aggfunc: str = "mean",
    table_name: str = "current"
) -> Dict[str, Any]:
    """
    Create a pivot table from a DataFrame.

    Args:
        session_id: Unique session identifier
        index: Column names to use as index
        columns: Column names to use as columns
        values: Column names to aggregate (optional)
        aggfunc: Aggregation function (default: "mean")
        table_name: Name of the table (default: "current")

    Returns:
        Dictionary with operation result
    """
    try:
        df = get_table_data(session_id, table_name)
        if df is None:
            return {
                "success": False,
                "error": f"Table '{table_name}' not found in session {session_id}"
            }

        missing_index = [col for col in index if col not in df.columns]
        missing_columns = [col for col in columns if col not in df.columns]
        missing_values = [col for col in (values or []) if col not in df.columns]
        if missing_index or missing_columns or missing_values:
            missing = missing_index + missing_columns + missing_values
            return {
                "success": False,
                "error": f"Columns not found: {', '.join(missing)}"
            }

        pivot_df = pd.pivot_table(
            df,
            index=index,
            columns=columns,
            values=values,
            aggfunc=aggfunc
        ).reset_index()

        if commit_dataframe(session_id, table_name, pivot_df):
            _record_operation(session_id, table_name, {
                "type": "pivot_table",
                "index": index,
                "columns": columns,
                "values": values,
                "aggfunc": aggfunc,
                "rows_after": len(pivot_df)
            })
            return {
                "success": True,
                "message": "Created pivot table",
                "session_id": session_id,
                "table_name": table_name,
                "preview": pivot_df.head(5).to_dict(orient="records")
            }
        return {
            "success": False,
            "error": "Failed to save changes to session"
        }
    except Exception as e:
        logger.error(f"Failed to create pivot table: {e}")
        return {
            "success": False,
            "error": f"Failed to create pivot table: {str(e)}"
        }


def melt_unpivot(
    session_id: str,
    id_vars: List[str],
    value_vars: Optional[List[str]] = None,
    var_name: str = "variable",
    value_name: str = "value",
    table_name: str = "current"
) -> Dict[str, Any]:
    """
    Unpivot a table from wide to long format.

    Args:
        session_id: Unique session identifier
        id_vars: Columns to keep as identifiers
        value_vars: Columns to unpivot (optional)
        var_name: Name for the variable column (default: "variable")
        value_name: Name for the value column (default: "value")
        table_name: Name of the table (default: "current")

    Returns:
        Dictionary with operation result
    """
    try:
        df = get_table_data(session_id, table_name)
        if df is None:
            return {
                "success": False,
                "error": f"Table '{table_name}' not found in session {session_id}"
            }

        missing_id = [col for col in id_vars if col not in df.columns]
        missing_values = [col for col in (value_vars or []) if col not in df.columns]
        if missing_id or missing_values:
            missing = missing_id + missing_values
            return {
                "success": False,
                "error": f"Columns not found: {', '.join(missing)}"
            }

        melted_df = df.melt(
            id_vars=id_vars,
            value_vars=value_vars,
            var_name=var_name,
            value_name=value_name
        )

        if commit_dataframe(session_id, table_name, melted_df):
            _record_operation(session_id, table_name, {
                "type": "melt_unpivot",
                "id_vars": id_vars,
                "value_vars": value_vars,
                "var_name": var_name,
                "value_name": value_name,
                "rows_after": len(melted_df)
            })
            return {
                "success": True,
                "message": "Unpivoted table",
                "session_id": session_id,
                "table_name": table_name,
                "preview": melted_df.head(5).to_dict(orient="records")
            }
        return {
            "success": False,
            "error": "Failed to save changes to session"
        }
    except Exception as e:
        logger.error(f"Failed to unpivot table: {e}")
        return {
            "success": False,
            "error": f"Failed to unpivot table: {str(e)}"
        }