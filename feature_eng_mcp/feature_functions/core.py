"""
Session helpers: reuse data_mcp in-process state + HTTP sync, plus fit artifact storage.
"""

from __future__ import annotations

import logging
import pickle
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Callable

import pandas as pd

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

try:
    from data_mcp.data_functions.core import (
        initialize_table,
        get_data_summary,
        list_available_tables,
        undo_last_operation,
        redo_operation as redo_operation_fe,
        commit_dataframe,
        get_table_data,
        _record_operation,
    )
except ImportError as e:
    logger.warning("Could not import data_mcp.data_functions.core: %s", e)
    raise ImportError(
        "feature_eng_mcp requires repo root on PYTHONPATH (run uvicorn from Data-Assistant root)"
    ) from e

# fit_id -> arbitrary pickled sklearn/pipeline state (per session)
fit_artifacts: Dict[str, Dict[str, bytes]] = {}
# pipeline_id -> serialized pipeline spec + fitted objects
saved_pipelines: Dict[str, Dict[str, Any]] = {}


def store_fit_object(session_id: str, fit_id: str, obj: Any) -> None:
    if session_id not in fit_artifacts:
        fit_artifacts[session_id] = {}
    fit_artifacts[session_id][fit_id] = pickle.dumps(obj)


def get_fit_object(session_id: str, fit_id: str) -> Any:
    blob = fit_artifacts.get(session_id, {}).get(fit_id)
    if blob is None:
        return None
    return pickle.loads(blob)


def save_pipeline_spec(pipeline_id: str, steps: list, session_id: str) -> None:
    saved_pipelines[pipeline_id] = {"steps": steps, "session_id": session_id}


def get_pipeline_spec(pipeline_id: str) -> Optional[Dict[str, Any]]:
    return saved_pipelines.get(pipeline_id)


def run_fe_tool(
    session_id: str,
    table_name: str,
    op_type: str,
    fn: Callable[[pd.DataFrame], tuple[pd.DataFrame, Dict[str, Any]]],
) -> Dict[str, Any]:
    """
    Load DF, apply fn(df) -> (new_df, result_meta), commit, record operation.
    """
    df = get_table_data(session_id, table_name)
    if df is None:
        return {
            "success": False,
            "error": f"Table '{table_name}' not found in session {session_id}",
            "session_id": session_id,
        }
    try:
        new_df, meta = fn(df.copy())
        commit_dataframe(session_id, table_name, new_df)
        _record_operation(session_id, table_name, {"type": op_type, **meta})
        out = {"success": True, "session_id": session_id, "table_name": table_name}
        out.update(meta)
        return out
    except Exception as e:
        logger.exception("run_fe_tool failed")
        return {
            "success": False,
            "error": str(e),
            "session_id": session_id,
            "table_name": table_name,
        }


def preview_tail(df: pd.DataFrame, n: int = 5) -> list:
    try:
        return df.tail(n).replace({pd.NA: None}).to_dict(orient="records")
    except Exception:
        return []
