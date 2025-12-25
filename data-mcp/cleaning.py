"""Data cleaning tools for DataFrame manipulation."""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any
import logging
from .core import load_current_dataframe, commit_dataframe

logger = logging.getLogger(__name__)


def drop_rows(session_id: str, indices: List[int] = None, condition: str = None, subset: List[str] = None, keep: str = "first", table_name: str = "current") -> Dict:
    """Remove rows by index, condition, or duplicates."""
    try:
        df = load_current_dataframe(session_id, table_name)
        rows_before = len(df)
        df_result = df.copy()
        
        if indices is not None:
            # Drop by index
            df_result = df_result.drop(df_result.index[indices])
            change_summary = f"Removed {len(indices)} rows by index"
        elif condition is not None:
            # Filter by condition
            try:
                mask = df_result.eval(condition)
                rows_dropped = mask.sum()
                df_result = df_result[~mask]
                change_summary = f"Removed {rows_dropped} rows matching condition: {condition}"
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Invalid condition expression: {str(e)}",
                    "rows_before": rows_before,
                    "rows_after": rows_before,
                    "columns_before": len(df.columns),
                    "columns_after": len(df.columns)
                }
        elif subset is not None:
            # Drop duplicates
            # Validate columns exist
            missing_cols = [col for col in subset if col not in df_result.columns]
            if missing_cols:
                return {
                    "success": False,
                    "error": f"Columns not found: {missing_cols}",
                    "rows_before": rows_before,
                    "rows_after": rows_before,
                    "columns_before": len(df.columns),
                    "columns_after": len(df.columns)
                }
            rows_before_dedup = len(df_result)
            df_result = df_result.drop_duplicates(subset=subset, keep=keep)
            rows_dropped = rows_before_dedup - len(df_result)
            change_summary = f"Removed {rows_dropped} duplicate rows (keeping {keep})"
        else:
            return {
                "success": False,
                "error": "Must specify either indices, condition, or subset for dropping duplicates",
                "rows_before": rows_before,
                "rows_after": rows_before,
                "columns_before": len(df.columns),
                "columns_after": len(df.columns)
            }
        
        return commit_dataframe(df_result, session_id, change_summary, table_name)
    except Exception as e:
        logger.error(f"Error in drop_rows: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "rows_before": 0,
            "rows_after": 0,
            "columns_before": 0,
            "columns_after": 0
        }


def fill_missing(session_id: str, value: Any = None, method: str = None, columns: List[str] = None, table_name: str = "current") -> Dict:
    """Fill NaN values with strategy."""
    try:
        df = load_current_dataframe(session_id, table_name)
        df_result = df.copy()
        
        if columns:
            missing_cols = [col for col in columns if col not in df_result.columns]
            if missing_cols:
                return {
                    "success": False,
                    "error": f"Columns not found: {missing_cols}",
                    "rows_before": len(df),
                    "rows_after": len(df),
                    "columns_before": len(df.columns),
                    "columns_after": len(df.columns)
                }
            target_cols = columns
        else:
            target_cols = df_result.columns.tolist()
        
        missing_before = df_result[target_cols].isnull().sum().sum()
        
        if value is not None:
            # Fill with specific value
            df_result[target_cols] = df_result[target_cols].fillna(value)
            change_summary = f"Filled {missing_before} missing values with {value}"
        elif method == "ffill":
            df_result[target_cols] = df_result[target_cols].fillna(method="ffill")
            change_summary = f"Forward-filled {missing_before} missing values"
        elif method == "bfill":
            df_result[target_cols] = df_result[target_cols].fillna(method="bfill")
            change_summary = f"Backward-filled {missing_before} missing values"
        elif method == "mean":
            numeric_cols = [col for col in target_cols if pd.api.types.is_numeric_dtype(df_result[col])]
            for col in numeric_cols:
                df_result[col] = df_result[col].fillna(df_result[col].mean())
            change_summary = f"Filled {missing_before} missing values with mean"
        elif method == "median":
            numeric_cols = [col for col in target_cols if pd.api.types.is_numeric_dtype(df_result[col])]
            for col in numeric_cols:
                df_result[col] = df_result[col].fillna(df_result[col].median())
            change_summary = f"Filled {missing_before} missing values with median"
        elif method == "mode":
            for col in target_cols:
                mode_value = df_result[col].mode()
                if len(mode_value) > 0:
                    df_result[col] = df_result[col].fillna(mode_value[0])
            change_summary = f"Filled {missing_before} missing values with mode"
        else:
            return {
                "success": False,
                "error": "Must specify either value or method (ffill, bfill, mean, median, mode)",
                "rows_before": len(df),
                "rows_after": len(df),
                "columns_before": len(df.columns),
                "columns_after": len(df.columns)
            }
        
        return commit_dataframe(df_result, session_id, change_summary, table_name)
    except Exception as e:
        logger.error(f"Error in fill_missing: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "rows_before": 0,
            "rows_after": 0,
            "columns_before": 0,
            "columns_after": 0
        }


