"""
Session data fetching for visualization.
"""

import os
import requests
import pandas as pd
from typing import Optional

import streamlit as st

# Session endpoint configuration (should match SESSION_ENDPOINT in app.py)
FASTAPI_URL = os.getenv("FASTAPI_URL", "https://data-assistant-84sf.onrender.com")
SESSION_ENDPOINT = f"{FASTAPI_URL}/api/session"


@st.cache_data(ttl=30, show_spinner=False)
def get_dataframe_from_session(session_id: str, table_name: str) -> Optional[pd.DataFrame]:
    """
    Fetch session data and convert preview to DataFrame.
    Uses preview data (first 10 rows) for visualization.
    For full data, would need to fetch with format=full and deserialize.

    Args:
        session_id: Session ID
        table_name: Name of the table to fetch

    Returns:
        DataFrame or None if error
    """
    try:
        response = requests.get(
            f"{SESSION_ENDPOINT}/{session_id}/tables",
            params={"format": "summary"},
            timeout=10
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

        df = pd.DataFrame(preview_data)
        return df

    except Exception as e:
        st.error(f"Error loading data: {e}")
        return None
