"""Feature engineering tools for DataFrame manipulation."""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional
import logging
from datetime import datetime
from .core import load_current_dataframe, commit_dataframe

logger = logging.getLogger(__name__)


def create_date_features(session_id: str, date_column: str, features: List[str] = None, table_name: str = "current") -> Dict:
    """Extract year, month, day, weekday, quarter from date column."""
    try:
        df = load_current_dataframe(session_id, table_name)
        
        if date_column not in df.columns:
            return {
                "success": False,
                "error": f"Column '{date_column}' not found",
                "rows_before": len(df),
                "rows_after": len(df),
                "columns_before": len(df.columns),
                "columns_after": len(df.columns)
            }
        
        # Ensure date column is datetime
        if not pd.api.types.is_datetime64_any_dtype(df[date_column]):
            try:
                df[date_column] = pd.to_datetime(df[date_column])
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Could not convert '{date_column}' to datetime: {str(e)}",
                    "rows_before": len(df),
                    "rows_after": len(df),
                    "columns_before": len(df.columns),
                    "columns_after": len(df.columns)
                }
        
        df_result = df.copy()
        default_features = ["year", "month", "day", "weekday", "quarter", "is_weekend"]
        features_to_create = features if features else default_features
        
        features_created = []
        if "year" in features_to_create:
            df_result[f"{date_column}_year"] = df_result[date_column].dt.year
            features_created.append("year")
        if "month" in features_to_create:
            df_result[f"{date_column}_month"] = df_result[date_column].dt.month
            features_created.append("month")
        if "day" in features_to_create:
            df_result[f"{date_column}_day"] = df_result[date_column].dt.day
            features_created.append("day")
        if "weekday" in features_to_create:
            df_result[f"{date_column}_weekday"] = df_result[date_column].dt.weekday
            features_created.append("weekday")
        if "quarter" in features_to_create:
            df_result[f"{date_column}_quarter"] = df_result[date_column].dt.quarter
            features_created.append("quarter")
        if "is_weekend" in features_to_create:
            df_result[f"{date_column}_is_weekend"] = df_result[date_column].dt.weekday >= 5
            features_created.append("is_weekend")
        
        change_summary = f"Created {len(features_created)} date features from '{date_column}': {', '.join(features_created)}"
        
        return commit_dataframe(df_result, session_id, change_summary, table_name)
    except Exception as e:
        logger.error(f"Error in create_date_features: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "rows_before": 0,
            "rows_after": 0,
            "columns_before": 0,
            "columns_after": 0
        }


def bin_numeric(session_id: str, column: str, bins: int = 4, labels: List[str] = None, qcut: bool = False, table_name: str = "current") -> Dict:
    """Bin continuous column into categories."""
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
        
        if not pd.api.types.is_numeric_dtype(df[column]):
            return {
                "success": False,
                "error": f"Column '{column}' is not numeric",
                "rows_before": len(df),
                "rows_after": len(df),
                "columns_before": len(df.columns),
                "columns_after": len(df.columns)
            }
        
        df_result = df.copy()
        
        if qcut:
            # Quantile-based binning
            if labels:
                if len(labels) != bins:
                    return {
                        "success": False,
                        "error": f"Number of labels ({len(labels)}) must match number of bins ({bins})",
                        "rows_before": len(df),
                        "rows_after": len(df),
                        "columns_before": len(df.columns),
                        "columns_after": len(df.columns)
                    }
                df_result[f"{column}_binned"] = pd.qcut(df_result[column], q=bins, labels=labels, duplicates="drop")
            else:
                df_result[f"{column}_binned"] = pd.qcut(df_result[column], q=bins, duplicates="drop")
            method = "quantile"
        else:
            # Equal-width binning
            if labels:
                if len(labels) != bins:
                    return {
                        "success": False,
                        "error": f"Number of labels ({len(labels)}) must match number of bins ({bins})",
                        "rows_before": len(df),
                        "rows_after": len(df),
                        "columns_before": len(df.columns),
                        "columns_after": len(df.columns)
                    }
                df_result[f"{column}_binned"] = pd.cut(df_result[column], bins=bins, labels=labels)
            else:
                df_result[f"{column}_binned"] = pd.cut(df_result[column], bins=bins)
            method = "equal-width"
        
        change_summary = f"Binned '{column}' into {bins} {method} bins"
        if labels:
            change_summary += f" with labels: {', '.join(labels)}"
        
        return commit_dataframe(df_result, session_id, change_summary, table_name)
    except Exception as e:
        logger.error(f"Error in bin_numeric: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "rows_before": 0,
            "rows_after": 0,
            "columns_before": 0,
            "columns_after": 0
        }


