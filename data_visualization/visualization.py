"""
Visualization Centre — thin orchestrator: theme, data, controls, chart, export, dashboard.
"""

from __future__ import annotations

import os
from typing import Optional

import pandas as pd
import requests
import streamlit as st

from components.empty_state import render_empty_state

from .core.data_fetcher import get_dataframe_from_session
from .dashboard_builder import DashboardBuilder
from .smart_recommendations import get_chart_recommendations
from .theme.css import inject_viz_css
from .ui.chart_display import render_main_chart
from .ui.controls import render_chart_controls
from .ui.data_preview import render_data_preview
from .ui.export_panel import render_export_panel
from .ui.filter_bar import render_filter_bar
from .ui.metric_cards import render_data_summary_metrics
from .ui.toolbar import render_action_bar

# Public API for other modules & tests
from .core.chart_generator import generate_chart, generate_from_config  # noqa: F401

FASTAPI_URL = os.getenv("FASTAPI_URL", "https://data-assistant-hj5f.onrender.com")
SESSION_ENDPOINT = f"{FASTAPI_URL}/api/session"

_default_dashboard_builder = DashboardBuilder()


def render_visualization_tab() -> None:
    inject_viz_css()
    _default_dashboard_builder._initialize_state()

    st.header("📈 Visualization Centre")
    st.markdown("**Build charts from your session data. Use **More Options** for aggregation, palettes, and advanced chart types.**")
    st.caption("Charts respect cross-filters when you select points on the main chart.")

    session_id = st.session_state.get("current_session_id")
    if not session_id:
        render_empty_state(
            title="No data loaded yet",
            message="Upload a file in the Upload tab first. Then create charts and dashboards here.",
            primary_action_label="Go to Upload",
            primary_action_key="empty_viz_upload",
            secondary_action_label="How it works",
            secondary_action_key="empty_viz_help",
            icon="📈",
        )
        return

    try:
        response = requests.get(
            f"{SESSION_ENDPOINT}/{session_id}/tables",
            params={"format": "summary"},
            timeout=10,
        )
        response.raise_for_status()
        tables_data = response.json()
        tables = tables_data.get("tables", {})
        if not tables:
            st.warning("⚠️ No tables found in session. Please upload a file first.")
            return
        table_names = list(tables.keys())
        if len(table_names) > 1:
            selected_table = st.selectbox("Select table to visualize", table_names, key="viz_table_select")
        else:
            selected_table = table_names[0]
        df = get_dataframe_from_session(session_id, selected_table)
    except Exception as e:
        st.error(f"❌ Error loading session data: {e}")
        return

    if df is None or df.empty:
        st.warning("⚠️ No data available for visualization.")
        return

    render_data_summary_metrics(df, selected_table)

    # --- Smart recommendations (card) ---
    st.markdown('<div class="card-elevated" role="region">', unsafe_allow_html=True)
    if "viz_recommendations" not in st.session_state:
        st.session_state["viz_recommendations"] = None
    if "viz_user_goal_text" not in st.session_state:
        st.session_state["viz_user_goal_text"] = ""

    expander_expanded = st.session_state.get("viz_recommendations") is not None
    with st.expander("🤖 Smart chart recommendations", expanded=expander_expanded):
        st.caption("Describe your goal for tailored suggestions.")
        c1, c2 = st.columns([3, 1])
        with c1:
            user_goal = st.text_input(
                "Goal (optional)",
                placeholder="e.g. Show sales trends over time",
                key="viz_user_goal",
                value=st.session_state.get("viz_user_goal_text", ""),
            )
        with c2:
            recommend_button = st.button("✨ Get recommendations", type="primary", use_container_width=True)

        if recommend_button:
            st.session_state["viz_user_goal_text"] = user_goal
            with st.spinner("Analyzing…"):
                try:
                    recs = get_chart_recommendations(df, user_goal or None)
                    st.session_state["viz_recommendations"] = recs
                except Exception:
                    st.session_state["viz_recommendations"] = None
                    recs = []
            if recs:
                st.success(f"Found {len(recs)} suggestions.")
                for idx, rec in enumerate(recs, 1):
                    st.markdown(f"**#{idx}** `{rec.get('chart_type', '')}` — {rec.get('reasoning', '')}")
                    if st.button("Apply", key=f"apply_rec_{idx}_{rec.get('chart_type')}"):
                        st.session_state["viz_chart_type"] = rec.get("chart_type", "bar")
                        if rec.get("x_column") in df.columns:
                            st.session_state["viz_x_col"] = rec["x_column"]
                        else:
                            st.session_state["viz_x_col"] = "None"
                        if rec.get("y_column") in df.columns:
                            st.session_state["viz_y_col"] = rec["y_column"]
                        else:
                            st.session_state["viz_y_col"] = "None"
                        st.rerun()
            else:
                st.warning("Could not generate recommendations. Try manual selection.")

        stored = st.session_state.get("viz_recommendations")
        if stored and not recommend_button:
            st.caption("Saved suggestions:")
            for idx, rec in enumerate(stored, 1):
                if st.button("Apply", key=f"apply_rec_persist_{idx}_{rec.get('chart_type')}"):
                    st.session_state["viz_chart_type"] = rec.get("chart_type", "bar")
                    st.session_state["viz_x_col"] = rec.get("x_column") if rec.get("x_column") in df.columns else "None"
                    st.session_state["viz_y_col"] = rec.get("y_column") if rec.get("y_column") in df.columns else "None"
                    st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)
    st.divider()

    st.subheader("⚡ Quick templates")
    qt1, qt2, qt3, qt4 = st.columns(4)
    with qt1:
        if st.button("Bar", key="qt_bar"):
            st.session_state["viz_chart_type"] = "bar"
    with qt2:
        if st.button("Line", key="qt_line"):
            st.session_state["viz_chart_type"] = "line"
    with qt3:
        if st.button("Scatter", key="qt_scatter"):
            st.session_state["viz_chart_type"] = "scatter"
    with qt4:
        if st.button("Histogram", key="qt_hist"):
            st.session_state["viz_chart_type"] = "histogram"

    st.divider()

    config, chart_mode, composition_params, can_render, validation_message = render_chart_controls(df)

    render_filter_bar()

    # --- Full-width chart ---
    fig = render_main_chart(
        df,
        config,
        can_render,
        validation_message,
        chart_key="main_viz_chart",
    )

    if fig is not None and can_render:
        c_pin, _ = st.columns([1, 4])
        with c_pin:
            if st.button("📌 Pin to dashboard", key="pin_chart_button", help="Save this chart to the dashboard"):
                chart_cfg = _default_dashboard_builder.get_chart_config(
                    chart_mode,
                    config.chart_type,
                    st.session_state.get("viz_x_col", "None"),
                    st.session_state.get("viz_y_col", "None"),
                    st.session_state.get("viz_agg", "none"),
                    st.session_state.get("viz_color_col", "None"),
                    composition_params,
                    st.session_state.get("viz_heatmap_cols") if config.chart_type == "heatmap" else None,
                )
                if _default_dashboard_builder.pin_chart(chart_cfg):
                    st.success("Chart pinned. Enable Dashboard Mode below.")
        pinned_count = len(st.session_state.get("dashboard_charts", []))
        render_action_bar(pinned_count)

        render_export_panel(
            fig,
            chart_mode,
            config.chart_type if chart_mode == "basic" else "combo",
            selected_table,
            config.x_col,
            config.y_col,
            config.color_col,
        )

        render_data_preview(df, selected_table)

    st.divider()
    _default_dashboard_builder.render_tab(df, selected_table)
