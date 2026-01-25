"""
Feature engineering operations module for MCP Server.
Handles date features, binning, encoding, scaling, and interactions.
"""

import logging
from typing import List, Optional, Dict, Any
import pandas as pd

from .core import get_table_data, commit_dataframe, _record_operation

logger = logging.getLogger(__name__)


def create_date_features(
    session_id: str,
    date_column: str,
    features: Optional[List[str]] = None,
    table_name: str = "current",
    date_format: Optional[str] = None
) -> Dict[str, Any]:
    """
    Extract date features (year, month, day, weekday, quarter, is_weekend) from a date column.
    
    Args:
        session_id: Unique session identifier
        date_column: Name of the date column
        features: List of features to extract - "year", "month", "day", "weekday", "quarter", "is_weekend"
                  (optional, extracts all if not specified)
        table_name: Name of the table (default: "current")
        date_format: Optional datetime format for parsing
    
    Returns:
        Dictionary with operation result and new feature columns
    """
    try:
        df = get_table_data(session_id, table_name)
        if df is None:
            return {
                "success": False,
                "error": f"Table '{table_name}' not found in session {session_id}"
            }

        if date_column not in df.columns:
            return {
                "success": False,
                "error": f"Column '{date_column}' not found"
            }

        allowed_features = {"year", "month", "day", "weekday", "quarter", "is_weekend"}
        selected_features = features or sorted(allowed_features)
        invalid_features = [feat for feat in selected_features if feat not in allowed_features]
        if invalid_features:
            return {
                "success": False,
                "error": f"Unsupported date features: {', '.join(invalid_features)}"
            }

        parsed_dates = pd.to_datetime(df[date_column], format=date_format, errors="coerce")
        if parsed_dates.isna().all():
            return {
                "success": False,
                "error": f"Failed to parse any dates in '{date_column}'"
            }

        for feature in selected_features:
            new_col = f"{date_column}_{feature}"
            if feature == "year":
                df[new_col] = parsed_dates.dt.year
            elif feature == "month":
                df[new_col] = parsed_dates.dt.month
            elif feature == "day":
                df[new_col] = parsed_dates.dt.day
            elif feature == "weekday":
                df[new_col] = parsed_dates.dt.weekday
            elif feature == "quarter":
                df[new_col] = parsed_dates.dt.quarter
            elif feature == "is_weekend":
                df[new_col] = parsed_dates.dt.weekday >= 5

        if commit_dataframe(session_id, table_name, df):
            _record_operation(session_id, table_name, {
                "type": "create_date_features",
                "date_column": date_column,
                "features": selected_features,
                "date_format": date_format
            })
            return {
                "success": True,
                "message": f"Created date features from '{date_column}'",
                "session_id": session_id,
                "table_name": table_name,
                "created_features": selected_features,
                "preview": df.head(5).to_dict(orient="records")
            }
        return {
            "success": False,
            "error": "Failed to save changes to session"
        }
    except Exception as e:
        logger.error(f"Failed to create date features: {e}")
        return {
            "success": False,
            "error": f"Failed to create date features: {str(e)}"
        }


def bin_numeric(
    session_id: str,
    column: str,
    bins: int = 4,
    labels: Optional[List[str]] = None,
    qcut: bool = False,
    table_name: str = "current"
) -> Dict[str, Any]:
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
                "error": f"Column '{column}' not found"
            }
        if not pd.api.types.is_numeric_dtype(df[column]):
            return {
                "success": False,
                "error": f"Column '{column}' must be numeric for binning"
            }
        if bins <= 0:
            return {
                "success": False,
                "error": "Bins must be a positive integer"
            }
        if labels is not None and len(labels) != bins:
            return {
                "success": False,
                "error": "Labels length must match number of bins"
            }

        new_col = f"{column}_binned"
        if qcut:
            df[new_col] = pd.qcut(df[column], q=bins, labels=labels)
        else:
            df[new_col] = pd.cut(df[column], bins=bins, labels=labels)

        if commit_dataframe(session_id, table_name, df):
            _record_operation(session_id, table_name, {
                "type": "bin_numeric",
                "column": column,
                "bins": bins,
                "labels": labels,
                "qcut": qcut,
                "new_column": new_col
            })
            return {
                "success": True,
                "message": f"Binned '{column}' into '{new_col}'",
                "session_id": session_id,
                "table_name": table_name,
                "new_column": new_col,
                "preview": df.head(5).to_dict(orient="records")
            }
        return {
            "success": False,
            "error": "Failed to save changes to session"
        }
    except Exception as e:
        logger.error(f"Failed to bin numeric column: {e}")
        return {
            "success": False,
            "error": f"Failed to bin numeric column: {str(e)}"
        }


