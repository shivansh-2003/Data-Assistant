"""KPI row with column-type hints."""

from __future__ import annotations

import pandas as pd
import streamlit as st


def render_data_summary_metrics(df: pd.DataFrame, selected_table: str) -> None:
    numeric_n = sum(1 for c in df.columns if pd.api.types.is_numeric_dtype(df[c]))
    cat_n = len(df.columns) - numeric_n
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Rows", f"{len(df):,}")
    with col2:
        st.metric("Columns", len(df.columns))
    with col3:
        st.caption("Types")
        st.markdown(f"🔢 **{numeric_n}** numeric · 🔤 **{cat_n}** other")
    with col4:
        st.metric("Table", selected_table)