def one_hot_encode(session_id: str, columns: List[str], drop_first: bool = False, table_name: str = "current") -> Dict:
    """One-hot encode categorical columns."""
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
        
        df_result = pd.get_dummies(df, columns=columns, drop_first=drop_first, prefix=columns, prefix_sep="_")
        
        new_cols = len(df_result.columns) - len(df.columns)
        change_summary = f"One-hot encoded {len(columns)} columns → {new_cols} new binary columns"
        if drop_first:
            change_summary += " (dropped first category)"
        
        return commit_dataframe(df_result, session_id, change_summary, table_name)
    except Exception as e:
        logger.error(f"Error in one_hot_encode: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "rows_before": 0,
            "rows_after": 0,
            "columns_before": 0,
            "columns_after": 0
        }


def scale_numeric(session_id: str, columns: List[str], method: str = "standard", table_name: str = "current") -> Dict:
    """Standardize or Min-Max scale numeric columns."""
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
        
        # Ensure columns are numeric
        numeric_cols = [col for col in columns if pd.api.types.is_numeric_dtype(df[col])]
        if len(numeric_cols) != len(columns):
            non_numeric = [col for col in columns if col not in numeric_cols]
            return {
                "success": False,
                "error": f"Non-numeric columns: {non_numeric}",
                "rows_before": len(df),
                "rows_after": len(df),
                "columns_before": len(df.columns),
                "columns_after": len(df.columns)
            }
        
        df_result = df.copy()
        
        if method == "standard":
            # Z-score normalization: (x - mean) / std
            for col in numeric_cols:
                mean = df_result[col].mean()
                std = df_result[col].std()
                if std != 0:
                    df_result[col] = (df_result[col] - mean) / std
            change_summary = f"Standardized (z-score) {len(numeric_cols)} columns"
        elif method == "minmax":
            # Min-Max scaling: (x - min) / (max - min)
            for col in numeric_cols:
                min_val = df_result[col].min()
                max_val = df_result[col].max()
                if max_val != min_val:
                    df_result[col] = (df_result[col] - min_val) / (max_val - min_val)
            change_summary = f"Min-Max scaled {len(numeric_cols)} columns to [0, 1]"
        else:
            return {
                "success": False,
                "error": f"Unknown method: {method}. Must be 'standard' or 'minmax'",
                "rows_before": len(df),
                "rows_after": len(df),
                "columns_before": len(df.columns),
                "columns_after": len(df.columns)
            }
        
        return commit_dataframe(df_result, session_id, change_summary, table_name)
    except Exception as e:
        logger.error(f"Error in scale_numeric: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "rows_before": 0,
            "rows_after": 0,
            "columns_before": 0,
            "columns_after": 0
        }


def create_interaction(session_id: str, col1: str, col2: str, new_name: str, operation: str = "multiply", table_name: str = "current") -> Dict:
    """Multiply or combine two columns."""
    try:
        df = load_current_dataframe(session_id, table_name)
        
        missing_cols = [col for col in [col1, col2] if col not in df.columns]
        if missing_cols:
            return {
                "success": False,
                "error": f"Columns not found: {missing_cols}",
                "rows_before": len(df),
                "rows_after": len(df),
                "columns_before": len(df.columns),
                "columns_after": len(df.columns)
            }
        
        if new_name in df.columns:
            return {
                "success": False,
                "error": f"Column '{new_name}' already exists",
                "rows_before": len(df),
                "rows_after": len(df),
                "columns_before": len(df.columns),
                "columns_after": len(df.columns)
            }
        
        df_result = df.copy()
        
        if operation == "multiply":
            df_result[new_name] = df_result[col1] * df_result[col2]
            op_symbol = "*"
        elif operation == "divide":
            df_result[new_name] = df_result[col1] / df_result[col2]
            op_symbol = "/"
        elif operation == "add":
            df_result[new_name] = df_result[col1] + df_result[col2]
            op_symbol = "+"
        elif operation == "subtract":
            df_result[new_name] = df_result[col1] - df_result[col2]
            op_symbol = "-"
        else:
            return {
                "success": False,
                "error": f"Unknown operation: {operation}. Must be 'multiply', 'divide', 'add', or 'subtract'",
                "rows_before": len(df),
                "rows_after": len(df),
                "columns_before": len(df.columns),
                "columns_after": len(df.columns)
            }
        
        change_summary = f"Created '{new_name}' = {col1} {op_symbol} {col2}"
        
        return commit_dataframe(df_result, session_id, change_summary, table_name)
    except Exception as e:
        logger.error(f"Error in create_interaction: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "rows_before": 0,
            "rows_after": 0,
            "columns_before": 0,
            "columns_after": 0
        }

