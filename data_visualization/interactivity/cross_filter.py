"""Linked-chart cross-filter state (session_state)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st

from ..config import SESSION_CROSS_FILTER


def get_cross_filter_state() -> Optional[Dict[str, Any]]:
    return st.session_state.get(SESSION_CROSS_FILTER)


def set_cross_filter(column: str, values: List[Any], source_chart: str) -> None:
    st.session_state[SESSION_CROSS_FILTER] = {
        "column": column,
        "values": values,
        "source_chart": source_chart,
    }


def clear_cross_filter() -> None:
    if SESSION_CROSS_FILTER in st.session_state:
        del st.session_state[SESSION_CROSS_FILTER]


def apply_cross_filter(df: pd.DataFrame) -> pd.DataFrame:
    """Return df filtered by active cross-filter, or unchanged if none."""
    state = get_cross_filter_state()
    if not state:
        return df
    col = state.get("column")
    vals = state.get("values") or []
    if not col or col not in df.columns or not vals:
        return df
    try:
        return df[df[col].isin(vals)].copy()
    except Exception:
        return df
