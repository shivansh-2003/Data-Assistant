"""
Data selection operations module for MCP Server.
Handles column selection, row filtering, and sampling operations.
"""

import logging
import re
from typing import List, Optional, Dict, Any
import pandas as pd

from .core import get_table_data, commit_dataframe, _record_operation

logger = logging.getLogger(__name__)


def select_columns(
    session_id: str,
    columns: List[str],
    keep: bool = True,
    table_name: str = "current",
    pattern: Optional[str] = None,
    dtypes: Optional[List[str]] = None,
    case_insensitive: bool = False
) -> Dict[str, Any]:
    """
    Select or drop specific columns from a table.
    
    Args:
        session_id: Unique session identifier
        columns: List of column names
        keep: If True, keep these columns; if False, drop these columns (default: True)
        table_name: Name of the table (default: "current")
        pattern: Regex pattern to match columns (optional)
        dtypes: List of dtypes to include (optional, e.g., ["number", "bool", "datetime"])
        case_insensitive: Case-insensitive regex matching (default: False)
    
    Returns:
        Dictionary with operation result and updated column count
    """
    try:
        df = get_table_data(session_id, table_name)
        if df is None:
            return {
                "success": False,
                "error": f"Table '{table_name}' not found in session {session_id}"
            }
        
        original_columns = list(df.columns)
        
        if not columns and not pattern and not dtypes:
            return {
                "success": False,
                "error": "Provide columns, pattern, or dtypes to select"
            }

        selected_set = set()
        if columns:
            invalid_cols = [col for col in columns if col not in df.columns]
            if invalid_cols:
                return {
                    "success": False,
                    "error": f"Columns not found: {', '.join(invalid_cols)}"
                }
            selected_set.update(columns)

        if pattern:
            regex = pattern
            if case_insensitive:
                regex = f"(?i){pattern}"
            pattern_cols = list(df.filter(regex=regex).columns)
            selected_set.update(pattern_cols)

        if dtypes:
            dtype_cols = list(df.select_dtypes(include=dtypes).columns)
            selected_set.update(dtype_cols)

        selected_cols = [col for col in original_columns if col in selected_set]
        if keep:
            df = df[selected_cols]
        else:
            df = df.drop(columns=selected_cols)
            selected_cols = [col for col in original_columns if col not in selected_set]
        
        # Commit changes
        if commit_dataframe(session_id, table_name, df):
            # Record operation
            _record_operation(session_id, table_name, {
                "type": "select_columns",
                "columns": columns,
                "keep": keep,
                "pattern": pattern,
                "dtypes": dtypes,
                "case_insensitive": case_insensitive,
                "original_columns": original_columns,
                "new_columns": list(df.columns)
            })
            
            return {
                "success": True,
                "message": f"{'Kept' if keep else 'Dropped'} {len(columns)} columns",
                "session_id": session_id,
                "table_name": table_name,
                "action": "keep" if keep else "drop",
                "columns_affected": list(selected_set),
                "original_column_count": len(original_columns),
                "new_column_count": len(df.columns),
                "selected_columns": selected_cols,
                "preview": df.head(5).to_dict(orient="records")
            }
        else:
            return {
                "success": False,
                "error": "Failed to save changes to session"
            }
            
    except Exception as e:
        logger.error(f"Failed to select columns: {e}")
        return {
            "success": False,
            "error": f"Failed to select columns: {str(e)}"
        }