def one_hot_encode(
    session_id: str,
    columns: List[str],
    drop_first: bool = False,
    table_name: str = "current"
) -> Dict[str, Any]:
    """
    One-hot encode categorical columns into binary columns.
    
    Args:
        session_id: Unique session identifier
        columns: List of categorical column names
        drop_first: Drop first category to avoid multicollinearity (default: False)
        table_name: Name of the table (default: "current")
    
    Returns:
        Dictionary with operation result and new binary columns
    """
    try:
        df = get_table_data(session_id, table_name)
        if df is None:
            return {
                "success": False,
                "error": f"Table '{table_name}' not found in session {session_id}"
            }
        missing_cols = [col for col in columns if col not in df.columns]
        if missing_cols:
            return {
                "success": False,
                "error": f"Columns not found: {', '.join(missing_cols)}"
            }

        before_columns = set(df.columns)
        encoded_df = pd.get_dummies(df, columns=columns, drop_first=drop_first)
        new_columns = [col for col in encoded_df.columns if col not in before_columns]

        if commit_dataframe(session_id, table_name, encoded_df):
            _record_operation(session_id, table_name, {
                "type": "one_hot_encode",
                "columns": columns,
                "drop_first": drop_first,
                "new_columns": new_columns
            })
            return {
                "success": True,
                "message": f"One-hot encoded columns: {', '.join(columns)}",
                "session_id": session_id,
                "table_name": table_name,
                "new_columns": new_columns,
                "preview": encoded_df.head(5).to_dict(orient="records")
            }
        return {
            "success": False,
            "error": "Failed to save changes to session"
        }
    except Exception as e:
        logger.error(f"Failed to one-hot encode: {e}")
        return {
            "success": False,
            "error": f"Failed to one-hot encode: {str(e)}"
        }


def scale_numeric(
    session_id: str,
    columns: List[str],
    method: str = "standard",
    table_name: str = "current"
) -> Dict[str, Any]:
    """
    Scale numeric columns (standardization or min-max scaling).
    
    Args:
        session_id: Unique session identifier
        columns: List of numeric column names
        method: Scaling method - "standard" (z-score) or "minmax" (0-1 range) (default: "standard")
        table_name: Name of the table (default: "current")
    
    Returns:
        Dictionary with operation result and scaled columns
    """
    try:
        df = get_table_data(session_id, table_name)
        if df is None:
            return {
                "success": False,
                "error": f"Table '{table_name}' not found in session {session_id}"
            }
        missing_cols = [col for col in columns if col not in df.columns]
        if missing_cols:
            return {
                "success": False,
                "error": f"Columns not found: {', '.join(missing_cols)}"
            }
        non_numeric = [col for col in columns if not pd.api.types.is_numeric_dtype(df[col])]
        if non_numeric:
            return {
                "success": False,
                "error": f"Columns must be numeric for scaling: {', '.join(non_numeric)}"
            }

        method = method.lower()
        if method not in {"standard", "minmax", "robust"}:
            return {
                "success": False,
                "error": "Method must be 'standard', 'minmax', or 'robust'"
            }

        scaled_df = df.copy()
        for col in columns:
            series = scaled_df[col]
            if method == "standard":
                std = series.std()
                if std == 0 or pd.isna(std):
                    scaled_df[col] = 0
                else:
                    scaled_df[col] = (series - series.mean()) / std
            elif method == "minmax":
                min_val = series.min()
                max_val = series.max()
                if pd.isna(min_val) or pd.isna(max_val) or min_val == max_val:
                    scaled_df[col] = 0
                else:
                    scaled_df[col] = (series - min_val) / (max_val - min_val)
            else:
                median = series.median()
                q1 = series.quantile(0.25)
                q3 = series.quantile(0.75)
                iqr = q3 - q1
                if iqr == 0 or pd.isna(iqr):
                    scaled_df[col] = 0
                else:
                    scaled_df[col] = (series - median) / iqr

        if commit_dataframe(session_id, table_name, scaled_df):
            _record_operation(session_id, table_name, {
                "type": "scale_numeric",
                "columns": columns,
                "method": method
            })
            return {
                "success": True,
                "message": f"Scaled columns using {method} method",
                "session_id": session_id,
                "table_name": table_name,
                "scaled_columns": columns,
                "preview": scaled_df.head(5).to_dict(orient="records")
            }
        return {
            "success": False,
            "error": "Failed to save changes to session"
        }
    except Exception as e:
        logger.error(f"Failed to scale numeric columns: {e}")
        return {
            "success": False,
            "error": f"Failed to scale numeric columns: {str(e)}"
        }


