"""
Data cleaning operations module for MCP Server.
Handles missing values, row operations, value replacements, and string cleaning.
"""

import logging
import re
import unicodedata
from typing import List, Optional, Any, Dict
import pandas as pd
import numpy as np

from .core import get_table_data, commit_dataframe, _record_operation

logger = logging.getLogger(__name__)


def drop_rows(
    session_id: str,
    indices: Optional[List[int]] = None,
    condition: Optional[str] = None,
    subset: Optional[List[str]] = None,
    keep: str = "first",
    table_name: str = "current",
    inplace: bool = True,
    new_table_name: Optional[str] = None
) -> Dict[str, Any]:
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
    """
    try:
        df = get_table_data(session_id, table_name)
        if df is None:
            return {
                "success": False,
                "error": f"Table '{table_name}' not found in session {session_id}"
            }
        
        original_count = len(df)
        
        duplicate_stats = None
        # Handle different drop methods
        if indices is not None:
            # Drop by index
            if not indices:
                return {
                    "success": False,
                    "error": "Indices list cannot be empty"
                }
            invalid = [idx for idx in indices if idx >= len(df) or idx < -len(df)]
            if invalid:
                return {
                    "success": False,
                    "error": f"Indices out of bounds: {invalid}"
                }
            df = df.drop(df.index[indices])
            operation_type = "drop_by_index"
            operation_details = {"indices": indices}
        elif condition is not None:
            # Drop by condition
            try:
                mask = df.eval(condition, engine="python")
                df = df[~mask]
                operation_type = "drop_by_condition"
                operation_details = {"condition": condition}
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Invalid condition '{condition}': {str(e)}"
                }
        elif subset is not None:
            # Drop duplicates
            missing_cols = [col for col in subset if col not in df.columns]
            if missing_cols:
                return {
                    "success": False,
                    "error": f"Columns not found: {', '.join(missing_cols)}"
                }
            original_len = len(df)
            duplicate_mask = df.duplicated(subset=subset, keep=keep)
            df = df.drop_duplicates(subset=subset, keep=keep)
            dropped_count = duplicate_mask.sum()
            duplicate_stats = {
                "original_rows": original_len,
                "unique_rows": len(df),
                "dropped_duplicates": dropped_count
            }
            operation_type = "drop_duplicates"
            operation_details = {"subset": subset, "keep": keep, "dropped_count": dropped_count}
        else:
            return {
                "success": False,
                "error": "Must specify one of: indices, condition, or subset"
            }
        
        dropped_count = original_count - len(df)
        
        target_table = table_name if inplace else (new_table_name or f"{table_name}_dropped")
        # Commit changes
        if commit_dataframe(session_id, target_table, df):
            # Record operation
            _record_operation(session_id, target_table, {
                "type": operation_type,
                "details": operation_details,
                "duplicate_stats": duplicate_stats,
                "dropped_count": dropped_count,
                "original_count": original_count,
                "new_count": len(df)
            })
            
            return {
                "success": True,
                "message": f"Dropped {dropped_count} rows",
                "session_id": session_id,
                "table_name": target_table,
                "original_count": original_count,
                "new_count": len(df),
                "dropped_count": dropped_count,
                "duplicate_stats": duplicate_stats,
                "preview": df.head(5).to_dict(orient="records")
            }
        else:
            return {
                "success": False,
                "error": "Failed to save changes to session"
            }
            
    except Exception as e:
        logger.error(f"Failed to drop rows: {e}")
        return {
            "success": False,
            "error": f"Failed to drop rows: {str(e)}"
        }


def fill_missing(
    session_id: str,
    value: Optional[Any] = None,
    method: Optional[str] = None,
    values: Optional[Dict[str, Any]] = None,
    methods: Optional[Dict[str, str]] = None,
    interpolate_method: Optional[str] = None,
    columns: Optional[List[str]] = None,
    table_name: str = "current"
) -> Dict[str, Any]:
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
    """
    try:
        df = get_table_data(session_id, table_name)
        if df is None:
            return {
                "success": False,
                "error": f"Table '{table_name}' not found in session {session_id}"
            }
        
        # Determine columns to fill
        if columns is None:
            columns = list(df.columns)
        
        # Validate columns exist
        invalid_cols = [col for col in columns if col not in df.columns]
        if invalid_cols:
            return {
                "success": False,
                "error": f"Columns not found: {', '.join(invalid_cols)}"
            }
        
        filled_count = 0
        fill_details = {}
        
        for col in columns:
            if df[col].isnull().any():
                missing_before = df[col].isnull().sum()

                col_value = values.get(col) if values else None
                col_method = methods.get(col) if methods else None
                chosen_value = col_value if col_value is not None else value
                chosen_method = col_method if col_method is not None else method

                if chosen_value is not None:
                    df[col] = df[col].fillna(chosen_value)
                    fill_method = f"value_{chosen_value}"
                elif chosen_method == "ffill":
                    df[col] = df[col].ffill()
                    fill_method = "forward_fill"
                elif chosen_method == "bfill":
                    df[col] = df[col].bfill()
                    fill_method = "backward_fill"
                elif chosen_method == "mean":
                    df[col] = df[col].fillna(df[col].mean())
                    fill_method = "mean"
                elif chosen_method == "median":
                    df[col] = df[col].fillna(df[col].median())
                    fill_method = "median"
                elif chosen_method == "mode":
                    mode_val = df[col].mode()
                    if len(mode_val) > 0:
                        df[col] = df[col].fillna(mode_val.iloc[0])
                    fill_method = "mode"
                elif chosen_method == "interpolate":
                    df[col] = df[col].interpolate(method=interpolate_method or "linear")
                    fill_method = "interpolate"
                else:
                    return {
                        "success": False,
                        "error": f"Invalid fill method: {chosen_method}"
                    }
                
                missing_after = df[col].isnull().sum()
                filled_in_col = missing_before - missing_after
                filled_count += filled_in_col
                fill_details[col] = {
                    "method": fill_method,
                    "filled": filled_in_col,
                    "remaining_missing": missing_after
                }
        
        # Commit changes
        if commit_dataframe(session_id, table_name, df):
            # Record operation
            _record_operation(session_id, table_name, {
                "type": "fill_missing",
                "method": method,
                "value": value,
                "values": values,
                "methods": methods,
                "interpolate_method": interpolate_method,
                "columns": columns,
                "filled_count": filled_count,
                "fill_details": fill_details
            })
            
            return {
                "success": True,
                "message": f"Filled {filled_count} missing values",
                "session_id": session_id,
                "table_name": table_name,
                "filled_count": filled_count,
                "fill_details": fill_details,
                "preview": df.head(5).to_dict(orient="records")
            }
        else:
            return {
                "success": False,
                "error": "Failed to save changes to session"
            }
            
    except Exception as e:
        logger.error(f"Failed to fill missing values: {e}")
        return {
            "success": False,
            "error": f"Failed to fill missing values: {str(e)}"
        }