def filter_rows(
    session_id: str,
    condition: str,
    table_name: str = "current",
    variables: Optional[Dict[str, Any]] = None,
    use_query: bool = True
) -> Dict[str, Any]:
    """
    Filter rows based on a boolean condition.
    
    Args:
        session_id: Unique session identifier
        condition: Boolean expression string (e.g., "Price > 11.0", "Company == 'Apple'")
        table_name: Name of the table (default: "current")
        variables: Optional variables for query evaluation
        use_query: Use pandas DataFrame.query when True (default: True)
    
    Returns:
        Dictionary with operation result and filtered row count
    """
    try:
        df = get_table_data(session_id, table_name)
        if df is None:
            return {
                "success": False,
                "error": f"Table '{table_name}' not found in session {session_id}"
            }
        
        original_count = len(df)
        
        def _normalize_condition(expr: str) -> Optional[str]:
            lower_map = {}
            for col in df.columns:
                key = col.lower()
                if key in lower_map:
                    return None
                lower_map[key] = col

            def replace_tokens(text: str) -> str:
                def repl(match: re.Match) -> str:
                    token = match.group(0)
                    return lower_map.get(token.lower(), token)
                return re.sub(r"\b[A-Za-z_][A-Za-z0-9_]*\b", repl, text)

            parts = re.split(r'(".*?"|\'.*?\')', expr)
            for idx, part in enumerate(parts):
                if idx % 2 == 0:
                    parts[idx] = replace_tokens(part)
            return "".join(parts)

        try:
            # Apply the condition
            if use_query:
                df_filtered = df.query(condition, local_dict=variables, engine="python")
            else:
                mask = df.eval(condition, engine="python", local_dict=variables)
                df_filtered = df[mask]
        except Exception as e:
            normalized = _normalize_condition(condition)
            if normalized and normalized != condition:
                try:
                    if use_query:
                        df_filtered = df.query(normalized, local_dict=variables, engine="python")
                    else:
                        mask = df.eval(normalized, engine="python", local_dict=variables)
                        df_filtered = df[mask]
                except Exception:
                    pass
                else:
                    condition = normalized
            if 'df_filtered' not in locals():
                return {
                    "success": False,
                    "error": (
                        f"Invalid condition '{condition}': {str(e)}. "
                        "Use a pandas-style boolean expression, e.g. "
                        "'Price > 11', 'Company == \"Apple\"', "
                        "'Company == \"Apple\" and Ram >= 8'. "
                        "Column names are case-sensitive; available columns: "
                        f"{', '.join(df.columns)}"
                    )
                }
        
        filtered_count = len(df_filtered)
        dropped_count = original_count - filtered_count
        
        # Commit changes
        if commit_dataframe(session_id, table_name, df_filtered):
            # Record operation
            _record_operation(session_id, table_name, {
                "type": "filter_rows",
                "condition": condition,
                "variables": variables,
                "use_query": use_query,
                "original_count": original_count,
                "filtered_count": filtered_count,
                "dropped_count": dropped_count
            })
            
            return {
                "success": True,
                "message": f"Filtered to {filtered_count} rows ({dropped_count} rows removed)",
                "session_id": session_id,
                "table_name": table_name,
                "condition": condition,
                "original_count": original_count,
                "filtered_count": filtered_count,
                "dropped_count": dropped_count,
                "preview": df_filtered.head(5).to_dict(orient="records")
            }
        else:
            return {
                "success": False,
                "error": "Failed to save changes to session"
            }
            
    except Exception as e:
        logger.error(f"Failed to filter rows: {e}")
        return {
            "success": False,
            "error": f"Failed to filter rows: {str(e)}"
        }


def sample_rows(
    session_id: str,
    n: Optional[int] = None,
    frac: Optional[float] = None,
    random_state: Optional[int] = None,
    table_name: str = "current",
    by: Optional[str] = None,
    replace: bool = False
) -> Dict[str, Any]:
    """
    Sample random rows from a table.
    
    Args:
        session_id: Unique session identifier
        n: Number of rows to sample (optional)
        frac: Fraction of rows to sample (0.0 to 1.0) (optional)
        random_state: Random seed for reproducibility (optional)
        table_name: Name of the table (default: "current")
        by: Column name for stratified sampling (optional)
        replace: Sample with replacement (default: False)
    
    Returns:
        Dictionary with operation result and sampled row count
    """
    try:
        df = get_table_data(session_id, table_name)
        if df is None:
            return {
                "success": False,
                "error": f"Table '{table_name}' not found in session {session_id}"
            }
        
        original_count = len(df)
        
        # Validate sampling parameters
        if n is not None and frac is not None:
            return {
                "success": False,
                "error": "Cannot specify both 'n' and 'frac' parameters"
            }
        
        if n is not None:
            if n <= 0:
                return {
                    "success": False,
                    "error": "Sample size 'n' must be positive"
                }
            if n > original_count:
                return {
                    "success": False,
                    "error": f"Sample size {n} exceeds table size {original_count}"
                }
        
        if frac is not None:
            if frac <= 0 or frac > 1:
                return {
                    "success": False,
                    "error": "Fraction 'frac' must be between 0 and 1"
                }

        if by is not None and by not in df.columns:
            return {
                "success": False,
                "error": f"Column '{by}' not found in table"
            }
        
        # Sample the data
        if by is None:
            df_sampled = df.sample(n=n, frac=frac, random_state=random_state, replace=replace)
        else:
            grouped = df.groupby(by, group_keys=False)
            if n is not None:
                if not replace and any(grouped.size() < n):
                    return {
                        "success": False,
                        "error": "Sample size exceeds group size for stratified sampling"
                    }
                df_sampled = grouped.apply(lambda g: g.sample(n=n, random_state=random_state, replace=replace))
            else:
                df_sampled = grouped.apply(lambda g: g.sample(frac=frac, random_state=random_state, replace=replace))
        sampled_count = len(df_sampled)
        
        # Commit changes (this creates a new table state)
        if commit_dataframe(session_id, table_name, df_sampled):
            # Record operation
            _record_operation(session_id, table_name, {
                "type": "sample_rows",
                "n": n,
                "frac": frac,
                "random_state": random_state,
                "by": by,
                "replace": replace,
                "original_count": original_count,
                "sampled_count": sampled_count
            })
            
            return {
                "success": True,
                "message": f"Sampled {sampled_count} rows",
                "session_id": session_id,
                "table_name": table_name,
                "sampling_method": "n_rows" if n is not None else "fraction",
                "sampling_value": n if n is not None else frac,
                "random_state": random_state,
                "by": by,
                "replace": replace,
                "original_count": original_count,
                "sampled_count": sampled_count,
                "preview": df_sampled.head(5).to_dict(orient="records")
            }
        else:
            return {
                "success": False,
                "error": "Failed to save changes to session"
            }
            
    except Exception as e:
        logger.error(f"Failed to sample rows: {e}")
        return {
            "success": False,
            "error": f"Failed to sample rows: {str(e)}"
        }


