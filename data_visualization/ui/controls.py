"""
Chart control widgets: dropdowns, toggles, palette, quick templates, chart mode.
"""

import pandas as pd
import streamlit as st
import plotly.express as px
from typing import Dict, Any, List, Optional


def _column_label(df: pd.DataFrame, col_name: str) -> str:
    if col_name == 'None':
        return "— None"
    if col_name not in df.columns:
        return col_name
    if pd.api.types.is_numeric_dtype(df[col_name]):
        return f"🔢 {col_name}"
    return f"🔤 {col_name}"


def _chart_label(chart_name: str) -> str:
    mapping = {
        'bar': '📊 Bar',
        'line': '📈 Line',
        'scatter': '🔵 Scatter',
        'area': '🌊 Area',
        'box': '📦 Box',
        'histogram': '📊 Histogram',
        'pie': '🥧 Pie',
        'heatmap': '🔥 Heatmap'
    }
    return mapping.get(chart_name, chart_name)


def render_controls(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Render Quick Templates, Chart Mode, Chart Controls expander, and Composition settings.
    Returns a dict with chart_type, x_col, y_col, color_col, agg_func, heatmap_columns,
    chart_title, color_palette, chart_mode, composition_params.
    """
    cols = ['None'] + df.columns.tolist()

    # Quick templates
    st.markdown(
        '<div class="card-elevated" role="region" aria-label="Quick chart templates">',
        unsafe_allow_html=True,
    )
    st.markdown('<h2 class="section-title">⚡ Quick Chart Templates</h2>', unsafe_allow_html=True)
    st.caption("Apply a recommended configuration with one click.")
    qt1, qt2, qt3, qt4 = st.columns(4)
    with qt1:
        if st.button("📊 Bar: Category vs Value", key="qt_bar"):
            st.session_state['viz_chart_type'] = 'bar'
    with qt2:
        if st.button("📈 Line: Trend over Time", key="qt_line"):
            st.session_state['viz_chart_type'] = 'line'
    with qt3:
        if st.button("🔵 Scatter: Relationship", key="qt_scatter"):
            st.session_state['viz_chart_type'] = 'scatter'
    with qt4:
        if st.button("📊 Histogram: Distribution", key="qt_hist"):
            st.session_state['viz_chart_type'] = 'histogram'
    st.markdown('</div>', unsafe_allow_html=True)

    if 'viz_chart_mode' not in st.session_state:
        st.session_state['viz_chart_mode'] = 'basic'
    chart_mode = st.radio(
        "Chart Mode",
        options=['basic', 'combo'],
        format_func=lambda x: {'basic': '📊 Basic Chart', 'combo': '🔀 Combo Chart (Dual Y-Axes)'}[x],
        key="viz_chart_mode",
        horizontal=True
    )
    st.caption("Use Basic for single metrics, Combo for dual-axis comparisons.")
    st.divider()

    # Chart Controls expander
    st.markdown(
        '<div class="card-elevated" role="region" aria-label="Chart controls">',
        unsafe_allow_html=True,
    )
    with st.expander("📊 Chart Controls", expanded=True):
        st.caption("Pick chart type, columns, and optional grouping to build your visualization.")
        col1, col2, col3, col4 = st.columns(4)
        chart_options = ['bar', 'line', 'scatter', 'area', 'box', 'histogram', 'pie', 'heatmap']
        if 'viz_chart_type' not in st.session_state:
            st.session_state['viz_chart_type'] = 'bar'
        if st.session_state.get('viz_chart_type') not in chart_options:
            st.session_state['viz_chart_type'] = 'bar'

        with col1:
            chart_type = st.selectbox(
                "Chart Type",
                options=chart_options,
                format_func=_chart_label,
                help="Bar for categories, Line for trends, Scatter for correlations, etc.",
                key="viz_chart_type"
            )
        with col2:
            if 'viz_x_col' not in st.session_state:
                default_x_idx = 0
                if len(df.columns) > 0:
                    for i, col in enumerate(df.columns):
                        if not pd.api.types.is_numeric_dtype(df[col]):
                            default_x_idx = i + 1
                            break
                    if default_x_idx == 0 and len(df.columns) > 0:
                        default_x_idx = 1
                st.session_state['viz_x_col'] = cols[default_x_idx]
            if st.session_state.get('viz_x_col') not in cols:
                st.session_state['viz_x_col'] = 'None'
            x_col = st.selectbox(
                "X-Axis (or Category)",
                options=cols,
                format_func=lambda c: _column_label(df, c),
                key="viz_x_col"
            )
        with col3:
            if 'viz_y_col' not in st.session_state:
                default_y_idx = 0
                if len(df.columns) > 1:
                    for i, col in enumerate(df.columns):
                        if pd.api.types.is_numeric_dtype(df[col]):
                            default_y_idx = i + 1
                            break
                    if default_y_idx == 0 and len(df.columns) > 1:
                        default_y_idx = 2 if len(df.columns) > 1 else 1
                st.session_state['viz_y_col'] = cols[default_y_idx]
            if st.session_state.get('viz_y_col') not in cols:
                st.session_state['viz_y_col'] = 'None'
            y_col = st.selectbox(
                "Y-Axis (or Value)",
                options=cols,
                format_func=lambda c: _column_label(df, c),
                key="viz_y_col"
            )
        with col4:
            if 'viz_color_col' not in st.session_state:
                st.session_state['viz_color_col'] = 'None'
            if st.session_state.get('viz_color_col') not in cols:
                st.session_state['viz_color_col'] = 'None'
            color_col = st.selectbox(
                "Color/Group By (Optional)",
                options=cols,
                format_func=lambda c: _column_label(df, c),
                key="viz_color_col"
            )

        heatmap_columns: Optional[List[str]] = None  # set below when chart_type == 'heatmap'
        if chart_type == 'heatmap':
            st.markdown("---")
            st.subheader("🔥 Heatmap Column Selection")
            st.markdown("**Select multiple columns for correlation matrix or pivot table**")
            if 'viz_heatmap_cols' not in st.session_state:
                st.session_state['viz_heatmap_cols'] = []
            available_cols = [c for c in df.columns.tolist() if c in df.columns]
            current_selection = [c for c in st.session_state.get('viz_heatmap_cols', []) if c in available_cols]
            selected_heatmap_cols = st.multiselect(
                "Select Columns for Heatmap",
                options=available_cols,
                default=current_selection,
                help="Select 2+ columns. Numeric columns will create correlation matrix.",
                key="viz_heatmap_cols"
            )
            heatmap_columns = selected_heatmap_cols
            if len(selected_heatmap_cols) > 0:
                numeric_count = sum(1 for c in selected_heatmap_cols if pd.api.types.is_numeric_dtype(df[c]))
                categorical_count = len(selected_heatmap_cols) - numeric_count
                if len(selected_heatmap_cols) < 2:
                    st.warning("⚠️ Please select at least 2 columns for heatmap")
                elif numeric_count == len(selected_heatmap_cols):
                    st.info(f"✅ {numeric_count} numeric columns → correlation matrix")
                elif numeric_count >= 1 and categorical_count >= 1:
                    st.info("✅ Pivot table")
                else:
                    st.warning("⚠️ Need at least 1 numeric column for heatmap")
            else:
                st.caption("💡 Select 2+ columns above.")

        col_agg1, col_agg2 = st.columns([1, 3])
        with col_agg1:
            if y_col != 'None' and y_col in df.columns and pd.api.types.is_numeric_dtype(df[y_col]):
                agg_func = st.selectbox(
                    "Aggregate Y By",
                    options=['none', 'sum', 'mean', 'count', 'min', 'max'],
                    index=0,
                    key="viz_agg"
                )
            else:
                agg_func = 'none'
                st.caption("Aggregation\n(requires numeric Y)")
        with col_agg2:
            st.caption("💡 Tip: Select columns above to generate chart instantly")
        st.markdown("---")
        style_col1, style_col2 = st.columns([2, 2])
        with style_col1:
            chart_title = st.text_input(
                "Chart Title (optional)",
                placeholder="e.g., Revenue by Region",
                key="viz_title"
            )
        with style_col2:
            palette_options = {
                "Default": None,
                "Vibrant": px.colors.qualitative.Bold,
                "Pastel": px.colors.qualitative.Pastel,
                "Prism": px.colors.qualitative.Prism,
                "Dark24": px.colors.qualitative.Dark24
            }
            palette_choice = st.selectbox(
                "Color Palette",
                options=list(palette_options.keys()),
                key="viz_palette"
            )
            color_palette = palette_options.get(palette_choice)

    st.markdown('</div>', unsafe_allow_html=True)

    composition_params: Dict[str, Any] = {}
    if chart_mode != 'basic':
        if 'viz_composition_params' not in st.session_state:
            st.session_state['viz_composition_params'] = {}
        st.markdown("---")
        st.markdown(
            '<div class="card-elevated" role="region" aria-label="Composition settings">',
            unsafe_allow_html=True,
        )
        st.markdown('<h2 class="section-title">🎨 Composition Settings</h2>', unsafe_allow_html=True)
        if chart_mode == 'combo':
            col_comp1, col_comp2, col_comp3 = st.columns(3)
            with col_comp1:
                y2_col = st.selectbox(
                    "Second Y-Axis Column",
                    options=cols,
                    key="viz_y2_col",
                    help="Second metric for right y-axis"
                )
            with col_comp2:
                chart1_type = st.selectbox(
                    "First Chart Type",
                    options=['bar', 'line', 'scatter', 'area'],
                    index=0,
                    key="viz_combo_chart1"
                )
            with col_comp3:
                chart2_type = st.selectbox(
                    "Second Chart Type",
                    options=['bar', 'line', 'scatter', 'area'],
                    index=1,
                    key="viz_combo_chart2"
                )
            composition_params = {
                'y2_col': y2_col,
                'chart1_type': chart1_type,
                'chart2_type': chart2_type
            }
        st.markdown('</div>', unsafe_allow_html=True)

    return {
        'chart_type': chart_type,
        'x_col': x_col,
        'y_col': y_col,
        'color_col': color_col,
        'agg_func': agg_func,
        'heatmap_columns': heatmap_columns,
        'chart_title': chart_title,
        'color_palette': color_palette,
        'chart_mode': chart_mode,
        'composition_params': composition_params,
    }
