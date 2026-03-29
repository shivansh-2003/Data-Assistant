"""Session-backed DataFrame loading for Visualization Centre."""

from __future__ import annotations

import os
from typing import Optional

import pandas as pd
import requests
import streamlit as st

FASTAPI_URL = os.getenv("FASTAPI_URL", "https://data-assistant-hj5f.onrender.com")
SESSION_ENDPOINT = f"{FASTAPI_URL}/api/session"


@st.cache_data(ttl=30, show_spinner=False)
def get_dataframe_from_session(session_id: str, table_name: str) -> Optional[pd.DataFrame]:
    """
    Fetch session data and convert preview to DataFrame (summary format).
    """
    try:
        response = requests.get(
            f"{SESSION_ENDPOINT}/{session_id}/tables",
            params={"format": "summary"},
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()

        tables = data.get("tables", {})
        if table_name not in tables:
            return None

        table_info = tables[table_name]
        preview_data = table_info.get("preview", [])

        if not preview_data:
            return None

        return pd.DataFrame(preview_data)

    except Exception as e:
        st.error(f"Error loading data: {e}")
        return None
