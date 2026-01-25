"""
Multi-table operations module for MCP Server.
Handles table merging and concatenation operations.
"""

import logging
from typing import List, Optional, Dict, Any
import pandas as pd

from .core import get_table_data, commit_dataframe, _record_operation

logger = logging.getLogger(__name__)


def merge_tables(
    session_id: str,
    left_table: str,
    right_table: str,
    how: str = "inner",
    left_on: Optional[str] = None,
    right_on: Optional[str] = None,
    on: Optional[str] = None,
    new_table_name: Optional[str] = None,
    suffixes: tuple = ("_left", "_right")
) -> Dict[str, Any]:
    """
    Merge two tables using database-style join operation.
    
    Args:
        session_id: Unique session identifier
        left_table: Name of the left table
        right_table: Name of the right table
        how: Type of merge - "left", "right", "outer", "inner", "cross" (default: "inner")
        left_on: Column name to join on in left table (optional)
        right_on: Column name to join on in right table (optional)
        on: Column name to join on in both tables (optional)
        new_table_name: Name for the merged table (optional)
        suffixes: Suffixes to apply to overlapping column names (default: ("_left", "_right"))
    
    Returns:
        Dictionary with operation result and merged table
    """
    try:
        left_df = get_table_data(session_id, left_table)
        right_df = get_table_data(session_id, right_table)
        if left_df is None:
            return {
                "success": False,
                "error": f"Table '{left_table}' not found in session {session_id}"
            }
        if right_df is None:
            return {
                "success": False,
                "error": f"Table '{right_table}' not found in session {session_id}"
            }

        if on and (left_on or right_on):
            return {
                "success": False,
                "error": "Provide either 'on' or ('left_on' and 'right_on'), not both"
            }
        if on is None and (left_on is None or right_on is None):
            return {
                "success": False,
                "error": "You must provide 'on' or both 'left_on' and 'right_on'"
            }

        if on is not None:
            if on not in left_df.columns or on not in right_df.columns:
                return {
                    "success": False,
                    "error": f"Join column '{on}' not found in both tables"
                }
            left_on = right_on = None
        else:
            if left_on not in left_df.columns:
                return {
                    "success": False,
                    "error": f"Column '{left_on}' not found in left table '{left_table}'"
                }
            if right_on not in right_df.columns:
                return {
                    "success": False,
                    "error": f"Column '{right_on}' not found in right table '{right_table}'"
                }

        if on is not None:
            if not pd.api.types.is_dtype_equal(left_df[on].dtype, right_df[on].dtype):
                return {
                    "success": False,
                    "error": f"Join column '{on}' has incompatible dtypes"
                }
        else:
            if not pd.api.types.is_dtype_equal(left_df[left_on].dtype, right_df[right_on].dtype):
                return {
                    "success": False,
                    "error": f"Join columns '{left_on}' and '{right_on}' have incompatible dtypes"
                }

        merged_df = pd.merge(
            left_df,
            right_df,
            how=how,
            left_on=left_on,
            right_on=right_on,
            on=on,
            suffixes=suffixes
        )

        target_table = new_table_name or left_table
        if commit_dataframe(session_id, target_table, merged_df):
            _record_operation(session_id, target_table, {
                "type": "merge_tables",
                "left_table": left_table,
                "right_table": right_table,
                "how": how,
                "left_on": left_on,
                "right_on": right_on,
                "on": on,
                "suffixes": suffixes,
                "target_table": target_table,
                "rows_before_left": len(left_df),
                "rows_before_right": len(right_df),
                "rows_after": len(merged_df)
            })
            return {
                "success": True,
                "message": f"Merged tables '{left_table}' and '{right_table}'",
                "session_id": session_id,
                "table_name": target_table,
                "preview": merged_df.head(5).to_dict(orient="records")
            }
        return {
            "success": False,
            "error": "Failed to save merged table to session"
        }
    except Exception as e:
        logger.error(f"Failed to merge tables: {e}")
        return {
            "success": False,
            "error": f"Failed to merge tables: {str(e)}"
        }


