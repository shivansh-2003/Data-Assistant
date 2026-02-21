"""
Cross-tab cache coordination utilities.

Import and call `on_data_changed()` from:
  - Data Manipulation tab (after every successful MCP operation)
  - InsightBot (after code execution that modifies data)

This ensures the Visualization Centre always shows fresh data
after a manipulation without forcing an unnecessary API call on
every render.
"""

import streamlit as st

# Mirrors the keys used in core/data_fetcher.py
_CACHE_VERSION_KEY = "viz_cache_version"
_TABLES_CACHE_KEY = "viz_tables_cache"
_DF_CACHE_KEY = "viz_df_cache"
_FIG_CACHE_KEY = "viz_fig_cache"


def on_data_changed():
    """
    Call this whenever the underlying data in the session changes.
    Invalidates all visualization caches so the next render fetches
    fresh data from the backend.

    Usage in Data Manipulation tab (app.py):
        from data_visualization.cache_invalidation import on_data_changed

        result = analyze_data_sync(session_id, query)
        if result["success"]:
            on_data_changed()          # ← add this line
            st.success("Done!")
    """
    # Bump version → busts @st.cache_data keyed on version
    st.session_state[_CACHE_VERSION_KEY] = (
        st.session_state.get(_CACHE_VERSION_KEY, 0) + 1
    )

    # Clear all hot-cache entries for tables and DataFrames
    keys_to_delete = [
        k for k in st.session_state
        if k.startswith(_TABLES_CACHE_KEY)
        or k.startswith(_DF_CACHE_KEY)
    ]
    for k in keys_to_delete:
        del st.session_state[k]

    # Clear figure cache so charts regenerate with new data
    if _FIG_CACHE_KEY in st.session_state:
        del st.session_state[_FIG_CACHE_KEY]


def get_cache_stats() -> dict:
    """
    Debug helper — returns current cache state.
    Call from a st.expander in dev mode to inspect cache health.
    """
    version = st.session_state.get(_CACHE_VERSION_KEY, 0)
    hot_table_keys = [k for k in st.session_state if k.startswith(_TABLES_CACHE_KEY)]
    hot_df_keys = [k for k in st.session_state if k.startswith(_DF_CACHE_KEY)]
    fig_count = len(st.session_state.get(_FIG_CACHE_KEY, {}))

    return {
        "cache_version": version,
        "hot_table_cache_entries": len(hot_table_keys),
        "hot_df_cache_entries": len(hot_df_keys),
        "memoized_figures": fig_count,
    }