def drop_missing(session_id: str, how: str = "any", thresh: int = None, axis: int = 0, subset: List[str] = None, table_name: str = "current") -> Dict:
    """Drop rows/columns with missing values."""
    try:
        df = load_current_dataframe(session_id, table_name)
        rows_before = len(df)
        cols_before = len(df.columns)
        
        if subset:
            missing_cols = [col for col in subset if col not in df.columns]
            if missing_cols:
                return {
                    "success": False,
                    "error": f"Columns not found: {missing_cols}",
                    "rows_before": rows_before,
                    "rows_after": rows_before,
                    "columns_before": cols_before,
                    "columns_after": cols_before
                }
        
        # pandas doesn't allow both how and thresh at the same time
        if thresh is not None:
            df_result = df.dropna(thresh=thresh, axis=axis, subset=subset)
        else:
            df_result = df.dropna(how=how, axis=axis, subset=subset)
        
        rows_after = len(df_result)
        cols_after = len(df_result.columns)
        rows_dropped = rows_before - rows_after if axis == 0 else 0
        cols_dropped = cols_before - cols_after if axis == 1 else 0
        
        if axis == 0:
            change_summary = f"Dropped {rows_dropped} rows with {'any' if how == 'any' else 'all'} missing values"
        else:
            change_summary = f"Dropped {cols_dropped} columns with {'any' if how == 'any' else 'all'} missing values"
        
        return commit_dataframe(df_result, session_id, change_summary, table_name)
    except Exception as e:
        logger.error(f"Error in drop_missing: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "rows_before": 0,
            "rows_after": 0,
            "columns_before": 0,
            "columns_after": 0
        }


def replace_values(session_id: str, to_replace: Dict, value: Any = None, regex: bool = False, table_name: str = "current") -> Dict:
    """Replace specific values (including regex)."""
    try:
        df = load_current_dataframe(session_id, table_name)
        df_result = df.copy()
        
        # If to_replace is a dict mapping column names to replacement dicts
        if isinstance(to_replace, dict) and all(isinstance(v, dict) for v in to_replace.values()):
            # Column-specific replacements
            for col, replacements in to_replace.items():
                if col not in df_result.columns:
                    return {
                        "success": False,
                        "error": f"Column '{col}' not found",
                        "rows_before": len(df),
                        "rows_after": len(df),
                        "columns_before": len(df.columns),
                        "columns_after": len(df.columns)
                    }
                df_result[col] = df_result[col].replace(replacements, regex=regex)
            change_summary = f"Replaced values in {len(to_replace)} columns"
        else:
            # Global replacement
            df_result = df_result.replace(to_replace, value=value, regex=regex)
            change_summary = f"Replaced values across DataFrame"
        
        return commit_dataframe(df_result, session_id, change_summary, table_name)
    except Exception as e:
        logger.error(f"Error in replace_values: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "rows_before": 0,
            "rows_after": 0,
            "columns_before": 0,
            "columns_after": 0
        }


