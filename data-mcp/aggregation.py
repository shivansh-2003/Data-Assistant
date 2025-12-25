"""Data aggregation and grouping tools for DataFrame manipulation."""

import pandas as pd
from typing import Dict, List, Optional
import logging
from .core import load_current_dataframe, commit_dataframe

logger = logging.getLogger(__name__)


def group_by_agg(session_id: str, by: List[str], agg: Dict[str, str], table_name: str = "current") -> Dict:
    """Group and aggregate."""
    try:
        df = load_current_dataframe(session_id, table_name)
        
        all_cols = by + list(agg.keys())
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
        
        # Map string aggfuncs to pandas functions
        aggfunc_map = {
            "sum": "sum",
            "mean": "mean",
            "count": "count",
            "min": "min",
            "max": "max",
            "std": "std",
            "median": "median",
            "first": "first",
            "last": "last"
        }
        
        # Convert agg dict to proper format
        agg_dict = {}
        for col, func in agg.items():
            agg_dict[col] = aggfunc_map.get(func.lower(), func)
        
        df_result = df.groupby(by).agg(agg_dict).reset_index().copy()
        
        agg_list = [f"{func}({col})" for col, func in agg.items()]
        change_summary = f"Grouped by {', '.join(by)}: computed {', '.join(agg_list)}"
        
        return commit_dataframe(df_result, session_id, change_summary, table_name)
    except Exception as e:
        logger.error(f"Error in group_by_agg: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "rows_before": 0,
            "rows_after": 0,
            "columns_before": 0,
            "columns_after": 0
        }


def describe_stats(session_id: str, group_by: List[str] = None, table_name: str = "current") -> Dict:
    """Get summary statistics (optionally per group)."""
    try:
        df = load_current_dataframe(session_id, table_name)
        
        if group_by:
            missing_cols = [col for col in group_by if col not in df.columns]
            if missing_cols:
                return {
                    "success": False,
                    "error": f"Columns not found: {missing_cols}",
                    "rows_before": len(df),
                    "rows_after": len(df),
                    "columns_before": len(df.columns),
                    "columns_after": len(df.columns)
                }
            df_result = df.groupby(group_by).describe().reset_index().copy()
            change_summary = f"Generated descriptive statistics grouped by {', '.join(group_by)}"
        else:
            # Get numeric columns only for describe
            numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
            if len(numeric_cols) == 0:
                return {
                    "success": False,
                    "error": "No numeric columns found for statistics",
                    "rows_before": len(df),
                    "rows_after": len(df),
                    "columns_before": len(df.columns),
                    "columns_after": len(df.columns)
                }
            df_result = df[numeric_cols].describe().reset_index().copy()
            change_summary = "Generated descriptive statistics for all numeric columns"
        
        return commit_dataframe(df_result, session_id, change_summary, table_name)
    except Exception as e:
        logger.error(f"Error in describe_stats: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "rows_before": 0,
            "rows_after": 0,
            "columns_before": 0,
            "columns_after": 0
        }

