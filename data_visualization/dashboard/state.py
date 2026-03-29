"""Dashboard session state keys and helpers."""

import streamlit as st


def ensure_dashboard_state() -> None:
    if "dashboard_charts" not in st.session_state:
        st.session_state["dashboard_charts"] = []
    if "dashboard_layout" not in st.session_state:
        st.session_state["dashboard_layout"] = "2x2"
    if "dashboard_active" not in st.session_state:
        st.session_state["dashboard_active"] = False
    if "dashboard_layout_preset" not in st.session_state:
        st.session_state["dashboard_layout_preset"] = "classic_2x2"
