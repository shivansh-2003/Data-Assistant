"""Multi-table operations for DataFrame manipulation."""

import pandas as pd
from typing import Dict, List, Optional
import logging
from .core import load_current_dataframe, commit_dataframe, list_available_tables as _list_available_tables

logger = logging.getLogger(__name__)


def merge_tables(session_id: str, right_table: str, on: List[str] = None, left_on: str = None, right_on: str = None, how: str = "inner", table_name: str = "current") -> Dict:
    """Merge current df with another table in session."""
    try:
        df_left = load_current_dataframe(session_id, table_name)
        df_right = load_current_dataframe(session_id, right_table)
        
        # Validate join keys
        if on:
            missing_left = [col for col in on if col not in df_left.columns]
            missing_right = [col for col in on if col not in df_right.columns]
            if missing_left or missing_right:
                return {
                    "success": False,
                    "error": f"Join keys not found - left: {missing_left}, right: {missing_right}",
                    "rows_before": len(df_left),
                    "rows_after": len(df_left),
                    "columns_before": len(df_left.columns),
                    "columns_after": len(df_left.columns)
                }
            merge_keys = {"on": on}
        elif left_on and right_on:
            if left_on not in df_left.columns:
                return {
                    "success": False,
                    "error": f"Left join key '{left_on}' not found",
                    "rows_before": len(df_left),
                    "rows_after": len(df_left),
                    "columns_before": len(df_left.columns),
                    "columns_after": len(df_left.columns)
                }
            if right_on not in df_right.columns:
                return {
                    "success": False,
                    "error": f"Right join key '{right_on}' not found",
                    "rows_before": len(df_left),
                    "rows_after": len(df_left),
                    "columns_before": len(df_left.columns),
                    "columns_after": len(df_left.columns)
                }
            merge_keys = {"left_on": left_on, "right_on": right_on}
        else:
            return {
                "success": False,
                "error": "Must specify either 'on' (same column names) or both 'left_on' and 'right_on'",
                "rows_before": len(df_left),
                "rows_after": len(df_left),
                "columns_before": len(df_left.columns),
                "columns_after": len(df_left.columns)
            }
        
        # Validate how parameter
        valid_how = ["inner", "left", "right", "outer"]
        if how not in valid_how:
            return {
                "success": False,
                "error": f"Invalid 'how' parameter: {how}. Must be one of {valid_how}",
                "rows_before": len(df_left),
                "rows_after": len(df_left),
                "columns_before": len(df_left.columns),
                "columns_after": len(df_left.columns)
            }
        
        df_result = pd.merge(df_left, df_right, how=how, **merge_keys, suffixes=("", f"_{right_table}"))
        
        key_desc = f"on {', '.join(on)}" if on else f"on {left_on} = {right_on}"
        change_summary = f"{how.title()}-joined '{right_table}' table {key_desc} → {len(df_result)} rows"
        
        return commit_dataframe(df_result, session_id, change_summary, table_name)
    except Exception as e:
        logger.error(f"Error in merge_tables: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "rows_before": 0,
            "rows_after": 0,
            "columns_before": 0,
            "columns_after": 0
        }


def concat_tables(session_id: str, tables: List[str], axis: int = 0, ignore_index: bool = True, table_name: str = "current") -> Dict:
    """Stack tables vertically/horizontally."""
    try:
        if table_name in tables:
            return {
                "success": False,
                "error": f"Cannot concatenate table with itself. '{table_name}' is in the tables list",
                "rows_before": 0,
                "rows_after": 0,
                "columns_before": 0,
                "columns_after": 0
            }
        
        # Load all tables
        dfs = []
        for table in tables:
            try:
                df = load_current_dataframe(session_id, table)
                dfs.append(df)
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Error loading table '{table}': {str(e)}",
                    "rows_before": 0,
                    "rows_after": 0,
                    "columns_before": 0,
                    "columns_after": 0
                }
        
        if len(dfs) == 0:
            return {
                "success": False,
                "error": "No valid tables to concatenate",
                "rows_before": 0,
                "rows_after": 0,
                "columns_before": 0,
                "columns_after": 0
            }
        
        # Get initial size for summary
        initial_df = load_current_dataframe(session_id, table_name)
        rows_before = len(initial_df)
        cols_before = len(initial_df.columns)
        
        # Concatenate
        df_result = pd.concat([initial_df] + dfs, axis=axis, ignore_index=ignore_index).copy()
        
        if axis == 0:
            change_summary = f"Concatenated {len(tables)} tables vertically → {len(df_result)} rows"
        else:
            change_summary = f"Concatenated {len(tables)} tables horizontally → {len(df_result.columns)} columns"
        
        return commit_dataframe(df_result, session_id, change_summary, table_name)
    except Exception as e:
        logger.error(f"Error in concat_tables: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "rows_before": 0,
            "rows_after": 0,
            "columns_before": 0,
            "columns_after": 0
        }


def list_available_tables(session_id: str) -> List[str]:
    """Helper to show session tables."""
    return _list_available_tables(session_id)

