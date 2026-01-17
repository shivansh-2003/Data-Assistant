"""Advanced data table component with search, filters, sorting, and pagination."""

from typing import Optional, Dict, List, Tuple
import pandas as pd
import streamlit as st
from pandas.api.types import is_numeric_dtype, is_datetime64_any_dtype


@st.cache_data(show_spinner=False)
def _build_search_series(df: pd.DataFrame) -> pd.Series:
    return df.astype(str).agg(" ".join, axis=1).str.lower()


@st.cache_data(show_spinner=False)
def _get_unique_display_values(df: pd.DataFrame, col: str) -> List[str]:
    series = df[col].dropna()
    if series.empty:
        return []
    values = series.astype(str).unique().tolist()
    return sorted(values)


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
    
    # Search functionality
    search_query = st.text_input(
        "Search across all columns",
        placeholder="Type to filter rows...",
        key=f"{key_prefix}_search"
    )

    # Filters section
    with st.expander("Filters", expanded=False):
        filter_cols = st.multiselect(
            "Select columns to filter",
            options=list(df.columns),
            key=f"{key_prefix}_filter_cols"
        )

        filters = {}
        for col in filter_cols:
            series = df[col]
            if is_numeric_dtype(series):
                min_val = series.min()
                max_val = series.max()
                if pd.isna(min_val) or pd.isna(max_val):
                    st.caption(f"{col}: no numeric values available.")
                    continue
                value = st.slider(
                    f"Filter {col}",
                    min_value=float(min_val),
                    max_value=float(max_val),
                    value=(float(min_val), float(max_val)),
                    key=f"{key_prefix}_filter_{col}"
                )
                filters[col] = ("numeric", value)
            elif is_datetime64_any_dtype(series):
                unique_vals = _get_unique_display_values(df, col)
                if not unique_vals:
                    st.caption(f"{col}: no values available.")
                    continue
                filters[col] = ("categorical", st.multiselect(
                    f"Filter {col}",
                    options=unique_vals,
                    key=f"{key_prefix}_filter_{col}"
                ))
            else:
                unique_vals = _get_unique_display_values(df, col)
                if len(unique_vals) > 200:
                    st.caption(f"{col}: too many unique values to show.")
                    continue
                if not unique_vals:
                    st.caption(f"{col}: no values available.")
                    continue
                filters[col] = ("categorical", st.multiselect(
                    f"Filter {col}",
                    options=unique_vals,
                    key=f"{key_prefix}_filter_{col}"
                ))

    # Build a single mask for faster filtering
    mask = pd.Series(True, index=df.index)
    if search_query:
        search_lower = search_query.lower()
        search_series = _build_search_series(df)
        mask &= search_series.str.contains(search_lower, regex=False)
    for col, filter_spec in filters.items():
        ftype, fvalue = filter_spec
        if ftype == "numeric":
            min_val, max_val = fvalue
            mask &= df[col].between(min_val, max_val)
        else:
            if fvalue:
                mask &= df[col].astype(str).isin(fvalue)

    filtered_df = df[mask]

    st.divider()

    # Controls row
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

    total_rows = len(filtered_df)
    page_size_options = [10, 25, 50, 100]
    if total_rows > 0:
        page_size_options = [opt for opt in page_size_options if opt <= total_rows] or [total_rows]
    else:
        page_size_options = [10]

    with col3:
        # Find the index for default page size
        try:
            default_index = page_size_options.index(page_size_default)
        except ValueError:
            default_index = min(len(page_size_options) - 1, 0)
        
        page_size = st.selectbox(
            "Rows per page",
            options=page_size_options,
            index=default_index,
            key=f"{key_prefix}_page_size"
        )

    # Apply sorting
    if sort_col != "(none)":
        filtered_df = filtered_df.sort_values(
            by=sort_col,
            ascending=(sort_dir == "Ascending")
        )

    # Pagination
    total_pages = max(1, (total_rows + page_size - 1) // page_size)

    # Reset to page 1 when filters/search/page size changes
    signature_key = f"{key_prefix}_filter_signature"
    page_key = f"{key_prefix}_page"
    signature = (
        search_query,
        tuple(
            (col, (ftype, tuple(fvalue) if isinstance(fvalue, (list, tuple)) else fvalue))
            for col, (ftype, fvalue) in filters.items()
        ),
        sort_col,
        sort_dir,
        page_size,
    )
    if st.session_state.get(signature_key) != signature:
        st.session_state[signature_key] = signature
        st.session_state[page_key] = 1

    page = st.number_input(
        "Page",
        min_value=1,
        max_value=total_pages,
        value=min(st.session_state.get(page_key, 1), total_pages),
        step=1,
        key=page_key
    )

    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    page_df = filtered_df.iloc[start_idx:end_idx]

    st.caption(f"Showing {len(page_df)} of {total_rows} rows")
    st.dataframe(page_df, width='stretch', height=height, hide_index=True)

    return filtered_df


