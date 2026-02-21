"""
Visualization Centre module for Data Assistant Platform.
Thin orchestrator: loads session data, delegates to ui/* and core/*.

Optimized for <1s chart render latency:
  - Tables list fetched via get_tables_from_session() (hot-cached, no extra HTTP call)
  - DataFrame fetched via get_dataframe_from_session() (hot-cached)
  - Plotly figure memoized in session_state keyed to chart config hash
  - Spinner only shown on actual cache miss (first render or after invalidation)
"""

import hashlib
import json
import streamlit as st
import pandas as pd

from .core.data_fetcher import (
    get_tables_from_session,
    get_dataframe_from_session,
    get_cache_version,
)
from .core.chart_generator import generate_chart
from .core.validators import get_validation_result
from .charts.combo import generate_combo_chart
from .ui.recommendations import render_recommendations_panel
from .ui.controls import render_controls
from .ui.export import render_export_section
from .ui.dashboard import (
    get_default_dashboard_builder,
    render_pin_section,
    render_raw_data_preview,
    render_dashboard_section,
)
from components.empty_state import render_empty_state

# Session-state key for memoized figures
_FIG_CACHE_KEY = "viz_fig_cache"


def _chart_config_hash(
    session_id: str,
    table_name: str,
    chart_mode: str,
    chart_type: str,
    x_col: str,
    y_col: str,
    agg_func: str,
    color_col: str,
    heatmap_columns,
    chart_title: str,
    color_palette,
    composition_params: dict,
    cache_version: int,
) -> str:
    """
    Stable MD5 hash of all chart inputs. When this matches the stored hash,
    the cached figure is served instantly without re-running Plotly.
    """
    payload = {
        "sid": session_id,
        "tbl": table_name,
        "mode": chart_mode,
        "type": chart_type,
        "x": x_col,
        "y": y_col,
        "agg": agg_func,
        "color": color_col,
        "heatmap": sorted(heatmap_columns) if heatmap_columns else [],
        "title": chart_title or "",
        "palette": str(color_palette),
        "comp": composition_params,
        "ver": cache_version,
    }
    return hashlib.md5(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def render_visualization_tab():
    """Render the Visualization Centre tab content."""
    builder = get_default_dashboard_builder()
    builder._initialize_state()

    st.markdown(
        '<div class="hero-section" role="region" aria-label="Visualization Centre">'
        '<h1 class="main-header">📈 Visualization Centre</h1>'
        '<p class="section-subtitle">Select columns below to build charts instantly. '
        'Charts update in <b>&lt;1 second</b> using cached session data.</p>'
        '</div>',
        unsafe_allow_html=True,
    )

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

    # ── Step 1: Load tables list (hot-cached, ~0ms on hit) ─────────────────────
    tables = get_tables_from_session(session_id)
    if not tables:
        st.warning("⚠️ No tables found in session. Please upload a file first.")
        return

    table_names = list(tables.keys())
    selected_table = (
        st.selectbox("Select Table to Visualize", table_names, key="viz_table_select")
        if len(table_names) > 1
        else table_names[0]
    )

    # ── Step 2: Load DataFrame (hot-cached, ~0ms on hit) ──────────────────────
    df = get_dataframe_from_session(session_id, selected_table)

    if df is None or df.empty:
        st.warning("⚠️ No data available for visualization. The table may be empty.")
        return

    # ── Step 3: Data summary metrics (instant) ────────────────────────────────
    st.markdown('<div class="card-elevated" role="region" aria-label="Data summary">', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Rows", f"{len(df):,}")
    with c2:
        st.metric("Columns", len(df.columns))
    with c3:
        st.metric("Table", selected_table)
    st.markdown('</div>', unsafe_allow_html=True)
    st.divider()

    # ── Step 4: Controls + chart in two columns ────────────────────────────────
    viz_left_col, viz_right_col = st.columns([2, 3])

    with viz_left_col:
        render_recommendations_panel(df)
        controls = render_controls(df)

    chart_type = controls["chart_type"]
    x_col = controls["x_col"]
    y_col = controls["y_col"]
    color_col = controls["color_col"]
    agg_func = controls["agg_func"]
    heatmap_columns = controls["heatmap_columns"]
    chart_title = controls["chart_title"]
    color_palette = controls["color_palette"]
    chart_mode = controls["chart_mode"]
    composition_params = controls["composition_params"]

    can_render, validation_message = get_validation_result(
        chart_mode, chart_type, x_col, y_col, heatmap_columns, composition_params
    )

    # ── Step 5: Chart rendering with figure memoization ───────────────────────
    with viz_right_col:
        if validation_message:
            st.warning(validation_message)

        st.markdown('<div class="card-elevated" role="region">', unsafe_allow_html=True)

        if can_render:
            cfg_hash = _chart_config_hash(
                session_id, selected_table, chart_mode, chart_type,
                x_col, y_col, agg_func, color_col, heatmap_columns,
                chart_title, color_palette, composition_params,
                get_cache_version(),
            )

            fig_cache = st.session_state.get(_FIG_CACHE_KEY, {})
            cached_fig = fig_cache.get(cfg_hash)

            if cached_fig is not None:
                # Cache hit: render instantly, no spinner
                st.plotly_chart(cached_fig, width="stretch", theme="streamlit")
            else:
                # Cache miss: generate chart (only on first render or after data change)
                with st.spinner("Generating chart…"):
                    if chart_mode == "basic":
                        fig = generate_chart(
                            df,
                            chart_type,
                            x_col if x_col != "None" else None,
                            y_col if y_col != "None" else None,
                            agg_func,
                            color_col if color_col != "None" else None,
                            heatmap_columns if chart_type == "heatmap" else None,
                            chart_title or None,
                            color_palette,
                        )
                    else:
                        fig = generate_combo_chart(
                            df,
                            x_col if x_col != "None" else None,
                            y_col if y_col != "None" else None,
                            composition_params.get("y2_col") if composition_params.get("y2_col") != "None" else None,
                            composition_params.get("chart1_type", "bar"),
                            composition_params.get("chart2_type", "line"),
                            color_col if color_col != "None" else None,
                        )

                # Store in figure cache (keep max 10 entries to cap memory)
                fig_cache[cfg_hash] = fig
                if len(fig_cache) > 10:
                    oldest = next(iter(fig_cache))
                    del fig_cache[oldest]
                st.session_state[_FIG_CACHE_KEY] = fig_cache

                st.plotly_chart(fig, width="stretch", theme="streamlit")

            render_pin_section(
                builder, chart_mode, chart_type, x_col, y_col, agg_func,
                color_col, composition_params,
                heatmap_columns if chart_type == "heatmap" else None,
            )
            render_raw_data_preview(df, selected_table)
            render_export_section(
                fig_cache.get(cfg_hash), chart_mode, chart_type,
                selected_table, x_col, y_col, color_col,
                cfg_hash=cfg_hash,
            )

        elif not validation_message:
            st.info("👆 Select at least one column to get started.")
            numeric_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
            categorical_cols = [c for c in df.columns if not pd.api.types.is_numeric_dtype(df[c])]
            if numeric_cols or categorical_cols:
                with st.expander("💡 Quick Start Suggestions", expanded=False):
                    if categorical_cols:
                        st.write(f"**For X-Axis (Category):** Try `{categorical_cols[0]}`")
                    if numeric_cols:
                        st.write(f"**For Y-Axis (Value):** Try `{numeric_cols[0]}`")
                    if categorical_cols and numeric_cols:
                        st.write(f"**Example:** X=`{categorical_cols[0]}`, Y=`{numeric_cols[0]}`, Chart=`Bar`")

        st.markdown("</div>", unsafe_allow_html=True)

    render_dashboard_section(df, selected_table)