def concat_tables(
    session_id: str,
    tables: List[str],
    axis: int = 0,
    join: str = "outer",
    ignore_index: bool = False,
    new_table_name: Optional[str] = None,
    keys: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Concatenate multiple tables along a particular axis.
    
    Args:
        session_id: Unique session identifier
        tables: List of table names to concatenate
        axis: 0 for rows, 1 for columns (default: 0)
        join: How to handle indexes on other axis - "inner" or "outer" (default: "outer")
        ignore_index: If True, do not use the index values along the concatenation axis (default: False)
        new_table_name: Name for the concatenated table (optional)
        keys: Optional keys for hierarchical indexing (optional)
    
    Returns:
        Dictionary with operation result and concatenated table
    """
    try:
        if not tables or len(tables) < 2:
            return {
                "success": False,
                "error": "Provide at least two tables to concatenate"
            }
        if axis not in (0, 1):
            return {
                "success": False,
                "error": "Axis must be 0 (rows) or 1 (columns)"
            }

        dataframes = []
        for table in tables:
            df = get_table_data(session_id, table)
            if df is None:
                return {
                    "success": False,
                    "error": f"Table '{table}' not found in session {session_id}"
                }
            dataframes.append(df)

        if axis == 0:
            base_columns = list(dataframes[0].columns)
            for df in dataframes[1:]:
                if list(df.columns) != base_columns:
                    return {
                        "success": False,
                        "error": "All tables must have identical columns for row-wise concatenation"
                    }
            for col in base_columns:
                base_dtype = dataframes[0][col].dtype
                if any(not pd.api.types.is_dtype_equal(df[col].dtype, base_dtype) for df in dataframes[1:]):
                    return {
                        "success": False,
                        "error": f"Column '{col}' has incompatible dtypes across tables"
                    }

        concatenated_df = pd.concat(
            dataframes,
            axis=axis,
            join=join,
            ignore_index=ignore_index,
            keys=keys
        )

        target_table = new_table_name or tables[0]
        if commit_dataframe(session_id, target_table, concatenated_df):
            _record_operation(session_id, target_table, {
                "type": "concat_tables",
                "tables": tables,
                "axis": axis,
                "join": join,
                "ignore_index": ignore_index,
                "keys": keys,
                "target_table": target_table,
                "rows_after": len(concatenated_df)
            })
            return {
                "success": True,
                "message": f"Concatenated {len(tables)} tables",
                "session_id": session_id,
                "table_name": target_table,
                "preview": concatenated_df.head(5).to_dict(orient="records")
            }
        return {
            "success": False,
            "error": "Failed to save concatenated table to session"
        }
    except Exception as e:
        logger.error(f"Failed to concatenate tables: {e}")
        return {
            "success": False,
            "error": f"Failed to concatenate tables: {str(e)}"
        }


def merge_on_index(
    session_id: str,
    left_table: str,
    right_table: str,
    how: str = "inner",
    new_table_name: Optional[str] = None,
    suffixes: tuple = ("_left", "_right")
) -> Dict[str, Any]:
    """
    Merge two tables using their index values.

    Args:
        session_id: Unique session identifier
        left_table: Name of the left table
        right_table: Name of the right table
        how: Type of merge - "left", "right", "outer", "inner" (default: "inner")
        new_table_name: Name for the merged table (optional)
        suffixes: Suffixes to apply to overlapping column names (default: ("_left", "_right"))

    Returns:
        Dictionary with operation result and merged table
    """
    try:
        left_df = get_table_data(session_id, left_table)
        right_df = get_table_data(session_id, right_table)
        if left_df is None:
            return {
                "success": False,
                "error": f"Table '{left_table}' not found in session {session_id}"
            }
        if right_df is None:
            return {
                "success": False,
                "error": f"Table '{right_table}' not found in session {session_id}"
            }

        merged_df = pd.merge(
            left_df,
            right_df,
            how=how,
            left_index=True,
            right_index=True,
            suffixes=suffixes
        )

        target_table = new_table_name or left_table
        if commit_dataframe(session_id, target_table, merged_df):
            _record_operation(session_id, target_table, {
                "type": "merge_on_index",
                "left_table": left_table,
                "right_table": right_table,
                "how": how,
                "suffixes": suffixes,
                "target_table": target_table,
                "rows_before_left": len(left_df),
                "rows_before_right": len(right_df),
                "rows_after": len(merged_df)
            })
            return {
                "success": True,
                "message": f"Merged tables '{left_table}' and '{right_table}' on index",
                "session_id": session_id,
                "table_name": target_table,
                "preview": merged_df.head(5).to_dict(orient="records")
            }
        return {
            "success": False,
            "error": "Failed to save merged table to session"
        }
    except Exception as e:
        logger.error(f"Failed to merge tables on index: {e}")
        return {
            "success": False,
            "error": f"Failed to merge tables on index: {str(e)}"
        }