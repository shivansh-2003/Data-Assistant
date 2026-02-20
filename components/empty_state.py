"""Shared empty state component for consistent no-data UI."""

from typing import Optional
import streamlit as st


def render_empty_state(
    title: str,
    message: str,
    primary_action_label: str,
    primary_action_key: str,
    secondary_action_label: Optional[str] = None,
    secondary_action_key: Optional[str] = None,
    icon: str = "📭",
) -> None:
    """Render a shared empty state card with icon, title, message, and optional actions."""
    st.markdown('<div class="card-elevated" role="region">', unsafe_allow_html=True)
    st.markdown(f"### {icon} {title}")
    st.caption(message)
    col1, col2, _ = st.columns([1, 1, 2])
    with col1:
        st.button(primary_action_label, key=primary_action_key, type="primary")
    if secondary_action_label and secondary_action_key:
        with col2:
            st.button(secondary_action_label, key=secondary_action_key)
    st.markdown("</div>", unsafe_allow_html=True)