def drop_missing(
    session_id: str,
    how: str = "any",
    thresh: Optional[int] = None,
    axis: int = 0,
    subset: Optional[List[str]] = None,
    table_name: str = "current"
) -> Dict[str, Any]:
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
    """
    try:
        df = get_table_data(session_id, table_name)
        if df is None:
            return {
                "success": False,
                "error": f"Table '{table_name}' not found in session {session_id}"
            }
        
        original_shape = df.shape
        
        # Drop missing values
        df_cleaned = df.dropna(how=how, thresh=thresh, axis=axis, subset=subset)
        
        if axis == 0:
            # Dropped rows
            dropped_count = original_shape[0] - df_cleaned.shape[0]
            dropped_type = "rows"
            dropped_percentage = (dropped_count / original_shape[0]) * 100 if original_shape[0] else 0
        else:
            # Dropped columns
            dropped_count = original_shape[1] - df_cleaned.shape[1]
            dropped_type = "columns"
            dropped_percentage = (dropped_count / original_shape[1]) * 100 if original_shape[1] else 0
        
        # Commit changes
        if commit_dataframe(session_id, table_name, df_cleaned):
            # Record operation
            _record_operation(session_id, table_name, {
                "type": "drop_missing",
                "how": how,
                "thresh": thresh,
                "axis": axis,
                "subset": subset,
                "dropped_count": dropped_count,
                "dropped_type": dropped_type,
                "dropped_percentage": dropped_percentage,
                "original_shape": original_shape,
                "new_shape": df_cleaned.shape
            })
            
            return {
                "success": True,
                "message": f"Dropped {dropped_count} {dropped_type} with missing values",
                "session_id": session_id,
                "table_name": table_name,
                "dropped_count": dropped_count,
                "dropped_type": dropped_type,
                "dropped_percentage": dropped_percentage,
                "original_shape": original_shape,
                "new_shape": df_cleaned.shape,
                "preview": df_cleaned.head(5).to_dict(orient="records")
            }
        else:
            return {
                "success": False,
                "error": "Failed to save changes to session"
            }
            
    except Exception as e:
        logger.error(f"Failed to drop missing values: {e}")
        return {
            "success": False,
            "error": f"Failed to drop missing values: {str(e)}"
        }


def replace_values(
    session_id: str,
    to_replace: Dict[str, Dict[str, Any]],
    value: Optional[Any] = None,
    regex: bool = False,
    case_insensitive: bool = False,
    table_name: str = "current"
) -> Dict[str, Any]:
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
    """
    try:
        df = get_table_data(session_id, table_name)
        if df is None:
            return {
                "success": False,
                "error": f"Table '{table_name}' not found in session {session_id}"
            }
        
        replacement_details = {}
        
        def normalize_replacements(replacements: Dict[str, Any]) -> Dict[str, Any]:
            if not case_insensitive:
                return replacements
            updated = {}
            for key, replacement in replacements.items():
                if isinstance(key, str):
                    pattern = key if regex else re.escape(key)
                    updated[f"(?i){pattern}"] = replacement
                else:
                    updated[key] = replacement
            return updated

        for col, replacements in to_replace.items():
            if col not in df.columns:
                return {
                    "success": False,
                    "error": f"Column '{col}' not found in table"
                }

            before_series = df[col].copy()
            normalized_replacements = normalize_replacements(replacements)
            use_regex = regex or case_insensitive

            # Apply replacements
            if value is not None:
                # Replace all matching values with single value
                df[col] = df[col].replace(normalized_replacements, value, regex=use_regex)
                replacement_details[col] = {
                    "mode": "single_value",
                    "replacements": normalized_replacements,
                    "replacement_value": value,
                    "regex": use_regex
                }
            else:
                # Use replacement dictionary
                df[col] = df[col].replace(normalized_replacements, regex=use_regex)
                replacement_details[col] = {
                    "mode": "dictionary",
                    "replacements": normalized_replacements,
                    "regex": use_regex
                }

            after_series = df[col]
            unchanged = before_series.eq(after_series) | (before_series.isna() & after_series.isna())
            replaced_count = (~unchanged).sum()
            replacement_details[col]["replaced_count"] = int(replaced_count)
        
        # Commit changes
        if commit_dataframe(session_id, table_name, df):
            # Record operation
            _record_operation(session_id, table_name, {
                "type": "replace_values",
                "replacements": replacement_details
            })
            
            return {
                "success": True,
                "message": f"Replaced values in {len(to_replace)} columns",
                "session_id": session_id,
                "table_name": table_name,
                "replacements": replacement_details,
                "preview": df.head(5).to_dict(orient="records")
            }
        else:
            return {
                "success": False,
                "error": "Failed to save changes to session"
            }
            
    except Exception as e:
        logger.error(f"Failed to replace values: {e}")
        return {
            "success": False,
            "error": f"Failed to replace values: {str(e)}"
        }


