"""Core state management for data manipulation operations."""

import pandas as pd
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

# Module-level session state storage
# Structure: {session_id: {"tables": {table_name: df}, "history": {table_name: [df]}, "history_index": {table_name: int}, "undo_stack": {table_name: [df]}}}
_session_states: Dict[str, Dict] = {}


def _get_session_state(session_id: str) -> Dict:
    """Get or create session state."""
    if session_id not in _session_states:
        _session_states[session_id] = {
            "tables": {},
            "history": {},
            "history_index": {},
            "undo_stack": {}
        }
    return _session_states[session_id]


def load_current_dataframe(session_id: str, table_name: str = "current") -> pd.DataFrame:
    """Load DataFrame from session state."""
    state = _get_session_state(session_id)
    if table_name not in state["tables"]:
        raise ValueError(f"Table '{table_name}' not found in session '{session_id}'. Available tables: {list(state['tables'].keys())}")
    return state["tables"][table_name].copy()


def commit_dataframe(df: pd.DataFrame, session_id: str, change_summary: str, table_name: str = "current") -> Dict:
    """Save DataFrame, append to history, return preview/summary."""
    if df.empty:
        raise ValueError("Cannot commit empty DataFrame")
    
    state = _get_session_state(session_id)
    
    # Store previous state for history
    rows_before = len(state["tables"].get(table_name, pd.DataFrame()))
    columns_before = len(state["tables"].get(table_name, pd.DataFrame()).columns) if table_name in state["tables"] else 0
    
    # Initialize history for this table if needed
    if table_name not in state["history"]:
        state["history"][table_name] = []
        state["history_index"][table_name] = -1
        state["undo_stack"][table_name] = []
    
    # Truncate history if we're not at the end (user did undo, then new operation)
    if state["history_index"][table_name] < len(state["history"][table_name]) - 1:
        state["history"][table_name] = state["history"][table_name][:state["history_index"][table_name] + 1]
        # Clear undo stack when new operation is committed after undo
        state["undo_stack"][table_name] = []
    
    # Save new DataFrame
    state["tables"][table_name] = df.copy()
    
    # Add new state to history
    state["history"][table_name].append(df.copy())
    state["history_index"][table_name] = len(state["history"][table_name]) - 1
    
    rows_after = len(df)
    columns_after = len(df.columns)
    
    return {
        "success": True,
        "change_summary": change_summary,
        "rows_before": rows_before,
        "rows_after": rows_after,
        "columns_before": columns_before,
        "columns_after": columns_after,
        "preview_head": df.head(5).to_dict("records")
    }


def get_data_summary(session_id: str, table_name: str = "current") -> Dict:
    """Return rows, columns, dtypes, missing counts, etc."""
    try:
        df = load_current_dataframe(session_id, table_name)
        
        missing_counts = df.isnull().sum().to_dict()
        dtypes = {col: str(dtype) for col, dtype in df.dtypes.items()}
        
        return {
            "success": True,
            "rows": len(df),
            "columns": len(df.columns),
            "column_names": list(df.columns),
            "dtypes": dtypes,
            "missing_counts": missing_counts,
            "memory_usage_mb": df.memory_usage(deep=True).sum() / (1024 * 1024)
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


def undo_last_operation(session_id: str, table_name: str = "current") -> Dict:
    """Revert to previous state in history."""
    state = _get_session_state(session_id)
    
    if table_name not in state["history"] or len(state["history"][table_name]) < 2:
        return {
            "success": False,
            "error": "No operation to undo"
        }
    
    if state["history_index"][table_name] <= 0:
        return {
            "success": False,
            "error": "Already at the first operation"
        }
    
    # Save current state to undo stack
    if table_name in state["tables"]:
        state["undo_stack"][table_name].append(state["tables"][table_name].copy())
    
    # Move back in history
    state["history_index"][table_name] -= 1
    previous_df = state["history"][table_name][state["history_index"][table_name]].copy()
    state["tables"][table_name] = previous_df
    
    return {
        "success": True,
        "change_summary": "Undone last operation",
        "rows_after": len(previous_df),
        "columns_after": len(previous_df.columns),
        "preview_head": previous_df.head(5).to_dict("records")
    }


def redo_operation(session_id: str, table_name: str = "current") -> Dict:
    """Re-apply undone operation."""
    state = _get_session_state(session_id)
    
    if table_name not in state["history"]:
        return {
            "success": False,
            "error": "No history available"
        }
    
    # Check if there's a future state in history
    if state["history_index"][table_name] < len(state["history"][table_name]) - 1:
        state["history_index"][table_name] += 1
        next_df = state["history"][table_name][state["history_index"][table_name]].copy()
        state["tables"][table_name] = next_df
        
        return {
            "success": True,
            "change_summary": "Redone operation",
            "rows_after": len(next_df),
            "columns_after": len(next_df.columns),
            "preview_head": next_df.head(5).to_dict("records")
        }
    
    # Check undo stack
    if table_name in state["undo_stack"] and len(state["undo_stack"][table_name]) > 0:
        next_df = state["undo_stack"][table_name].pop()
        state["tables"][table_name] = next_df
        # Add back to history
        state["history"][table_name].append(next_df.copy())
        state["history_index"][table_name] = len(state["history"][table_name]) - 1
        
        return {
            "success": True,
            "change_summary": "Redone operation",
            "rows_after": len(next_df),
            "columns_after": len(next_df.columns),
            "preview_head": next_df.head(5).to_dict("records")
        }
    
    return {
        "success": False,
        "error": "No operation to redo"
    }


def list_available_tables(session_id: str) -> List[str]:
    """List all tables in session."""
    state = _get_session_state(session_id)
    return list(state["tables"].keys())


def initialize_table(session_id: str, df: pd.DataFrame, table_name: str = "current") -> None:
    """Initialize a table in session state (used when first loading data)."""
    state = _get_session_state(session_id)
    state["tables"][table_name] = df.copy()
    state["history"][table_name] = [df.copy()]
    state["history_index"][table_name] = 0
    state["undo_stack"][table_name] = []

