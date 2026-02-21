"""
Dashboard UI: Pin to Dashboard button, raw data preview, and dashboard view section.
"""

import pandas as pd
import streamlit as st
from typing import Dict, Any, Optional, List

from ..dashboard_builder import DashboardBuilder
from components.data_table import render_advanced_table

_default_dashboard_builder = DashboardBuilder()


def get_default_dashboard_builder() -> DashboardBuilder:
    """Return the shared DashboardBuilder instance."""
    return _default_dashboard_builder


def render_pin_section(
    builder: DashboardBuilder,
    chart_mode: str,
    chart_type: str,
    x_col: str,
    y_col: str,
    agg_func: str,
    color_col: str,
    composition_params: Dict[str, Any],
    heatmap_columns: Optional[List[str]],
) -> None:
    """Render Pin to Dashboard button and pinned count caption."""
    col_pin1, col_pin2 = st.columns([1, 4])
    with col_pin1:
        if st.button(
            "📌 Pin to Dashboard",
            key="pin_chart_button",
            type="secondary",
            help="Save this chart to your dashboard"
        ):
            chart_config = builder.get_chart_config(
                chart_mode,
                chart_type,
                x_col,
                y_col,
                agg_func,
                color_col,
                composition_params,
                heatmap_columns if chart_type == 'heatmap' else None
            )
            if builder.pin_chart(chart_config):
                st.success("✅ Chart pinned to dashboard!")
                st.info("💡 Enable Dashboard Mode to view your pinned charts.")
            else:
                st.error("❌ Failed to pin chart.")
    with col_pin2:
        pinned_count = len(st.session_state.get('dashboard_charts', []))
        if pinned_count > 0:
            st.caption(f"📊 {pinned_count} chart(s) pinned")


def render_raw_data_preview(df: pd.DataFrame, selected_table: str) -> None:
    """Render checkbox and optional raw data table."""
    if st.checkbox("Show Raw Data Preview", key="viz_table"):
        render_advanced_table(
            df,
            key_prefix=f"viz_raw_{selected_table}",
            height=320,
            page_size_default=25
        )


def render_dashboard_section(df: pd.DataFrame, selected_table: str) -> bool:
    """Render divider and dashboard builder tab. Returns dashboard active status."""
    st.divider()
    return _default_dashboard_builder.render_tab(df, selected_table)
