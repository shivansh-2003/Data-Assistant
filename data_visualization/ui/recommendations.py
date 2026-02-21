"""
Smart recommendations panel UI: expander and recommendation cards.
"""

import pandas as pd
import streamlit as st
from typing import List, Dict, Any

from ..intelligence.recommender import get_chart_recommendations
from components.empty_state import render_empty_state

_CHART_ICONS = {
    'bar': '📊', 'line': '📈', 'scatter': '🔵', 'area': '🌊',
    'box': '📦', 'histogram': '📊', 'pie': '🥧', 'heatmap': '🔥'
}


def _relevance_to_stars(rec: Dict[str, Any]) -> int:
    r = rec.get('relevance', 3)
    try:
        score = int(r) if isinstance(r, (int, float)) else 3
        return max(1, min(5, 6 - score))
    except (ValueError, TypeError):
        return 3


def _render_recommendation_cards(
    df: pd.DataFrame,
    recommendations_list: List[Dict[str, Any]],
    key_prefix: str,
) -> None:
    n = min(3, len(recommendations_list))
    rec_cols = st.columns(n)
    for i in range(n):
        rec = recommendations_list[i]
        idx = i + 1
        with rec_cols[i]:
            st.markdown(
                '<div class="card-interactive" style="padding: 1rem; margin-bottom: 0.75rem;">',
                unsafe_allow_html=True,
            )
            icon = _CHART_ICONS.get(rec.get('chart_type', ''), '📊')
            st.markdown(f"### {icon} {rec.get('chart_type', 'Chart').capitalize()}")
            stars = "⭐" * _relevance_to_stars(rec)
            st.caption(stars)
            reason = (rec.get('reasoning') or 'No reasoning provided')[:80]
            if len((rec.get('reasoning') or '')) > 80:
                reason += "…"
            st.caption(f"💡 {reason}")
            apply_key = f"{key_prefix}_{idx}_{rec.get('chart_type', 'chart')}"
            if st.button("Apply", key=apply_key, use_container_width=True):
                st.session_state['viz_chart_type'] = rec.get('chart_type', 'bar')
                if rec.get('x_column') and rec['x_column'] in df.columns:
                    st.session_state['viz_x_col'] = rec['x_column']
                else:
                    st.session_state['viz_x_col'] = 'None'
                if rec.get('y_column') and rec['y_column'] in df.columns:
                    st.session_state['viz_y_col'] = rec['y_column']
                else:
                    st.session_state['viz_y_col'] = 'None'
                if 'viz_color_col' not in st.session_state:
                    st.session_state['viz_color_col'] = 'None'
                st.success(f"✅ Applied recommendation #{idx}!")
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)


def render_recommendations_panel(df: pd.DataFrame) -> None:
    """Render the Smart Chart Recommendations expander and cards."""
    st.markdown(
        '<div class="card-elevated" role="region" aria-label="Smart chart recommendations">',
        unsafe_allow_html=True,
    )
    if 'viz_recommendations' not in st.session_state:
        st.session_state['viz_recommendations'] = None
    if 'viz_user_goal_text' not in st.session_state:
        st.session_state['viz_user_goal_text'] = ""

    expander_expanded = st.session_state.get('viz_recommendations') is not None
    with st.expander("🤖 Smart Chart Recommendations", expanded=expander_expanded):
        st.caption("Describe your goal to get tailored chart suggestions.")
        col1, col2 = st.columns([3, 1])
        with col1:
            user_goal = st.text_input(
                "Describe your visualization goal (optional):",
                placeholder="e.g., Show sales trends over time, Compare revenue by department",
                key="viz_user_goal",
                value=st.session_state.get('viz_user_goal_text', '')
            )
        with col2:
            recommend_button = st.button("✨ Get Recommendations", type="primary", width='stretch')

        if recommend_button:
            st.session_state['viz_user_goal_text'] = user_goal
            st.session_state['viz_loading_recommendations'] = True
            st.rerun()
        if st.session_state.get('viz_loading_recommendations'):
            st.markdown(
                '<div class="skeleton" style="height:40px;margin-bottom:8px;"></div>'
                '<div class="skeleton" style="height:40px;margin-bottom:8px;"></div>'
                '<div class="skeleton" style="height:32px;"></div>',
                unsafe_allow_html=True,
            )
            with st.spinner("🤔 Analyzing data and generating recommendations..."):
                try:
                    recommendations = get_chart_recommendations(
                        df, st.session_state.get('viz_user_goal_text') or None
                    )
                    st.session_state['viz_recommendations'] = recommendations
                except Exception as e:
                    st.error(f"❌ Error generating recommendations: {str(e)}")
                    st.info("💡 Falling back to rule-based recommendations...")
                    st.session_state['viz_recommendations'] = None
                st.session_state['viz_loading_recommendations'] = False
                if not st.session_state.get('viz_recommendations'):
                    st.session_state['viz_show_empty_rec'] = True
                elif st.session_state.get('viz_recommendations'):
                    st.session_state['viz_just_loaded_rec'] = True
                st.rerun()
        show_just_loaded = (
            bool(st.session_state.get('viz_recommendations'))
            and st.session_state.pop('viz_just_loaded_rec', False)
        )
        if st.session_state.pop('viz_show_empty_rec', False):
            render_empty_state(
                title="No recommendations",
                message="Try describing your goal or select columns manually in Chart Controls.",
                primary_action_label="Try again",
                primary_action_key="empty_viz_rec_try",
                secondary_action_label="Refresh",
                secondary_action_key="empty_viz_rec_refresh",
                icon="🤖",
            )
        elif show_just_loaded:
            recommendations = st.session_state['viz_recommendations']
            if recommendations:
                st.success(f"✅ Found {len(recommendations)} chart recommendations!")
                st.markdown("---")
                _render_recommendation_cards(df, recommendations, "apply_rec_new")

        stored_recommendations = st.session_state.get('viz_recommendations')
        if (
            stored_recommendations
            and not recommend_button
            and not st.session_state.get('viz_loading_recommendations')
            and not show_just_loaded
        ):
            st.markdown("---")
            st.caption("💡 **Saved Recommendations** (click Apply to use):")
            _render_recommendation_cards(df, stored_recommendations, "apply_rec_persist")

    st.markdown('</div>', unsafe_allow_html=True)
    st.divider()
