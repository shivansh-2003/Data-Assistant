"""
Data aggregation operations module for MCP Server.
Handles group-by operations and statistical descriptions.
"""

import logging
from typing import List, Dict, Optional, Any
import pandas as pd

from .core import get_table_data, commit_dataframe, _record_operation

logger = logging.getLogger(__name__)


def group_by_agg(
    session_id: str,
    by: List[str],
    agg: Dict[str, str],
    table_name: str = "current",
    as_index: bool = False
) -> Dict[str, Any]:
    """
    Group table by columns and compute aggregations.
    
    Args:
        session_id: Unique session identifier
        by: Column names to group by
        agg: Dictionary mapping column names to aggregation functions
             (e.g., {"Price": "mean", "Ram": "sum"})
             Supported functions: "sum", "mean", "count", "min", "max", "std", "median"
        table_name: Name of the table (default: "current")
        as_index: Keep group keys as index if True (default: False)
    
    Returns:
        Dictionary with operation result and aggregated table
    """
    try:
        df = get_table_data(session_id, table_name)
        if df is None:
            return {
                "success": False,
                "error": f"Table '{table_name}' not found in session {session_id}"
            }

        if not by:
            return {
                "success": False,
                "error": "Group-by columns cannot be empty"
            }

        missing_group_cols = [col for col in by if col not in df.columns]
        if missing_group_cols:
            return {
                "success": False,
                "error": f"Group-by columns not found: {', '.join(missing_group_cols)}"
            }

        if not agg:
            return {
                "success": False,
                "error": "Aggregation mapping cannot be empty"
            }

        missing_agg_cols = [col for col in agg.keys() if col not in df.columns]
        if missing_agg_cols:
            return {
                "success": False,
                "error": f"Aggregation columns not found: {', '.join(missing_agg_cols)}"
            }

        supported_aggs = {"sum", "mean", "count", "min", "max", "std", "median"}
        for col, funcs in agg.items():
            if isinstance(funcs, (list, tuple, set)):
                invalid = [f for f in funcs if f not in supported_aggs]
                if invalid:
                    return {
                        "success": False,
                        "error": f"Unsupported aggregations for '{col}': {', '.join(invalid)}"
                    }
            elif isinstance(funcs, str):
                if funcs not in supported_aggs:
                    return {
                        "success": False,
                        "error": f"Unsupported aggregation '{funcs}' for '{col}'"
                    }
            else:
                return {
                    "success": False,
                    "error": f"Invalid aggregation spec for '{col}'"
                }

        aggregated_df = df.groupby(by=by, as_index=as_index).agg(agg)

        if commit_dataframe(session_id, table_name, aggregated_df):
            _record_operation(session_id, table_name, {
                "type": "group_by_agg",
                "group_by": by,
                "agg": agg,
                "as_index": as_index,
                "rows_before": len(df),
                "rows_after": len(aggregated_df)
            })
            return {
                "success": True,
                "message": "Grouped and aggregated table",
                "session_id": session_id,
                "table_name": table_name,
                "preview": aggregated_df.head(5).reset_index().to_dict(orient="records")
            }
        return {
            "success": False,
            "error": "Failed to save aggregated table to session"
        }
    except Exception as e:
        logger.error(f"Failed to group and aggregate: {e}")
        return {
            "success": False,
            "error": f"Failed to group and aggregate: {str(e)}"
        }


def describe_stats(
    session_id: str,
    group_by: Optional[List[str]] = None,
    table_name: str = "current"
) -> Dict[str, Any]:
    """
    Get descriptive statistics for numeric columns, optionally grouped.
    
    Args:
        session_id: Unique session identifier
        group_by: Column names to group by (optional)
        table_name: Name of the table (default: "current")
    
    Returns:
        Dictionary with operation result and statistics table
    """
    try:
        df = get_table_data(session_id, table_name)
        if df is None:
            return {
                "success": False,
                "error": f"Table '{table_name}' not found in session {session_id}"
            }

        if group_by:
            missing_group_cols = [col for col in group_by if col not in df.columns]
            if missing_group_cols:
                return {
                    "success": False,
                    "error": f"Group-by columns not found: {', '.join(missing_group_cols)}"
                }
            stats_df = df.groupby(group_by).describe(include="all")
        else:
            stats_df = df.describe(include="all")

        preview_df = stats_df.head(5)
        try:
            preview = preview_df.reset_index().to_dict(orient="records")
        except Exception:
            preview = preview_df.to_dict()

        _record_operation(session_id, table_name, {
            "type": "describe_stats",
            "group_by": group_by
        })

        return {
            "success": True,
            "message": "Generated descriptive statistics",
            "session_id": session_id,
            "table_name": table_name,
            "group_by": group_by,
            "statistics": stats_df.to_dict(),
            "preview": preview
        }
    except Exception as e:
        logger.error(f"Failed to describe statistics: {e}")
        return {
            "success": False,
            "error": f"Failed to describe statistics: {str(e)}"
        }