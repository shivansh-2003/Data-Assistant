"""Single dashboard chart card (header + bordered container)."""

from __future__ import annotations

from typing import Any, Callable, Dict

import plotly.graph_objects as go
import streamlit as st


def render_chart_card(
    fig: go.Figure,
    chart_idx: int,
    chart_id: int,
    config: Dict[str, Any],
    on_remove: Callable[[], None],
    row: int,
    col_idx: int,
) -> None:
    title = f"Chart {chart_idx + 1}"
    st.markdown(f"<div class='dash-chart-card-header'>{title}</div>", unsafe_allow_html=True)
    st.markdown('<div class="dash-chart-card">', unsafe_allow_html=True)
    st.plotly_chart(fig, width="stretch", theme="streamlit", key=f"dash_chart_{chart_id}_{row}_{col_idx}")
    st.markdown("</div>", unsafe_allow_html=True)

    with st.expander(f"{title} — details", expanded=False):
        st.caption(f"**Mode:** {config.get('mode', 'basic')}")
        st.caption(f"**X:** {config.get('x_col', 'N/A')}")
        st.caption(f"**Y:** {config.get('y_col', 'N/A')}")
        remove_key = f"remove_chart_{chart_id}_{row}_{col_idx}_{chart_idx}"
        if st.button(f"Remove {title}", key=remove_key):
            on_remove()