def create_interaction(
    session_id: str,
    col1: str,
    col2: str,
    new_name: str,
    operation: str = "multiply",
    table_name: str = "current"
) -> Dict[str, Any]:
    """
    Create interaction feature from two columns.
    
    Args:
        session_id: Unique session identifier
        col1: First column name
        col2: Second column name
        new_name: Name for the new interaction column
        operation: Interaction operation - "multiply", "add", "subtract", "divide" (default: "multiply")
        table_name: Name of the table (default: "current")
    
    Returns:
        Dictionary with operation result and new interaction column
    """
    try:
        df = get_table_data(session_id, table_name)
        if df is None:
            return {
                "success": False,
                "error": f"Table '{table_name}' not found in session {session_id}"
            }

        for col in (col1, col2):
            if col not in df.columns:
                return {
                    "success": False,
                    "error": f"Column '{col}' not found"
                }

        operation = operation.lower()
        if operation not in {"multiply", "add", "subtract", "divide", "concat"}:
            return {
                "success": False,
                "error": "Operation must be 'multiply', 'add', 'subtract', 'divide', or 'concat'"
            }

        if operation == "concat":
            df[new_name] = df[col1].astype(str) + df[col2].astype(str)
        else:
            if not pd.api.types.is_numeric_dtype(df[col1]) or not pd.api.types.is_numeric_dtype(df[col2]):
                return {
                    "success": False,
                    "error": "Both columns must be numeric for numeric operations"
                }
            if operation == "multiply":
                df[new_name] = df[col1] * df[col2]
            elif operation == "add":
                df[new_name] = df[col1] + df[col2]
            elif operation == "subtract":
                df[new_name] = df[col1] - df[col2]
            elif operation == "divide":
                safe_divisor = df[col2].replace(0, pd.NA)
                df[new_name] = df[col1] / safe_divisor

        if commit_dataframe(session_id, table_name, df):
            _record_operation(session_id, table_name, {
                "type": "create_interaction",
                "col1": col1,
                "col2": col2,
                "new_name": new_name,
                "operation": operation
            })
            return {
                "success": True,
                "message": f"Created interaction column '{new_name}'",
                "session_id": session_id,
                "table_name": table_name,
                "new_column": new_name,
                "preview": df.head(5).to_dict(orient="records")
            }
        return {
            "success": False,
            "error": "Failed to save changes to session"
        }
    except Exception as e:
        logger.error(f"Failed to create interaction feature: {e}")
        return {
            "success": False,
            "error": f"Failed to create interaction feature: {str(e)}"
        }