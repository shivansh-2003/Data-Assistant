"""Advanced data table component with search, filters, sorting, and pagination."""

from typing import Optional
import pandas as pd
import streamlit as st


def render_advanced_table(
    df: Optional[pd.DataFrame],
    key_prefix: str,
    height: int = 400,
    page_size_default: int = 25
) -> Optional[pd.DataFrame]:
    """Render a data table with search, filters, sorting, and pagination.

    Returns the filtered DataFrame for optional exports.
    """
    if df is None or df.empty:
        st.info("No data available.")
        return None

    st.markdown("**Data Explorer**")
    search_query = st.text_input(
        "Search across all columns",
        placeholder="Type to filter rows...",
        key=f"{key_prefix}_search"
    )

    with st.expander("Filters", expanded=False):
        filter_cols = st.multiselect(
            "Select columns to filter",
            options=list(df.columns),
            key=f"{key_prefix}_filter_cols"
        )

        filters = {}
        for col in filter_cols:
            unique_vals = df[col].dropna().unique()
            if len(unique_vals) > 100:
                st.caption(f"{col}: too many unique values to show.")
                continue
            filters[col] = st.multiselect(
                f"Filter {col}",
                options=sorted(unique_vals.tolist()),
                key=f"{key_prefix}_filter_{col}"
            )

    # Apply search filter
    filtered_df = df.copy()
    if search_query:
        search_lower = search_query.lower()
        mask = filtered_df.apply(
            lambda row: row.astype(str).str.lower().str.contains(search_lower).any(),
            axis=1
        )
        filtered_df = filtered_df[mask]

    # Apply column filters
    for col, values in filters.items():
        if values:
            filtered_df = filtered_df[filtered_df[col].isin(values)]

    st.divider()

    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        sort_col = st.selectbox(
            "Sort by",
            options=["(none)"] + list(filtered_df.columns),
            key=f"{key_prefix}_sort_col"
        )
    with col2:
        sort_dir = st.selectbox(
            "Direction",
            options=["Ascending", "Descending"],
            key=f"{key_prefix}_sort_dir"
        )
    with col3:
        page_size = st.selectbox(
            "Rows per page",
            options=[10, 25, 50, 100],
            index=[10, 25, 50, 100].index(page_size_default) if page_size_default in [10, 25, 50, 100] else 1,
            key=f"{key_prefix}_page_size"
        )

    if sort_col != "(none)":
        filtered_df = filtered_df.sort_values(
            by=sort_col,
            ascending=(sort_dir == "Ascending")
        )

    total_rows = len(filtered_df)
    total_pages = max(1, (total_rows + page_size - 1) // page_size)

    page = st.number_input(
        "Page",
        min_value=1,
        max_value=total_pages,
        value=1,
        step=1,
        key=f"{key_prefix}_page"
    )

    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    page_df = filtered_df.iloc[start_idx:end_idx]

    st.caption(f"Showing {len(page_df)} of {total_rows} rows")
    st.dataframe(page_df, use_container_width=True, height=height, hide_index=True)

    return filtered_df