def clean_strings(
    session_id: str,
    columns: List[str],
    operation: str = "strip",
    operations: Optional[List[str]] = None,
    pattern: Optional[str] = None,
    replacement: str = "",
    case_insensitive: bool = False,
    replace_regex: bool = True,
    table_name: str = "current"
) -> Dict[str, Any]:
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
    """
    try:
        df = get_table_data(session_id, table_name)
        if df is None:
            return {
                "success": False,
                "error": f"Table '{table_name}' not found in session {session_id}"
            }
        
        # Validate columns exist and are string type
        invalid_cols = []
        for col in columns:
            if col not in df.columns:
                invalid_cols.append(f"'{col}' not found")
            elif not pd.api.types.is_string_dtype(df[col]):
                invalid_cols.append(f"'{col}' is not a string column")
        
        if invalid_cols:
            return {
                "success": False,
                "error": f"Invalid columns: {', '.join(invalid_cols)}"
            }
        
        operations_list = operations or [operation]
        allowed_operations = {"strip", "lower", "upper", "title", "replace", "normalize"}
        invalid_ops = [op for op in operations_list if op not in allowed_operations]
        if invalid_ops:
            return {
                "success": False,
                "error": f"Invalid operations: {', '.join(invalid_ops)}"
            }
        if "replace" in operations_list and pattern is None:
            return {
                "success": False,
                "error": "Pattern must be provided for replace operation"
            }

        def normalize_text(value: Any) -> str:
            text = "" if pd.isna(value) else str(value)
            normalized = unicodedata.normalize("NFKD", text)
            return normalized.encode("ascii", "ignore").decode("ascii")

        # Apply cleaning operation(s)
        cleaning_details = {}
        
        for col in columns:
            before_series = df[col].copy()
            series = df[col].astype(str)

            for op in operations_list:
                if op == "strip":
                    series = series.str.strip()
                elif op == "lower":
                    series = series.str.lower()
                elif op == "upper":
                    series = series.str.upper()
                elif op == "title":
                    series = series.str.title()
                elif op == "replace":
                    flags = re.IGNORECASE if case_insensitive else 0
                    series = series.str.replace(
                        pattern,
                        replacement,
                        regex=replace_regex,
                        flags=flags
                    )
                elif op == "normalize":
                    series = series.map(normalize_text)

            df[col] = series
            unchanged = before_series.eq(df[col]) | (before_series.isna() & df[col].isna())
            cleaned_count = int((~unchanged).sum())

            cleaning_details[col] = {
                "operations": operations_list,
                "processed_count": cleaned_count
            }
        
        # Commit changes
        if commit_dataframe(session_id, table_name, df):
            # Record operation
            _record_operation(session_id, table_name, {
                "type": "clean_strings",
                "columns": columns,
                "operation": operation,
                "operations": operations_list,
                "pattern": pattern,
                "replacement": replacement,
                "case_insensitive": case_insensitive,
                "replace_regex": replace_regex,
                "cleaning_details": cleaning_details
            })
            
            return {
                "success": True,
                "message": f"Cleaned {len(columns)} string columns",
                "session_id": session_id,
                "table_name": table_name,
                "operation": operation,
                "operations": operations_list,
                "columns_cleaned": columns,
                "cleaning_details": cleaning_details,
                "preview": df.head(5).to_dict(orient="records")
            }
        else:
            return {
                "success": False,
                "error": "Failed to save changes to session"
            }
            
    except Exception as e:
        logger.error(f"Failed to clean strings: {e}")
        return {
            "success": False,
            "error": f"Failed to clean strings: {str(e)}"
        }


def remove_outliers(
    session_id: str,
    columns: List[str],
    method: str = "iqr",
    threshold: float = 1.5,
    table_name: str = "current",
    handle_method: str = "remove",
    include_boxplot: bool = False
) -> Dict[str, Any]:
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
    """
    try:
        df = get_table_data(session_id, table_name)
        if df is None:
            return {
                "success": False,
                "error": f"Table '{table_name}' not found in session {session_id}"
            }
        
        original_count = len(df)
        outlier_details = {}
        boxplot_stats = {}
        overall_mask = pd.Series(False, index=df.index)
        bounds_by_col = {}
        
        for col in columns:
            if col not in df.columns:
                return {
                    "success": False,
                    "error": f"Column '{col}' not found in table"
                }
            
            if not pd.api.types.is_numeric_dtype(df[col]):
                return {
                    "success": False,
                    "error": f"Column '{col}' is not numeric"
                }
            
            if method == "iqr":
                # IQR method
                q1 = df[col].quantile(0.25)
                q3 = df[col].quantile(0.75)
                iqr = q3 - q1
                lower_bound = q1 - threshold * iqr
                upper_bound = q3 + threshold * iqr

                outlier_mask = (df[col] < lower_bound) | (df[col] > upper_bound)

                outlier_details[col] = {
                    "method": "iqr",
                    "threshold": threshold,
                    "lower_bound": lower_bound,
                    "upper_bound": upper_bound,
                    "outliers_found": outlier_mask.sum()
                }
                bounds_by_col[col] = (lower_bound, upper_bound)
                boxplot_stats[col] = {
                    "q1": q1,
                    "median": df[col].median(),
                    "q3": q3,
                    "lower_bound": lower_bound,
                    "upper_bound": upper_bound
                }
                
            elif method == "zscore":
                # Z-score method
                std = df[col].std()
                if std == 0 or pd.isna(std):
                    outlier_mask = pd.Series(False, index=df.index)
                    lower_bound = None
                    upper_bound = None
                else:
                    mean = df[col].mean()
                    z_scores = np.abs((df[col] - mean) / std)
                    outlier_mask = z_scores > threshold
                    lower_bound = mean - threshold * std
                    upper_bound = mean + threshold * std
                
                outlier_details[col] = {
                    "method": "zscore",
                    "threshold": threshold,
                    "outliers_found": outlier_mask.sum(),
                    "mean": df[col].mean(),
                    "std": std
                }
                if lower_bound is not None and upper_bound is not None:
                    bounds_by_col[col] = (lower_bound, upper_bound)
            else:
                return {
                    "success": False,
                    "error": f"Invalid method: {method}. Use 'iqr' or 'zscore'"
                }

            overall_mask |= outlier_mask

        if handle_method not in {"remove", "cap", "winsorize"}:
            return {
                "success": False,
                "error": "handle_method must be 'remove', 'cap', or 'winsorize'"
            }

        if handle_method == "remove":
            df_result = df[~overall_mask]
        else:
            df_result = df.copy()
            for col, (lower_bound, upper_bound) in bounds_by_col.items():
                df_result[col] = df_result[col].clip(lower=lower_bound, upper=upper_bound)
        
        dropped_count = original_count - len(df_result)
        
        # Commit changes
        if commit_dataframe(session_id, table_name, df_result):
            # Record operation
            _record_operation(session_id, table_name, {
                "type": "remove_outliers",
                "method": method,
                "columns": columns,
                "threshold": threshold,
                "handle_method": handle_method,
                "outlier_details": outlier_details,
                "dropped_count": dropped_count
            })
            
            return {
                "success": True,
                "message": f"Handled outliers with '{handle_method}'",
                "session_id": session_id,
                "table_name": table_name,
                "method": method,
                "threshold": threshold,
                "handle_method": handle_method,
                "outlier_details": outlier_details,
                "boxplot_stats": boxplot_stats if include_boxplot else None,
                "dropped_count": dropped_count,
                "preview": df_result.head(5).to_dict(orient="records")
            }
        else:
            return {
                "success": False,
                "error": "Failed to save changes to session"
            }
            
    except Exception as e:
        logger.error(f"Failed to remove outliers: {e}")
        return {
            "success": False,
            "error": f"Failed to remove outliers: {str(e)}"
        }


def detect_missing(
    session_id: str,
    table_name: str = "current"
) -> Dict[str, Any]:
    """
    Summarize missing values per column.

    Args:
        session_id: Unique session identifier
        table_name: Name of the table (default: "current")

    Returns:
        Dictionary with missing value summary
    """
    try:
        df = get_table_data(session_id, table_name)
        if df is None:
            return {
                "success": False,
                "error": f"Table '{table_name}' not found in session {session_id}"
            }

        total_rows = len(df)
        missing_summary = {}
        for col in df.columns:
            missing_count = int(df[col].isna().sum())
            missing_summary[col] = {
                "missing_count": missing_count,
                "missing_percentage": (missing_count / total_rows) * 100 if total_rows else 0
            }

        _record_operation(session_id, table_name, {
            "type": "detect_missing"
        })

        return {
            "success": True,
            "message": "Computed missing value summary",
            "session_id": session_id,
            "table_name": table_name,
            "missing_summary": missing_summary
        }
    except Exception as e:
        logger.error(f"Failed to detect missing values: {e}")
        return {
            "success": False,
            "error": f"Failed to detect missing values: {str(e)}"
        }