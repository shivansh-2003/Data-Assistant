"""
Main chart area: Plotly with on_select cross-filter.
"""

from __future__ import annotations

from typing import Optional

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ..core.chart_config import ChartConfig
from ..core.chart_generator import generate_from_config
from ..interactivity.cross_filter import set_cross_filter
from ..interactivity.selection_handler import selection_to_filter_values
from ..theme.layout import card_close, card_open


def render_chart_skeleton() -> None:
    st.markdown(
        """
<div class="viz-chart-container">
<div class="viz-skeleton-bars">
<div class="skeleton" style="height:60%;"></div>
<div class="skeleton" style="height:80%;"></div>
<div class="skeleton" style="height:45%;"></div>
<div class="skeleton" style="height:90%;"></div>
<div class="skeleton" style="height:55%;"></div>
</div>
</div>
        """,
        unsafe_allow_html=True,
    )


def render_main_chart(
    df: pd.DataFrame,
    config: ChartConfig,
    can_render: bool,
    validation_message: Optional[str],
    chart_key: str = "main_viz_chart",
) -> Optional[go.Figure]:
    """Render chart card; returns figure for export/pin."""
    if validation_message:
        st.warning(validation_message)

    st.markdown(card_open(), unsafe_allow_html=True)
    fig: Optional[go.Figure] = None

    if not can_render:
        if not validation_message:
            st.info("👆 Select columns to build a chart.")
        st.markdown(card_close(), unsafe_allow_html=True)
        return None

    with st.spinner("Generating chart…"):
        fig = generate_from_config(df, config)

    try:
        event = st.plotly_chart(
            fig,
            width="stretch",
            theme="streamlit",
            key=chart_key,
            on_select="rerun",
            selection_mode="points",
        )
    except TypeError:
        event = st.plotly_chart(
            fig,
            width="stretch",
            theme="streamlit",
            key=chart_key,
        )

    sel = getattr(event, "selection", None)
    if sel is None and isinstance(event, dict):
        sel = event.get("selection")
    if sel:
        col, vals = selection_to_filter_values(sel, config.x_col)
        if col and vals:
            set_cross_filter(col, vals, chart_key)

    st.markdown(card_close(), unsafe_allow_html=True)
    return fig
