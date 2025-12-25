"""Row and column selection tools for DataFrame manipulation."""

import pandas as pd
from typing import Dict, List, Optional
import logging
from .core import load_current_dataframe, commit_dataframe

logger = logging.getLogger(__name__)


def select_columns(session_id: str, columns: List[str], keep: bool = True, table_name: str = "current") -> Dict:
    """Keep or drop specific columns."""
    try:
        df = load_current_dataframe(session_id, table_name)
        cols_before = len(df.columns)
        
        missing_cols = [col for col in columns if col not in df.columns]
        if missing_cols:
            return {
                "success": False,
                "error": f"Columns not found: {missing_cols}",
                "rows_before": len(df),
                "rows_after": len(df),
                "columns_before": cols_before,
                "columns_after": cols_before
            }
        
        if keep:
            df_result = df[columns].copy()
            change_summary = f"Kept {len(columns)} columns: {', '.join(columns[:5])}{'...' if len(columns) > 5 else ''}"
        else:
            df_result = df.drop(columns=columns).copy()
            change_summary = f"Dropped {len(columns)} columns: {', '.join(columns[:5])}{'...' if len(columns) > 5 else ''}"
        
        return commit_dataframe(df_result, session_id, change_summary, table_name)
    except Exception as e:
        logger.error(f"Error in select_columns: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "rows_before": 0,
            "rows_after": 0,
            "columns_before": 0,
            "columns_after": 0
        }


def filter_rows(session_id: str, condition: str, table_name: str = "current") -> Dict:
    """Filter rows by condition (supports simple expressions)."""
    try:
        df = load_current_dataframe(session_id, table_name)
        rows_before = len(df)
        
        # Validate condition by trying to evaluate it
        try:
            mask = df.eval(condition)
            if not isinstance(mask, pd.Series):
                return {
                    "success": False,
                    "error": "Condition must evaluate to a boolean Series",
                    "rows_before": rows_before,
                    "rows_after": rows_before,
                    "columns_before": len(df.columns),
                    "columns_after": len(df.columns)
                }
            df_result = df[mask].copy()
        except Exception as e:
            return {
                "success": False,
                "error": f"Invalid condition expression: {str(e)}",
                "rows_before": rows_before,
                "rows_after": rows_before,
                "columns_before": len(df.columns),
                "columns_after": len(df.columns)
            }
        
        rows_after = len(df_result)
        rows_filtered = rows_before - rows_after
        change_summary = f"Filtered to {rows_after} rows (removed {rows_filtered} rows) matching condition: {condition}"
        
        return commit_dataframe(df_result, session_id, change_summary, table_name)
    except Exception as e:
        logger.error(f"Error in filter_rows: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "rows_before": 0,
            "rows_after": 0,
            "columns_before": 0,
            "columns_after": 0
        }


def sample_rows(session_id: str, n: int = None, frac: float = None, random_state: int = None, table_name: str = "current") -> Dict:
    """Random or fractional sample."""
    try:
        df = load_current_dataframe(session_id, table_name)
        rows_before = len(df)
        
        if n is None and frac is None:
            return {
                "success": False,
                "error": "Must specify either n (number of rows) or frac (fraction)",
                "rows_before": rows_before,
                "rows_after": rows_before,
                "columns_before": len(df.columns),
                "columns_after": len(df.columns)
            }
        
        if n is not None and n > rows_before:
            n = rows_before
            logger.warning(f"Requested {n} rows but only {rows_before} available, sampling all rows")
        
        if frac is not None and (frac <= 0 or frac > 1):
            return {
                "success": False,
                "error": "Fraction must be between 0 and 1",
                "rows_before": rows_before,
                "rows_after": rows_before,
                "columns_before": len(df.columns),
                "columns_after": len(df.columns)
            }
        
        df_result = df.sample(n=n, frac=frac, random_state=random_state).copy()
        
        if n is not None:
            change_summary = f"Sampled {len(df_result)} rows randomly"
        else:
            change_summary = f"Sampled {frac*100:.1f}% of rows ({len(df_result)} rows)"
        
        return commit_dataframe(df_result, session_id, change_summary, table_name)
    except Exception as e:
        logger.error(f"Error in sample_rows: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "rows_before": 0,
            "rows_after": 0,
            "columns_before": 0,
            "columns_after": 0
        }

