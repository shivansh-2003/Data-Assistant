"""Pin / dashboard hints row."""

import streamlit as st


def render_action_bar(pinned_count: int) -> None:
    if pinned_count > 0:
        st.caption(f"📊 {pinned_count} chart(s) pinned — enable Dashboard Mode below to view.")
