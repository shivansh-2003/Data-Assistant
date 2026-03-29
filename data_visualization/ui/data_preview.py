"""Raw data preview table."""

import streamlit as st

from components.data_table import render_advanced_table


def render_data_preview(df, selected_table: str) -> None:
    if st.checkbox("Show Raw Data Preview", key="viz_table"):
        render_advanced_table(
            df,
            key_prefix=f"viz_raw_{selected_table}",
            height=320,
            page_size_default=25,
        )
