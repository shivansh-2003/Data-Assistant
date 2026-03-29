"""Active cross-filter pill + clear."""

from __future__ import annotations

import streamlit as st

from ..interactivity.cross_filter import clear_cross_filter, get_cross_filter_state


def render_filter_bar() -> None:
    state = get_cross_filter_state()
    if not state:
        return
    col = state.get("column")
    vals = state.get("values") or []
    if not col or not vals:
        return
    label = f"{col}: {', '.join(str(v) for v in vals[:3])}"
    if len(vals) > 3:
        label += f" +{len(vals) - 3} more"
    c1, c2 = st.columns([6, 1])
    with c1:
        st.markdown(f'<span class="filter-pill">🔍 {label}</span>', unsafe_allow_html=True)
    with c2:
        if st.button("Clear filter", key="viz_clear_cross_filter"):
            clear_cross_filter()
            st.rerun()
