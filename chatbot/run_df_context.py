"""Per-run DataFrame context for the chatbot graph.

`df_dict` must not be written into LangGraph checkpoint state: the default
serde uses msgpack, which cannot serialize ``pandas.DataFrame``. The UI loads
tables once per turn and stashes them here for ``insight`` / ``viz`` nodes;
checkpoints only keep ``schema``, ``table_names``, etc.

Reset the context in ``finally`` after each ``graph.stream`` / ``invoke`` so
reruns and concurrent tabs do not leak frames across turns.
"""

from __future__ import annotations

import contextvars
from typing import Dict, Optional

import pandas as pd

_run_df_dict: contextvars.ContextVar[Optional[Dict[str, pd.DataFrame]]] = contextvars.ContextVar(
    "chatbot_run_df_dict", default=None
)


def set_run_df_dict(dfs: Optional[Dict[str, pd.DataFrame]]):
    """Return a token for :func:`reset_run_df_dict`."""
    return _run_df_dict.set(dfs)


def reset_run_df_dict(token) -> None:
    """Restore the previous value (usually ``None``)."""
    _run_df_dict.reset(token)


def get_run_df_dict() -> Optional[Dict[str, pd.DataFrame]]:
    """DataFrames for the current graph run, or ``None`` if not set."""
    return _run_df_dict.get()