def clean_strings(session_id: str, columns: List[str], operation: str = "strip", table_name: str = "current") -> Dict:
    """Strip whitespace, lower/upper case, title case."""
    try:
        df = load_current_dataframe(session_id, table_name)
        df_result = df.copy()
        
        missing_cols = [col for col in columns if col not in df_result.columns]
        if missing_cols:
            return {
                "success": False,
                "error": f"Columns not found: {missing_cols}",
                "rows_before": len(df),
                "rows_after": len(df),
                "columns_before": len(df.columns),
                "columns_after": len(df.columns)
            }
        
        # Ensure columns are string type
        for col in columns:
            df_result[col] = df_result[col].astype(str)
        
        if operation == "strip":
            for col in columns:
                df_result[col] = df_result[col].str.strip()
            change_summary = f"Stripped whitespace from {len(columns)} string columns"
        elif operation == "lower":
            for col in columns:
                df_result[col] = df_result[col].str.lower()
            change_summary = f"Converted {len(columns)} columns to lowercase"
        elif operation == "upper":
            for col in columns:
                df_result[col] = df_result[col].str.upper()
            change_summary = f"Converted {len(columns)} columns to uppercase"
        elif operation == "title":
            for col in columns:
                df_result[col] = df_result[col].str.title()
            change_summary = f"Converted {len(columns)} columns to title case"
        else:
            return {
                "success": False,
                "error": f"Unknown operation: {operation}. Must be 'strip', 'lower', 'upper', or 'title'",
                "rows_before": len(df),
                "rows_after": len(df),
                "columns_before": len(df.columns),
                "columns_after": len(df.columns)
            }
        
        return commit_dataframe(df_result, session_id, change_summary, table_name)
    except Exception as e:
        logger.error(f"Error in clean_strings: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "rows_before": 0,
            "rows_after": 0,
            "columns_before": 0,
            "columns_after": 0
        }


def remove_outliers(session_id: str, columns: List[str], method: str = "iqr", threshold: float = 1.5, table_name: str = "current") -> Dict:
    """Remove/filter outliers using IQR or std dev."""
    try:
        df = load_current_dataframe(session_id, table_name)
        rows_before = len(df)
        
        missing_cols = [col for col in columns if col not in df.columns]
        if missing_cols:
            return {
                "success": False,
                "error": f"Columns not found: {missing_cols}",
                "rows_before": rows_before,
                "rows_after": rows_before,
                "columns_before": len(df.columns),
                "columns_after": len(df.columns)
            }
        
        # Ensure columns are numeric
        numeric_cols = [col for col in columns if pd.api.types.is_numeric_dtype(df[col])]
        if len(numeric_cols) != len(columns):
            non_numeric = [col for col in columns if col not in numeric_cols]
            return {
                "success": False,
                "error": f"Non-numeric columns: {non_numeric}",
                "rows_before": rows_before,
                "rows_after": rows_before,
                "columns_before": len(df.columns),
                "columns_after": len(df.columns)
            }
        
        mask = pd.Series([True] * len(df))
        
        if method == "iqr":
            for col in numeric_cols:
                Q1 = df[col].quantile(0.25)
                Q3 = df[col].quantile(0.75)
                IQR = Q3 - Q1
                lower_bound = Q1 - threshold * IQR
                upper_bound = Q3 + threshold * IQR
                mask &= (df[col] >= lower_bound) & (df[col] <= upper_bound)
            change_summary = f"Removed outliers using IQR method (threshold={threshold}) from {len(numeric_cols)} columns"
        elif method == "zscore":
            for col in numeric_cols:
                z_scores = np.abs((df[col] - df[col].mean()) / df[col].std())
                mask &= z_scores < threshold
            change_summary = f"Removed outliers using z-score method (threshold={threshold}) from {len(numeric_cols)} columns"
        else:
            return {
                "success": False,
                "error": f"Unknown method: {method}. Must be 'iqr' or 'zscore'",
                "rows_before": rows_before,
                "rows_after": rows_before,
                "columns_before": len(df.columns),
                "columns_after": len(df.columns)
            }
        
        df_result = df[mask].copy()
        rows_removed = rows_before - len(df_result)
        change_summary = f"Removed {rows_removed} outliers ({change_summary})"
        
        return commit_dataframe(df_result, session_id, change_summary, table_name)
    except Exception as e:
        logger.error(f"Error in remove_outliers: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "rows_before": 0,
            "rows_after": 0,
            "columns_before": 0,
            "columns_after": 0
        }

