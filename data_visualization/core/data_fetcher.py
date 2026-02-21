"""
Session data fetching for visualization.
Optimized for <1s latency using multi-layer caching strategy:
  Layer 1: st.session_state (in-memory, instant, per-session)
  Layer 2: st.cache_data (TTL-based, survives rerenders)
  Layer 3: FastAPI/Redis (source of truth, only on miss/invalidation)
"""

import os
import requests
import pandas as pd
import streamlit as st
from typing import Optional, Dict, Any

FASTAPI_URL = os.getenv("FASTAPI_URL", "https://data-assistant-84sf.onrender.com")
SESSION_ENDPOINT = f"{FASTAPI_URL}/api/session"

# Cache keys
_TABLES_CACHE_KEY = "viz_tables_cache"
_DF_CACHE_KEY = "viz_df_cache"
_CACHE_VERSION_KEY = "viz_cache_version"


# ── Layer 2: TTL cache for the raw tables API response ────────────────────────
@st.cache_data(ttl=30, show_spinner=False)
def _fetch_tables_from_api(session_id: str, cache_version: int) -> Optional[Dict[str, Any]]:
    """
    Cached HTTP call to FastAPI. cache_version allows manual invalidation
    (increment it to bust the cache without waiting for TTL).
    Returns the raw tables dict or None on error.
    """
    try:
        response = requests.get(
            f"{SESSION_ENDPOINT}/{session_id}/tables",
            params={"format": "summary"},
            timeout=10,
        )
        response.raise_for_status()
        return response.json().get("tables", {})
    except Exception:
        return None


@st.cache_data(ttl=30, show_spinner=False)
def _build_dataframe(session_id: str, table_name: str, cache_version: int) -> Optional[pd.DataFrame]:
    """
    Cached DataFrame construction. Shares the cache_version with _fetch_tables_from_api
    so a single invalidation busts both caches at once.
    """
    tables = _fetch_tables_from_api(session_id, cache_version)
    if tables is None or table_name not in tables:
        return None
    preview_data = tables[table_name].get("preview", [])
    if not preview_data:
        return None
    return pd.DataFrame(preview_data)


# ── Layer 1: session_state hot cache ──────────────────────────────────────────
def get_cache_version() -> int:
    """Return current cache version (increments on data manipulation)."""
    return st.session_state.get(_CACHE_VERSION_KEY, 0)


def invalidate_viz_cache():
    """
    Call this from the Data Manipulation tab after any successful operation.
    Bumps the version so the next visualization render fetches fresh data.
    """
    st.session_state[_CACHE_VERSION_KEY] = st.session_state.get(_CACHE_VERSION_KEY, 0) + 1
    for key in [_TABLES_CACHE_KEY, _DF_CACHE_KEY]:
        if key in st.session_state:
            del st.session_state[key]


def get_tables_from_session(session_id: str) -> Optional[Dict[str, Any]]:
    """
    Get tables dict with hot-cache. Returns instantly on cache hit.
    Cache key includes session_id + cache_version.
    """
    version = get_cache_version()
    hot_key = f"{_TABLES_CACHE_KEY}_{session_id}_{version}"

    if hot_key in st.session_state:
        return st.session_state[hot_key]

    tables = _fetch_tables_from_api(session_id, version)
    if tables is not None:
        st.session_state[hot_key] = tables
    return tables


def get_dataframe_from_session(session_id: str, table_name: str) -> Optional[pd.DataFrame]:
    """
    Get DataFrame with hot-cache. Returns instantly on cache hit (~0ms).
    Falls back to layer-2 TTL cache, then API on full miss.
    """
    version = get_cache_version()
    hot_key = f"{_DF_CACHE_KEY}_{session_id}_{table_name}_{version}"

    if hot_key in st.session_state:
        return st.session_state[hot_key]

    df = _build_dataframe(session_id, table_name, version)
    if df is not None:
        st.session_state[hot_key] = df
    return df
