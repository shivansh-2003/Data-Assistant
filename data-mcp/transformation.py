"""Data transformation tools for DataFrame manipulation."""

import pandas as pd
from typing import Dict, List, Optional, Union
import logging
import re
from .core import load_current_dataframe, commit_dataframe

logger = logging.getLogger(__name__)


def rename_columns(session_id: str, mapping: Dict[str, str], table_name: str = "current") -> Dict:
    """Rename one or more columns."""
    try:
        df = load_current_dataframe(session_id, table_name)
        
        missing_cols = [col for col in mapping.keys() if col not in df.columns]
        if missing_cols:
            return {
                "success": False,
                "error": f"Columns not found: {missing_cols}",
                "rows_before": len(df),
                "rows_after": len(df),
                "columns_before": len(df.columns),
                "columns_after": len(df.columns)
            }
        
        df_result = df.rename(columns=mapping).copy()
        renamed_list = [f"{old} → {new}" for old, new in list(mapping.items())[:5]]
        change_summary = f"Renamed {len(mapping)} columns: {', '.join(renamed_list)}{'...' if len(mapping) > 5 else ''}"
        
        return commit_dataframe(df_result, session_id, change_summary, table_name)
    except Exception as e:
        logger.error(f"Error in rename_columns: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "rows_before": 0,
            "rows_after": 0,
            "columns_before": 0,
            "columns_after": 0
        }


def reorder_columns(session_id: str, columns: List[str], table_name: str = "current") -> Dict:
    """Reorder column positions."""
    try:
        df = load_current_dataframe(session_id, table_name)
        
        missing_cols = [col for col in columns if col not in df.columns]
        if missing_cols:
            return {
                "success": False,
                "error": f"Columns not found: {missing_cols}",
                "rows_before": len(df),
                "rows_after": len(df),
                "columns_before": len(df.columns),
                "columns_after": len(df.columns)
            }
        
        # Include any columns not in the list at the end
        other_cols = [col for col in df.columns if col not in columns]
        df_result = df[columns + other_cols].copy()
        
        change_summary = f"Reordered columns: moved {len(columns)} columns to front"
        
        return commit_dataframe(df_result, session_id, change_summary, table_name)
    except Exception as e:
        logger.error(f"Error in reorder_columns: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "rows_before": 0,
            "rows_after": 0,
            "columns_before": 0,
            "columns_after": 0
        }


def sort_data(session_id: str, by: List[str], ascending: Union[bool, List[bool]] = True, table_name: str = "current") -> Dict:
    """Sort by one or more columns."""
    try:
        df = load_current_dataframe(session_id, table_name)
        
        missing_cols = [col for col in by if col not in df.columns]
        if missing_cols:
            return {
                "success": False,
                "error": f"Columns not found: {missing_cols}",
                "rows_before": len(df),
                "rows_after": len(df),
                "columns_before": len(df.columns),
                "columns_after": len(df.columns)
            }
        
        df_result = df.sort_values(by=by, ascending=ascending).reset_index(drop=True).copy()
        
        asc_desc = "ascending" if (ascending if isinstance(ascending, bool) else ascending[0]) else "descending"
        change_summary = f"Sorted by {', '.join(by)} ({asc_desc})"
        
        return commit_dataframe(df_result, session_id, change_summary, table_name)
    except Exception as e:
        logger.error(f"Error in sort_data: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "rows_before": 0,
            "rows_after": 0,
            "columns_before": 0,
            "columns_after": 0
        }


def set_index(session_id: str, columns: List[str] = None, drop: bool = True, reset: bool = False, table_name: str = "current") -> Dict:
    """Set/reset index column(s)."""
    try:
        df = load_current_dataframe(session_id, table_name)
        
        if reset:
            df_result = df.reset_index(drop=drop).copy()
            change_summary = "Reset index" + (" (dropped original)" if drop else "")
        else:
            if columns is None:
                return {
                    "success": False,
                    "error": "Must specify columns to set as index",
                    "rows_before": len(df),
                    "rows_after": len(df),
                    "columns_before": len(df.columns),
                    "columns_after": len(df.columns)
                }
            
            missing_cols = [col for col in columns if col not in df.columns]
            if missing_cols:
                return {
                    "success": False,
                    "error": f"Columns not found: {missing_cols}",
                    "rows_before": len(df),
                    "rows_after": len(df),
                    "columns_before": len(df.columns),
                    "columns_after": len(df.columns)
                }
            
            df_result = df.set_index(columns, drop=drop).copy()
            change_summary = f"Set {', '.join(columns)} as index" + (" (dropped original)" if drop else "")
        
        return commit_dataframe(df_result, session_id, change_summary, table_name)
    except Exception as e:
        logger.error(f"Error in set_index: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "rows_before": 0,
            "rows_after": 0,
            "columns_before": 0,
            "columns_after": 0
        }