def head_rows(
    session_id: str,
    n: int = 5,
    table_name: str = "current"
) -> Dict[str, Any]:
    """
    Return the first n rows of a table without modifying it.
    """
    try:
        df = get_table_data(session_id, table_name)
        if df is None:
            return {
                "success": False,
                "error": f"Table '{table_name}' not found in session {session_id}"
            }
        if n <= 0:
            return {
                "success": False,
                "error": "n must be positive"
            }

        preview_df = df.head(n)
        _record_operation(session_id, table_name, {
            "type": "head_rows",
            "n": n
        })
        return {
            "success": True,
            "message": f"Retrieved first {n} rows",
            "session_id": session_id,
            "table_name": table_name,
            "preview": preview_df.to_dict(orient="records")
        }
    except Exception as e:
        logger.error(f"Failed to retrieve head rows: {e}")
        return {
            "success": False,
            "error": f"Failed to retrieve head rows: {str(e)}"
        }


def tail_rows(
    session_id: str,
    n: int = 5,
    table_name: str = "current"
) -> Dict[str, Any]:
    """
    Return the last n rows of a table without modifying it.
    """
    try:
        df = get_table_data(session_id, table_name)
        if df is None:
            return {
                "success": False,
                "error": f"Table '{table_name}' not found in session {session_id}"
            }
        if n <= 0:
            return {
                "success": False,
                "error": "n must be positive"
            }

        preview_df = df.tail(n)
        _record_operation(session_id, table_name, {
            "type": "tail_rows",
            "n": n
        })
        return {
            "success": True,
            "message": f"Retrieved last {n} rows",
            "session_id": session_id,
            "table_name": table_name,
            "preview": preview_df.to_dict(orient="records")
        }
    except Exception as e:
        logger.error(f"Failed to retrieve tail rows: {e}")
        return {
            "success": False,
            "error": f"Failed to retrieve tail rows: {str(e)}"
        }


def slice_rows(
    session_id: str,
    start: int,
    end: Optional[int] = None,
    step: Optional[int] = None,
    table_name: str = "current"
) -> Dict[str, Any]:
    """
    Return a slice of rows using iloc without modifying the table.
    """
    try:
        df = get_table_data(session_id, table_name)
        if df is None:
            return {
                "success": False,
                "error": f"Table '{table_name}' not found in session {session_id}"
            }
        if start is None:
            return {
                "success": False,
                "error": "Start index is required"
            }

        preview_df = df.iloc[start:end:step]
        _record_operation(session_id, table_name, {
            "type": "slice_rows",
            "start": start,
            "end": end,
            "step": step
        })
        return {
            "success": True,
            "message": "Retrieved row slice",
            "session_id": session_id,
            "table_name": table_name,
            "preview": preview_df.to_dict(orient="records")
        }
    except Exception as e:
        logger.error(f"Failed to slice rows: {e}")
        return {
            "success": False,
            "error": f"Failed to slice rows: {str(e)}"
        }