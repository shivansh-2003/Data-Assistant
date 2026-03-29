"""
Progressive-disclosure chart controls: tier-1 pills + column form + More Options.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

import pandas as pd
import streamlit as st

from ..core.chart_config import ChartConfig
from ..theme.palettes import PALETTE_OPTIONS

CHART_ICONS = {
    "bar": "📊 Bar",
    "line": "📈 Line",
    "scatter": "🔵 Scatter",
    "area": "🌊 Area",
    "box": "📦 Box",
    "histogram": "📊 Hist",
    "pie": "🥧 Pie",
    "heatmap": "🔥 Heat",
    "violin": "🎻 Violin",
    "sunburst": "☀️ Sun",
    "treemap": "🌳 Tree",
    "funnel": "🔻 Funnel",
    "sankey": "🔗 Sankey",
    "choropleth": "🗺️ Choropleth",
    "scatter_geo": "📍 Geo",
    "animated": "🎬 Anim",
}

ALL_BASIC_TYPES = list(CHART_ICONS.keys())


def _column_label(df: pd.DataFrame, col_name: str) -> str:
    if col_name == "None":
        return "— None"
    if col_name not in df.columns:
        return col_name
    if pd.api.types.is_numeric_dtype(df[col_name]):
        return f"🔢 {col_name}"
    if pd.api.types.is_datetime64_any_dtype(df[col_name]):
        return f"📅 {col_name}"
    return f"🔤 {col_name}"


def render_chart_controls(df: pd.DataFrame) -> Tuple[ChartConfig, str, Dict[str, Any], bool, Optional[str]]:
    """
    Returns:
        config: ChartConfig
        chart_mode: 'basic' | 'combo'
        composition_params: dict for combo mode
        can_render: whether chart can be drawn
        validation_message: optional warning
    """
    cols = ["None"] + [c for c in df.columns.tolist()]

    if "viz_chart_mode" not in st.session_state:
        st.session_state["viz_chart_mode"] = "basic"

    chart_mode = st.radio(
        "Chart Mode",
        options=["basic", "combo"],
        format_func=lambda x: {"basic": "📊 Basic Chart", "combo": "🔀 Combo (Dual Y)"}[x],
        key="viz_chart_mode",
        horizontal=True,
    )
    st.caption("Basic: single chart. Combo: two metrics on shared X.")

    # --- Chart type (icon labels via format_func; keeps key viz_chart_type for recommendations) ---
    if chart_mode == "basic":
        if "viz_chart_type" not in st.session_state:
            st.session_state["viz_chart_type"] = "bar"
        if st.session_state.get("viz_chart_type") not in ALL_BASIC_TYPES:
            st.session_state["viz_chart_type"] = "bar"
        chart_type = st.selectbox(
            "Chart type",
            options=ALL_BASIC_TYPES,
            format_func=lambda ct: CHART_ICONS.get(ct, ct),
            key="viz_chart_type",
            help="Choose visualization. Advanced columns appear in More Options.",
        )
    else:
        chart_type = st.session_state.get("viz_chart_type", "bar")

    # --- Column form (batch apply) ---
    with st.form("viz_column_form", border=False):
        fc1, fc2, fc3 = st.columns(3)
        with fc1:
            x_col = st.selectbox(
                "X Axis",
                options=cols,
                format_func=lambda c: _column_label(df, c),
                key="viz_x_col",
            )
        with fc2:
            y_col = st.selectbox(
                "Y Axis",
                options=cols,
                format_func=lambda c: _column_label(df, c),
                key="viz_y_col",
            )
        with fc3:
            color_col = st.selectbox(
                "Color / Group",
                options=cols,
                format_func=lambda c: _column_label(df, c),
                key="viz_color_col",
            )
        st.form_submit_button("Apply column selection", use_container_width=True)

    # Defaults after form
    x_col = st.session_state.get("viz_x_col", "None")
    y_col = st.session_state.get("viz_y_col", "None")
    color_col = st.session_state.get("viz_color_col", "None")

    # --- More Options ---
    heatmap_columns = None
    path_cols = None
    sankey_source = sankey_target = sankey_value = None
    geo_col = lat_col = lon_col = None
    geo_scope = "world"
    animation_col = None
    show_trendline = False

    with st.expander("⚙️ More Options", expanded=False):
        mo1, mo2 = st.columns(2)
        with mo1:
            if y_col != "None" and y_col in df.columns and pd.api.types.is_numeric_dtype(df[y_col]):
                agg_func = st.selectbox(
                    "Aggregate Y by X",
                    options=["none", "sum", "mean", "count", "min", "max"],
                    index=0,
                    key="viz_agg",
                )
            else:
                agg_func = "none"
                st.caption("Aggregation needs numeric Y.")
        with mo2:
            palette_choice = st.selectbox(
                "Color palette",
                options=list(PALETTE_OPTIONS.keys()),
                key="viz_palette",
            )
        chart_title = st.text_input("Chart title (optional)", key="viz_title", placeholder="e.g. Revenue by region")
        if chart_mode == "basic" and chart_type == "scatter":
            show_trendline = st.checkbox("Show OLS trendline", key="viz_show_trend")

        if chart_mode == "basic":
            if chart_type == "heatmap":
                heatmap_columns = st.multiselect(
                    "Heatmap columns (2+)",
                    options=[c for c in df.columns],
                    key="viz_heatmap_cols",
                )
            if chart_type in ("sunburst", "treemap"):
                path_cols = st.multiselect(
                    "Path columns (hierarchy order)",
                    options=[c for c in df.columns],
                    key="viz_path_cols",
                )
            if chart_type == "sankey":
                c1, c2, c3 = st.columns(3)
                with c1:
                    sankey_source = st.selectbox("Source", options=[c for c in df.columns], key="viz_sankey_src")
                with c2:
                    sankey_target = st.selectbox("Target", options=[c for c in df.columns], key="viz_sankey_tgt")
                with c3:
                    sankey_value = st.selectbox(
                        "Value (optional)",
                        options=["None"] + [c for c in df.columns],
                        key="viz_sankey_val",
                    )
                    if sankey_value == "None":
                        sankey_value = None
            if chart_type == "choropleth":
                geo_col = st.selectbox("Locations column", options=[c for c in df.columns], key="viz_geo_col")
                geo_scope = st.selectbox(
                    "Scope",
                    options=["world", "usa", "europe", "asia", "africa", "north america", "south america"],
                    key="viz_geo_scope",
                )
            if chart_type == "scatter_geo":
                lat_col = st.selectbox("Latitude", options=[c for c in df.columns], key="viz_lat")
                lon_col = st.selectbox("Longitude", options=[c for c in df.columns], key="viz_lon")
            if chart_type == "animated":
                animation_col = st.selectbox(
                    "Animation frame column",
                    options=[c for c in df.columns],
                    key="viz_anim_col",
                )

    color_palette = PALETTE_OPTIONS.get(st.session_state.get("viz_palette", "Default"))
    chart_title_val = st.session_state.get("viz_title") or None

    composition_params: Dict[str, Any] = {}
    if chart_mode == "combo":
        if "viz_composition_params" not in st.session_state:
            st.session_state["viz_composition_params"] = {}
        st.subheader("Combo settings")
        c1, c2, c3 = st.columns(3)
        with c1:
            y2_col = st.selectbox("Second Y", options=cols, key="viz_y2_col")
        with c2:
            chart1_type = st.selectbox("Trace 1 type", options=["bar", "line", "scatter", "area"], key="viz_combo_chart1")
        with c3:
            chart2_type = st.selectbox("Trace 2 type", options=["bar", "line", "scatter", "area"], key="viz_combo_chart2")
        composition_params = {
            "y2_col": y2_col,
            "chart1_type": chart1_type,
            "chart2_type": chart2_type,
        }

    # Build ChartConfig
    cfg = ChartConfig(
        chart_mode=chart_mode,
        chart_type=chart_type if chart_mode == "basic" else "bar",
        x_col=x_col if x_col != "None" else None,
        y_col=y_col if y_col != "None" else None,
        color_col=color_col if color_col != "None" else None,
        agg_func=st.session_state.get("viz_agg", "none"),
        heatmap_columns=heatmap_columns,
        color_palette=color_palette,
        title_override=chart_title_val,
        path_cols=path_cols,
        sankey_source=sankey_source,
        sankey_target=sankey_target,
        sankey_value=sankey_value,
        geo_col=geo_col,
        geo_scope=geo_scope or "world",
        lat_col=lat_col,
        lon_col=lon_col,
        animation_col=animation_col,
        show_trendline=show_trendline,
    )

    if chart_mode == "combo":
        cfg.chart_mode = "combo"
        cfg.y2_col = composition_params.get("y2_col") if composition_params.get("y2_col") != "None" else None
        cfg.chart1_type = composition_params.get("chart1_type", "bar")
        cfg.chart2_type = composition_params.get("chart2_type", "line")

    if chart_mode == "basic" and chart_type == "choropleth" and cfg.geo_col is None and x_col != "None":
        cfg.geo_col = x_col

    # Validation
    can_render = False
    validation_message = None
    if chart_mode == "combo":
        y2 = composition_params.get("y2_col")
        if x_col != "None" and y_col != "None" and y2 and y2 != "None":
            can_render = True
        else:
            validation_message = "⚠️ Combo chart requires X, Y1, and Y2 columns."
    elif chart_type in ("line", "scatter", "area", "animated"):
        if x_col != "None" and y_col != "None":
            can_render = True
        else:
            validation_message = "⚠️ This chart type needs both X and Y."
    elif chart_type == "box":
        can_render = y_col != "None"
        if not can_render:
            validation_message = "⚠️ Box plot requires Y."
    elif chart_type == "histogram":
        can_render = x_col != "None"
        if not can_render:
            validation_message = "⚠️ Histogram requires X."
    elif chart_type == "pie":
        can_render = x_col != "None" or y_col != "None"
        if not can_render:
            validation_message = "⚠️ Pie needs X or Y."
    elif chart_type == "heatmap":
        if heatmap_columns and len(heatmap_columns) >= 2:
            can_render = True
        elif x_col != "None" and y_col != "None":
            can_render = True
        else:
            validation_message = "⚠️ Heatmap: pick 2+ columns or X and Y."
    elif chart_type in ("sunburst", "treemap"):
        can_render = bool(path_cols and len(path_cols) >= (2 if chart_type == "sunburst" else 1))
        if not can_render:
            validation_message = "⚠️ Set path columns in More Options."
    elif chart_type == "funnel":
        can_render = x_col != "None"
        if not can_render:
            validation_message = "⚠️ Funnel requires X (stage)."
    elif chart_type == "sankey":
        can_render = bool(sankey_source and sankey_target)
        if not can_render:
            validation_message = "⚠️ Sankey needs Source and Target in More Options."
    elif chart_type == "choropleth":
        can_render = bool((geo_col or x_col != "None") and y_col != "None")
        if not can_render:
            validation_message = "⚠️ Choropleth needs location + values (Y)."
    elif chart_type == "scatter_geo":
        can_render = bool(lat_col and lon_col)
        if not can_render:
            validation_message = "⚠️ Scatter geo needs lat/lon in More Options."
    elif chart_type == "violin":
        can_render = y_col != "None"
        if not can_render:
            validation_message = "⚠️ Violin requires Y."
    else:
        # bar default
        can_render = x_col != "None" or y_col != "None"
        if not can_render:
            validation_message = "⚠️ Select at least X or Y."

    return cfg, chart_mode, composition_params, can_render, validation_message