def pivot_table(session_id: str, index: List[str], columns: List[str] = None, values: List[str] = None, aggfunc: str = "sum", table_name: str = "current") -> Dict:
    """Create pivot summary."""
    try:
        df = load_current_dataframe(session_id, table_name)
        
        all_cols = index + (columns or []) + (values or [])
        missing_cols = [col for col in all_cols if col not in df.columns]
        if missing_cols:
            return {
                "success": False,
                "error": f"Columns not found: {missing_cols}",
                "rows_before": len(df),
                "rows_after": len(df),
                "columns_before": len(df.columns),
                "columns_after": len(df.columns)
            }
        
        # Map string aggfunc to pandas function
        aggfunc_map = {
            "sum": "sum",
            "mean": "mean",
            "count": "count",
            "min": "min",
            "max": "max",
            "std": "std",
            "median": "median"
        }
        aggfunc_val = aggfunc_map.get(aggfunc.lower(), aggfunc)
        
        df_result = pd.pivot_table(df, index=index, columns=columns, values=values, aggfunc=aggfunc_val).reset_index().copy()
        
        change_summary = f"Created pivot table: {aggfunc} of {values[0] if values and len(values) == 1 else 'values'} by {', '.join(index)}"
        if columns:
            change_summary += f" and {', '.join(columns)}"
        
        return commit_dataframe(df_result, session_id, change_summary, table_name)
    except Exception as e:
        logger.error(f"Error in pivot_table: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "rows_before": 0,
            "rows_after": 0,
            "columns_before": 0,
            "columns_after": 0
        }


def melt_unpivot(session_id: str, id_vars: List[str], value_vars: List[str] = None, var_name: str = "variable", value_name: str = "value", table_name: str = "current") -> Dict:
    """Unpivot wide data to long."""
    try:
        df = load_current_dataframe(session_id, table_name)
        
        all_cols = id_vars + (value_vars or [])
        missing_cols = [col for col in all_cols if col not in df.columns]
        if missing_cols:
            return {
                "success": False,
                "error": f"Columns not found: {missing_cols}",
                "rows_before": len(df),
                "rows_after": len(df),
                "columns_before": len(df.columns),
                "columns_after": len(df.columns)
            }
        
        df_result = df.melt(id_vars=id_vars, value_vars=value_vars, var_name=var_name, value_name=value_name).copy()
        
        num_unpivoted = len(value_vars) if value_vars else len(df.columns) - len(id_vars)
        change_summary = f"Unpivoted {num_unpivoted} columns into '{var_name}' and '{value_name}' columns"
        
        return commit_dataframe(df_result, session_id, change_summary, table_name)
    except Exception as e:
        logger.error(f"Error in melt_unpivot: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "rows_before": 0,
            "rows_after": 0,
            "columns_before": 0,
            "columns_after": 0
        }


def apply_custom(session_id: str, column: str, function: str, new_column: str = None, table_name: str = "current") -> Dict:
    """Apply safe lambda or simple function to column(s)."""
    try:
        df = load_current_dataframe(session_id, table_name)
        
        if column not in df.columns:
            return {
                "success": False,
                "error": f"Column '{column}' not found",
                "rows_before": len(df),
                "rows_after": len(df),
                "columns_before": len(df.columns),
                "columns_after": len(df.columns)
            }
        
        df_result = df.copy()
        
        # Whitelist of safe operations (simple transformations)
        # Only allow basic arithmetic and string operations
        safe_patterns = [
            r'^lambda x: x \* \d+(\.\d+)?$',  # Multiply by constant
            r'^lambda x: x / \d+(\.\d+)?$',   # Divide by constant
            r'^lambda x: x \+ \d+(\.\d+)?$',  # Add constant
            r'^lambda x: x - \d+(\.\d+)?$',   # Subtract constant
            r'^lambda x: x \*\* \d+$',        # Power
            r'^lambda x: abs\(x\)$',          # Absolute value
            r'^lambda x: round\(x(, \d+)?\)$',  # Round
            r'^lambda x: str\(x\)$',          # String conversion
            r'^lambda x: int\(x\)$',          # Int conversion
            r'^lambda x: float\(x\)$',        # Float conversion
        ]
        
        # Check if function matches safe pattern
        is_safe = any(re.match(pattern, function.strip()) for pattern in safe_patterns)
        
        if not is_safe:
            return {
                "success": False,
                "error": f"Function not in whitelist of safe operations. Only simple arithmetic and type conversions allowed.",
                "rows_before": len(df),
                "rows_after": len(df),
                "columns_before": len(df.columns),
                "columns_after": len(df.columns)
            }
        
        # Evaluate the lambda function safely
        try:
            func = eval(function)  # Safe because we validated the pattern
            result = df_result[column].apply(func)
        except Exception as e:
            return {
                "success": False,
                "error": f"Error applying function: {str(e)}",
                "rows_before": len(df),
                "rows_after": len(df),
                "columns_before": len(df.columns),
                "columns_after": len(df.columns)
            }
        
        target_col = new_column if new_column else column
        df_result[target_col] = result
        
        change_summary = f"Applied function to '{column}'" + (f" → '{new_column}'" if new_column else "")
        
        return commit_dataframe(df_result, session_id, change_summary, table_name)
    except Exception as e:
        logger.error(f"Error in apply_custom: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "rows_before": 0,
            "rows_after": 0,
            "columns_before": 0,
            "columns_after": 0
        }

