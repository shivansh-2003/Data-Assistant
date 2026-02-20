"""
Streamlit application for Data Analyst Platform.
Connects to FastAPI ingestion endpoint and displays uploaded data.
Includes Data Manipulation tab with natural language queries.
"""

import streamlit as st
import requests
import pandas as pd
from typing import Dict, List, Optional, Any
import os
import asyncio
import time
import uuid
import logging
import graphviz
import base64
import pickle
from datetime import datetime
from data_visualization import render_visualization_tab
from chatbot.streamlit_ui import render_chatbot_tab
from components.data_table import render_advanced_table
from components.empty_state import render_empty_state
from observability.langfuse_client import update_trace_context

logger = logging.getLogger(__name__)

# Configuration using Streamlit secrets
# Falls back to environment variables if secrets not defined
def get_secret(key_path, fallback_env=None, default=None):
    """
    Get secret from st.secrets with fallback to environment variable.
    key_path can be a string like "openai.api_key" for nested keys.
    """
    try:
        keys = key_path.split('.')
        value = st.secrets
        for key in keys:
            value = value[key]
        return value
    except (KeyError, FileNotFoundError):
        if fallback_env:
            return os.getenv(fallback_env, default)
        return default

# FastAPI endpoint configuration
FASTAPI_URL = "https://data-assistant-84sf.onrender.com"
UPLOAD_ENDPOINT = f"{FASTAPI_URL}/api/ingestion/file-upload"
HEALTH_ENDPOINT = f"{FASTAPI_URL}/health"
CONFIG_ENDPOINT = f"{FASTAPI_URL}/api/ingestion/config"
SESSION_ENDPOINT = f"{FASTAPI_URL}/api/session"

# MCP Configuration
MCP_SERVER_URL = "https://data-assistant-84sf.onrender.com/data/mcp"
OPENAI_API_KEY = get_secret("openai.api_key", "OPENAI_API_KEY")
OPENAI_MODEL = "gpt-5.1"  # Fallback to gpt-4o if not specified

# Page configuration
st.set_page_config(
    page_title="Data Analyst Platform",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Theme and UI state initialization
if "ui_theme" not in st.session_state:
    st.session_state.ui_theme = "Auto"
if "show_shortcuts" not in st.session_state:
    st.session_state.show_shortcuts = False
if "onboarding_step" not in st.session_state:
    st.session_state.onboarding_step = 0
if "show_onboarding" not in st.session_state:
    st.session_state.show_onboarding = True

def _resolve_theme_choice(choice: str) -> str:
    if choice == "Auto":
        return "auto"
    return "dark" if choice == "Dark" else "light"

def apply_theme_script(theme: str):
    """Apply theme by setting data-theme attribute on the document element."""
    st.markdown(
        f"""
        <script>
        (function() {{
            const theme = "{theme}";
            if (theme === "auto") {{
                const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
                document.documentElement.setAttribute('data-theme', prefersDark ? 'dark' : 'light');
            }} else {{
                document.documentElement.setAttribute('data-theme', theme);
            }}
        }})();
        </script>
        """,
        unsafe_allow_html=True
    )

def inject_keyboard_shortcuts():
    """Global keyboard shortcuts via query params to trigger UI helpers."""
    st.markdown(
        """
        <script>
        (function() {
            const handler = (event) => {
                const isCmd = event.metaKey || event.ctrlKey;
                if (event.key === '?' && !isCmd) {
                    const url = new URL(window.location.href);
                    url.searchParams.set('shortcuts', '1');
                    window.location.href = url.toString();
                }
                if (isCmd && event.key.toLowerCase() === 'k') {
                    const url = new URL(window.location.href);
                    url.searchParams.set('command_palette', '1');
                    window.location.href = url.toString();
                }
            };
            document.addEventListener('keydown', handler);
        })();
        </script>
        """,
        unsafe_allow_html=True
    )

# Google Fonts for typography
st.markdown(
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">',
    unsafe_allow_html=True
)

# Custom CSS for better styling
st.markdown("""
    <style>
    :root {
        --primary: #667eea;
        --primary-600: #667eea;
        --primary-50: #eef2ff;
        --accent: #f59e0b;
        --accent-600: #d97706;
        --success: #22c55e;
        --warning: #f59e0b;
        --error: #ef4444;
        --text: #111827;
        --muted: #6b7280;
        --border: #e5e7eb;
        --card-bg: #ffffff;
        --shadow-sm: 0 4px 14px rgba(15, 23, 42, 0.08);
        --shadow-md: 0 16px 40px rgba(15, 23, 42, 0.14);
        --radius-sm: 8px;
        --radius-md: 12px;
        --radius-lg: 18px;
        --glass-bg: rgba(255, 255, 255, 0.65);
        --glass-border: rgba(255, 255, 255, 0.4);
        --focus-ring: rgba(102, 126, 234, 0.35);
        --font-sans: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        --font-mono: 'JetBrains Mono', 'SF Mono', Consolas, monospace;
        --text-xs: 0.75rem;
        --text-sm: 0.875rem;
        --text-base: 1rem;
        --text-lg: 1.125rem;
        --text-xl: 1.25rem;
        --text-2xl: 1.5rem;
        --text-3xl: 1.875rem;
        --text-4xl: 2.25rem;
        --weight-medium: 500;
        --weight-semibold: 600;
        --weight-bold: 700;
    }

    [data-theme="dark"] {
        --primary: #818cf8;
        --primary-600: #667eea;
        --primary-50: #1e1b4b;
        --accent: #fbbf24;
        --accent-600: #f59e0b;
        --success: #34d399;
        --warning: #fbbf24;
        --error: #f87171;
        --text: #e5e7eb;
        --muted: #9ca3af;
        --border: #1f2937;
        --card-bg: #0f172a;
        --shadow-sm: 0 6px 18px rgba(0, 0, 0, 0.35);
        --shadow-md: 0 20px 45px rgba(0, 0, 0, 0.5);
        --glass-bg: rgba(15, 23, 42, 0.7);
        --glass-border: rgba(148, 163, 184, 0.2);
        --focus-ring: rgba(129, 140, 248, 0.35);
    }

    body {
        color: var(--text);
        font-family: var(--font-sans);
        font-size: var(--text-base);
    }
    code, pre, .stCode {
        font-family: var(--font-mono);
    }

    /* Skip link for keyboard users */
    .skip-link {
        position: absolute;
        left: -999px;
        top: 0;
        background: #000;
        color: #fff;
        padding: 8px 12px;
        z-index: 1000;
        border-radius: 6px;
    }
    .skip-link:focus {
        left: 16px;
        top: 16px;
    }

    .main-header {
        font-size: var(--text-3xl);
        font-weight: var(--weight-bold);
        color: var(--primary);
        margin-bottom: 0.5rem;
        letter-spacing: -0.5px;
        font-family: var(--font-sans);
    }
    .section-title {
        font-size: var(--text-xl);
        font-weight: var(--weight-semibold);
        margin: 0.5rem 0 0.75rem 0;
        color: var(--text);
    }
    .section-subtitle {
        color: var(--muted);
        font-size: var(--text-sm);
        margin-bottom: 0.5rem;
    }
    .status-badge {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 4px 8px;
        border-radius: 999px;
        font-size: 0.8rem;
        font-weight: 600;
        background: var(--primary-50);
        color: var(--primary-600);
        border: 1px solid var(--border);
        animation: pulse 2.4s ease-in-out infinite;
    }
    .card {
        background: var(--glass-bg);
        border: 1px solid var(--glass-border);
        border-radius: var(--radius-lg);
        padding: 18px;
        box-shadow: var(--shadow-sm);
        backdrop-filter: blur(14px);
    }
    .glass-card {
        background: var(--glass-bg);
        border: 1px solid var(--glass-border);
        border-radius: var(--radius-lg);
        box-shadow: var(--shadow-md);
        backdrop-filter: blur(18px);
        padding: 18px;
    }
    .card-elevated {
        background: var(--glass-bg);
        border: 1px solid var(--glass-border);
        border-radius: 16px;
        padding: 24px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
        backdrop-filter: blur(20px);
        margin-bottom: 1rem;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .card-interactive:hover {
        transform: translateY(-4px);
        box-shadow: 0 8px 30px rgba(0, 0, 0, 0.12);
    }
    .card-interactive {
        background: var(--glass-bg);
        border: 1px solid var(--glass-border);
        border-radius: 16px;
        padding: 24px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
        backdrop-filter: blur(20px);
        margin-bottom: 1rem;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    [data-testid="stFileUploader"] {
        border: 2px dashed var(--border);
        border-radius: 16px;
        padding: 24px;
        min-height: 120px;
    }
    [data-testid="stFileUploader"]:hover {
        border-color: var(--primary);
        background: var(--primary-50);
    }
    .chip-button button {
        border-radius: 999px;
        padding: 6px 12px;
        background: var(--primary-50);
        border: 1px solid var(--border);
        font-weight: var(--weight-medium);
    }
    .chip-button button:hover {
        background: rgba(102, 126, 234, 0.18);
    }

    /* Streamlit component styling */
    .stButton > button {
        border-radius: 10px;
        font-weight: 600;
        transition: all 180ms ease-in-out;
    }
    .stButton > button:focus {
        outline: 2px solid var(--primary);
        outline-offset: 2px;
        box-shadow: 0 0 0 6px var(--focus-ring);
    }
    .stButton > button:focus-visible {
        outline: 2px solid var(--primary);
        outline-offset: 2px;
        box-shadow: 0 0 0 6px var(--focus-ring);
    }
    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: var(--shadow-sm);
    }
    .stTextArea textarea:focus-visible, .stTextInput input:focus-visible,
    .stSelectbox select:focus-visible, .stNumberInput input:focus-visible {
        outline: 2px solid var(--primary);
        outline-offset: 2px;
    }
    .card:hover, .card-elevated:hover {
        box-shadow: 0 8px 28px rgba(0, 0, 0, 0.1);
    }
    .content-fade-in {
        animation: contentFadeIn 0.35s ease-out;
    }
    @keyframes contentFadeIn {
        from { opacity: 0; transform: translateY(8px); }
        to { opacity: 1; transform: translateY(0); }
    }
    div[data-testid="stMetric"] {
        background: var(--card-bg);
        border: 1px solid var(--border);
        border-radius: var(--radius-sm);
        padding: 10px 12px;
        box-shadow: var(--shadow-sm);
        transition: transform 160ms ease;
    }
    div[data-testid="stMetric"]:hover {
        transform: translateY(-2px);
    }
    div[data-testid="stExpander"] {
        border: 1px solid var(--border);
        border-radius: var(--radius-md);
        background: var(--card-bg);
    }
    div[data-testid="stExpander"] summary {
        font-weight: 600;
    }
    div[data-testid="stTabs"] button {
        font-weight: 600;
    }
    div[data-testid="stCaptionContainer"] {
        color: var(--muted);
    }
    .stTextArea textarea, .stTextInput input, .stSelectbox select, .stNumberInput input {
        border-radius: 10px;
    }
    .stAlert {
        border-radius: var(--radius-md);
    }

    /* Chat styling */
    div[data-testid="stChatMessage"] {
        border-radius: 12px;
        padding: 8px 10px;
        box-shadow: var(--shadow-sm);
    }

    /* Scrollbar styling */
    ::-webkit-scrollbar {
        width: 10px;
        height: 10px;
    }
    ::-webkit-scrollbar-thumb {
        background: rgba(148, 163, 184, 0.45);
        border-radius: 999px;
    }
    ::-webkit-scrollbar-track {
        background: transparent;
    }

    @keyframes pulse {
        0%, 100% { opacity: 0.9; }
        50% { opacity: 0.6; }
    }

    /* Responsive: small screens */
    @media (max-width: 640px) {
        .main-header {
            font-size: 1.6rem;
        }
        .card-elevated, .card, .glass-card {
            padding: 16px;
        }
        div[data-testid="stMetric"] {
            padding: 8px 10px;
        }
        .stButton > button {
            width: 100%;
            min-height: 44px;
            padding: 10px 16px;
        }
        div[data-testid="stHorizontalBlock"] {
            flex-direction: column;
            gap: 0.75rem;
        }
    }
    /* Responsive: tablet */
    @media (min-width: 641px) and (max-width: 1024px) {
        .main-header {
            font-size: 2rem;
        }
        .stButton > button {
            min-height: 44px;
        }
    }
    /* Touch targets */
    @media (max-width: 1024px) {
        .stButton > button {
            min-height: 44px;
        }
    }
    </style>
""", unsafe_allow_html=True)


def card_open(class_name: str = "card-elevated"):
    """Render opening div for a card wrapper. Call card_close() after content."""
    st.markdown(f'<div class="{class_name}" role="region">', unsafe_allow_html=True)


def card_close():
    """Render closing div for a card wrapper."""
    st.markdown("</div>", unsafe_allow_html=True)


@st.cache_data(ttl=30, show_spinner=False)
def check_api_health() -> bool:
    """Check if FastAPI server is running."""
    try:
        response = requests.get(HEALTH_ENDPOINT, timeout=5)
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False


@st.cache_data(ttl=300, show_spinner=False)
def get_api_config() -> Dict:
    """Get API configuration."""
    try:
        response = requests.get(CONFIG_ENDPOINT, timeout=5)
        if response.status_code == 200:
            return response.json()
        return {}
    except:
        return {}


def upload_file(file, file_type: str = None, session_id: str = None) -> Dict:
    """Upload file to FastAPI endpoint."""
    try:
        files = {"file": (file.name, file.getvalue(), file.type)}
        data = {}
        if file_type:
            data["file_type"] = file_type
        if session_id:
            data["session_id"] = session_id
        
        response = requests.post(UPLOAD_ENDPOINT, files=files, data=data, timeout=60)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"success": False, "error": str(e)}


def upload_url(url: str, file_type: str = None, session_id: str = None) -> Dict:
    """Upload a file from a URL to FastAPI endpoint."""
    try:
        payload = {"url": url}
        if file_type:
            payload["file_type"] = file_type
        if session_id:
            payload["session_id"] = session_id
        response = requests.post(f"{FASTAPI_URL}/api/ingestion/url-upload", json=payload, timeout=60)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"success": False, "error": str(e)}


def upload_supabase(connection_string: str, schema: str = "public",
                    session_id: str = None, project_name: str = None) -> Dict:
    """Import tables from Supabase using a Postgres connection string."""
    try:
        payload = {"connection_string": connection_string, "schema": schema}
        if session_id:
            payload["session_id"] = session_id
        if project_name:
            payload["project_name"] = project_name
        response = requests.post(f"{FASTAPI_URL}/api/ingestion/supabase-import", json=payload, timeout=120)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"success": False, "error": str(e)}




def delete_redis_session(session_id: str) -> bool:
    """Delete session data from Redis."""
    if not session_id:
        return False
    try:
        response = requests.delete(f"{SESSION_ENDPOINT}/{session_id}", timeout=5)
        return response.status_code == 200
    except:
        return False


def cleanup_current_session():
    """Clean up current session from Redis if exists."""
    # Check session state
    if "current_session_id" in st.session_state and st.session_state.current_session_id:
        delete_redis_session(st.session_state.current_session_id)
        st.session_state.current_session_id = None
    
    # Also check query params (persists across reloads)
    if "sid" in st.query_params:
        delete_redis_session(st.query_params["sid"])
        del st.query_params["sid"]


def save_session_id(session_id: str):
    """Save session_id to both session state and query params."""
    st.session_state.current_session_id = session_id
    st.query_params["sid"] = session_id
    update_trace_context(session_id=session_id, metadata={"source": "streamlit"})


# ============================================================================
# MCP Client Integration (Synchronous Wrappers)
# ============================================================================

def analyze_data_sync(session_id: str, query: str) -> Dict[str, Any]:
    """
    Synchronous wrapper for MCP client analyze_data function.
    
    Args:
        session_id: Session ID containing the data in Redis
        query: Natural language query describing what to do with the data
        
    Returns:
        Dict with 'success', 'response', and optional 'error' keys
    """
    try:
        # Import here to avoid issues if mcp_client not available
        from mcp_client import analyze_data
        
        # Run async function in sync context
        response = asyncio.run(analyze_data(session_id, query))
        return {"success": True, "response": response}
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_session_tables_for_display(session_id: str) -> Optional[Dict]:
    """
    Fetch current tables from session for display.
    
    Args:
        session_id: Session ID to fetch tables for
        
    Returns:
        Dict with session data or None if error
    """
    try:
        response = requests.get(
            f"{SESSION_ENDPOINT}/{session_id}/tables",
            params={"format": "summary"},
            timeout=10
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching session tables: {e}")
        return None


def get_session_metadata_for_display(session_id: str) -> Optional[Dict]:
    """
    Fetch session metadata.
    
    Args:
        session_id: Session ID to fetch metadata for
        
    Returns:
        Dict with metadata or None if error
    """
    try:
        response = requests.get(
            f"{SESSION_ENDPOINT}/{session_id}/metadata",
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        return data.get("metadata")
    except requests.exceptions.RequestException:
        return None


@st.cache_data(ttl=60, show_spinner=False)
def get_full_table_dataframe(session_id: str, table_name: str) -> Optional[pd.DataFrame]:
    """Fetch full table data from backend and deserialize into a DataFrame."""
    try:
        response = requests.get(
            f"{SESSION_ENDPOINT}/{session_id}/tables",
            params={"format": "full"},
            timeout=30
        )
        response.raise_for_status()
        data = response.json()
        for table_info in data.get("tables", []):
            if table_info.get("table_name") == table_name:
                payload = table_info.get("data")
                if not payload:
                    return None
                decoded = base64.b64decode(payload)
                return pickle.loads(decoded)
        return None
    except requests.exceptions.RequestException:
        return None
    except Exception:
        return None




def display_table_info(
    table_info: Dict,
    table_index: int,
    session_id: Optional[str] = None,
    table_name: Optional[str] = None
):
    """Display information about a single table."""
    display_name = table_name or table_info.get("table_name") or f"Table {table_index + 1}"
    st.subheader(f"📋 {display_name}")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Rows", f"{table_info['row_count']:,}")
    with col2:
        st.metric("Columns", table_info['column_count'])
    with col3:
        if 'attributes' in table_info and 'confidence' in table_info['attributes']:
            st.metric("Confidence", f"{table_info['attributes']['confidence']:.2%}")
    
    # Display columns and data types
    with st.expander("📊 Column Information"):
        col_df = pd.DataFrame({
            "Column": table_info['columns'],
            "Data Type": [table_info['dtypes'].get(col, 'unknown') for col in table_info['columns']]
        })
        st.dataframe(col_df, width='stretch')
    
    # Display full data table (no preview)
    if session_id and table_name:
        full_df = get_full_table_dataframe(session_id, table_name)
        if full_df is not None and not full_df.empty:
            st.subheader("📊 Data Explorer")
            filtered_df = render_advanced_table(
                full_df,
                key_prefix=f"table_{table_index}_{table_name}",
                height=320,
                page_size_default=10
            )
            
            # Download button for full data
            export_df = filtered_df if filtered_df is not None else full_df
            csv = export_df.to_csv(index=False)
            st.download_button(
                label=f"📥 Download {display_name} as CSV",
                data=csv,
                file_name=f"{display_name}.csv",
                mime="text/csv",
                key=f"download_{table_index}"
            )
        else:
            st.warning("Full table data is not available yet. Please try again.")


def render_ingestion_result(result: Dict, session_id_input: Optional[str] = None):
    """Render ingestion results for file, URL, or Supabase imports."""
    if result.get("success"):
        save_session_id(result.get("session_id"))
        card_open("card-elevated")
        st.success("✅ File processed successfully!")
        
        metadata = result.get("metadata", {})
        session_id = result.get("session_id")
        tables_data = get_session_tables_for_display(session_id) if session_id else None
        tables_map = tables_data.get("tables", {}) if tables_data else {}
        table_count = metadata.get("table_count", 0)
        file_type = metadata.get("file_type", "unknown").upper()
        # Compact summary row
        row_total = 0
        col_total = 0
        if tables_map:
            for t in tables_map.values():
                row_total += t.get("row_count", 0) or 0
                cols = t.get("column_count", 0) or len(t.get("columns", []))
                if cols > col_total:
                    col_total = cols
        summary_parts = [f"{table_count} table(s)", f"{row_total:,} rows", f"{col_total} cols", file_type]
        st.caption(" · ".join(summary_parts))
        
        # CTAs
        cta1, cta2, cta3 = st.columns([1, 1, 2])
        with cta1:
            if st.button("Start Exploring", key="ingestion_cta_explore", type="primary"):
                st.session_state.upload_result_go_tab = "explore"
                st.rerun()
        with cta2:
            if st.button("View Details", key="ingestion_cta_details"):
                st.session_state.expand_table_preview = True
                st.rerun()
        if st.session_state.get("upload_result_go_tab") == "explore":
            st.info("👉 Open the **Chatbot** or **Visualization Centre** tab above to explore your data.")
            if st.button("Dismiss", key="ingestion_dismiss"):
                st.session_state.upload_result_go_tab = None
                st.rerun()
        
        st.markdown("---")
        st.header("📈 Processing Results")
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("File Type", file_type)
        with col2:
            st.metric("Tables Found", table_count)
        with col3:
            st.metric("Processing Time", f"{metadata.get('processing_time', 0)}s")
        with col4:
            if session_id_input:
                st.metric("Session ID", session_id_input[:8] + "...")
        
        errors = metadata.get("errors", [])
        if errors:
            st.warning(f"⚠️ Warnings: {len(errors)} issue(s) encountered")
            with st.expander("View Warnings"):
                for error in errors:
                    st.text(f"• {error}")
        
        st.markdown("---")
        
        tables = result.get("tables", [])
        if tables:
            table_names = list(tables_map.keys())
            expand_preview = st.session_state.get("expand_table_preview", False)
            with st.expander("View table preview", expanded=expand_preview):
                st.header(f"📊 Extracted Tables ({len(tables)})")
                if len(tables) > 1:
                    tab_names = [table_names[i] if i < len(table_names) else f"Table {i+1}" for i in range(len(tables))]
                    tabs = st.tabs(tab_names)
                    for idx, tab in enumerate(tabs):
                        with tab:
                            if idx < len(table_names):
                                table_name = table_names[idx]
                                display_table_info(tables_map.get(table_name, tables[idx]), idx, session_id, table_name)
                            else:
                                display_table_info(tables[idx], idx, session_id, None)
                else:
                    table_name = table_names[0] if table_names else None
                    table_info = tables_map.get(table_name, tables[0]) if table_name else tables[0]
                    display_table_info(table_info, 0, session_id, table_name)
        else:
            st.warning("No tables found in the uploaded file.")
        card_close()
    else:
        error_msg = result.get("error", "Unknown error occurred")
        st.error(f"❌ Failed to process file: {error_msg}")
        st.info("Try a smaller file, or specify the file type manually.")
        
        metadata = result.get("metadata", {})
        if metadata.get("errors"):
            with st.expander("Error Details"):
                for error in metadata["errors"]:
                    st.text(f"• {error}")


def initialize_session_state():
    """Initialize all session state variables."""
    if "current_session_id" not in st.session_state:
        st.session_state.current_session_id = None
        # On fresh load, check if there's a stale session in query params to cleanup
        if "sid" in st.query_params:
            delete_redis_session(st.query_params["sid"])
            del st.query_params["sid"]
    
    if "last_file_id" not in st.session_state:
        st.session_state.last_file_id = None
    
    if "last_ingestion_result" not in st.session_state:
        st.session_state.last_ingestion_result = None
    if "last_ingestion_file_id" not in st.session_state:
        st.session_state.last_ingestion_file_id = None
    
    # Operation history
    if "operation_history" not in st.session_state:
        st.session_state.operation_history = []


def render_onboarding_tip(title: str, steps: List[str], cta_label: Optional[str] = None, cta_key: Optional[str] = None):
    """Render onboarding tips when enabled."""
    if not st.session_state.get("show_onboarding", True):
        return
    with st.expander(f"✨ {title}", expanded=False):
        for step in steps:
            st.markdown(f"- {step}")
        if cta_label:
            st.button(cta_label, key=cta_key or f"cta_{title}", help="Quick action to get started")


def render_upload_tab():
    """Render the Upload tab content."""
    card_open("card-elevated")
    st.markdown('<p class="section-subtitle" style="margin-top:0;">Upload Your Data</p>', unsafe_allow_html=True)
    st.header("📤 Upload Your Data")
    st.caption("Drag & drop or click to upload. We will extract tables and prepare them for analysis.")

    render_onboarding_tip(
        "Upload in 3 steps",
        [
            "Drag and drop a CSV, Excel, or image file.",
            "Optionally set file type and session ID.",
            "Click Upload & Process to extract tables."
        ],
        cta_label="Jump to upload",
        cta_key="cta_upload_tab"
    )
    
    # Quick steps
    step1, step2, step3 = st.columns(3)
    with step1:
        st.markdown("**1. Upload**")
        st.caption("CSV, Excel, or image files")
    with step2:
        st.markdown("**2. Process**")
        st.caption("We extract tables and metadata")
    with step3:
        st.markdown("**3. Explore**")
        st.caption("Visualize and query your data")
    
    # File type pills (set selectbox value on click)
    if "upload_file_type_hint" not in st.session_state:
        st.session_state.upload_file_type_hint = "Auto-detect"
    st.markdown("**File type** (optional)")
    pill_col1, pill_col2, pill_col3, _ = st.columns([1, 1, 1, 3])
    with pill_col1:
        if st.button("CSV", key="pill_csv", use_container_width=True):
            st.session_state.upload_file_type_hint = "csv"
            st.rerun()
    with pill_col2:
        if st.button("XLSX", key="pill_xlsx", use_container_width=True):
            st.session_state.upload_file_type_hint = "excel"
            st.rerun()
    with pill_col3:
        if st.button("PNG", key="pill_png", use_container_width=True):
            st.session_state.upload_file_type_hint = "image"
            st.rerun()
    
    # File uploader
    uploaded_file = st.file_uploader(
        "Choose a file to upload",
        type=['csv', 'xlsx', 'xls', 'png', 'jpg', 'jpeg', 'tiff', 'bmp'],
        help="Supported formats: CSV, Excel, Images"
    )
    st.caption("CSV, Excel, Images supported. Max 100MB. For large files, prefer CSV or Excel for faster processing.")
    card_close()
    
    # Detect file clear/removal - cleanup Redis
    current_file_id = uploaded_file.file_id if uploaded_file else None
    if st.session_state.last_file_id and current_file_id != st.session_state.last_file_id:
        # File was removed or changed - cleanup old session
        cleanup_current_session()
        st.session_state.last_ingestion_result = None
        st.session_state.last_ingestion_file_id = None
    st.session_state.last_file_id = current_file_id
    
    # Optional file type hint (synced with pills)
    opts = ["Auto-detect", "csv", "excel", "pdf", "image"]
    idx = opts.index(st.session_state.upload_file_type_hint) if st.session_state.upload_file_type_hint in opts else 0
    file_type_hint = st.selectbox(
        "File Type (Optional - Auto-detected if not specified)",
        opts,
        index=idx,
        key="upload_file_type_select",
        help="Manually specify file type if auto-detection fails"
    )
    st.session_state.upload_file_type_hint = file_type_hint
    file_type = None if file_type_hint == "Auto-detect" else file_type_hint
    
    # Session ID (optional)
    session_id = st.text_input("Session ID (Optional)", help="Optional session identifier for tracking")
    
    # Upload button
    if uploaded_file is not None:
        col1, col2 = st.columns([1, 4])
        with col1:
            upload_button = st.button(
                "🚀 Upload & Process",
                type="primary",
                help="Upload the file and extract tables for analysis"
            )
        
        if upload_button:
            with st.status("Uploading and processing file...", expanded=True) as status:
                progress = st.progress(0)
                progress.progress(0.2, text="Uploading file")
                result = upload_file(uploaded_file, file_type, session_id if session_id else None)
                progress.progress(0.8, text="Extracting tables")
                st.session_state.last_ingestion_result = result
                st.session_state.last_ingestion_file_id = current_file_id
                render_ingestion_result(result, session_id_input=session_id)
                progress.progress(1.0, text="Completed")
                status.update(label="Processing complete", state="complete")
        elif (
            st.session_state.last_ingestion_result
            and st.session_state.last_ingestion_file_id == current_file_id
        ):
            render_ingestion_result(st.session_state.last_ingestion_result, session_id_input=session_id)
    
    else:
        # No file uploaded - cleanup any existing session
        cleanup_current_session()
        st.session_state.last_ingestion_result = None
        st.session_state.last_ingestion_file_id = None
        
        render_empty_state(
            title="No data loaded yet",
            message="Upload a CSV, Excel, or image file above to extract tables and start exploring.",
            primary_action_label="Upload File",
            primary_action_key="empty_upload_btn",
            secondary_action_label="How to use",
            secondary_action_key="empty_howto_btn",
            icon="📭",
        )
        # Example section
        with st.expander("📖 How to use"):
            st.markdown("""
            ### Steps:
            1. **Start FastAPI server**: Run `python main.py` in your terminal
            2. **Upload a file**: Use the file uploader above
            3. **View results**: Explore the extracted tables and data
            
            ### Supported File Types:
            - **CSV/TSV**: Comma or tab-separated values
            - **Excel**: .xlsx, .xls, .xlsm files (all sheets processed)
            - **Images**: PNG, JPEG, TIFF, BMP with tables (OCR-based extraction)
            
            ### Features:
            - Automatic file type detection
            - Multiple table extraction
            - Data preview and download
            - Column information and statistics
            """)

    st.divider()
    st.subheader("🌐 Upload From URL")
    with st.expander("Import a file from a URL", expanded=False):
        url_input = st.text_input(
            "File URL (http/https)",
            placeholder="https://example.com/data.csv",
            help="Paste a direct link to a CSV, Excel, or image file"
        )
        url_file_type_hint = st.selectbox(
            "File Type (Optional - Auto-detected if not specified)",
            ["Auto-detect", "csv", "excel", "image"],
            key="url_file_type_hint"
        )
        url_file_type = None if url_file_type_hint == "Auto-detect" else url_file_type_hint
        url_session_id = st.text_input(
            "Session ID (Optional)",
            key="url_session_id",
            help="Optional session identifier for tracking"
        )
        if st.button("⬇️ Fetch & Process URL", key="url_upload_button", type="primary"):
            if not url_input:
                st.warning("Please provide a valid URL.")
            else:
                with st.status("Downloading and processing URL...", expanded=True) as status:
                    progress = st.progress(0)
                    progress.progress(0.2, text="Fetching file")
                    result = upload_url(url_input, url_file_type, url_session_id if url_session_id else None)
                    progress.progress(0.8, text="Extracting tables")
                    render_ingestion_result(result, session_id_input=url_session_id)
                    progress.progress(1.0, text="Completed")
                    status.update(label="Processing complete", state="complete")

    st.divider()
    st.subheader("🧩 Import From Supabase")
    with st.expander("Connect using Postgres connection string", expanded=False):
        project_name = st.text_input(
            "Project Name (Optional)",
            key="supabase_project_name",
            help="Helps label the session for easier tracking"
        )
        connection_string = st.text_input(
            "Postgres Connection String (Required)",
            type="password",
            key="supabase_connection_string",
            placeholder="postgres://user:password@db.<project>.supabase.co:5432/postgres"
        )
        schema_name = st.text_input(
            "Schema (Optional)",
            value="public",
            key="supabase_schema"
        )
        supabase_session_id = st.text_input(
            "Session ID (Optional)",
            key="supabase_session_id",
            help="Optional session identifier for tracking"
        )
        if st.button("🔗 Import Supabase Tables", key="supabase_import_button", type="primary"):
            if not connection_string:
                st.warning("Please provide a connection string.")
            else:
                with st.status("Connecting to Supabase and importing tables...", expanded=True) as status:
                    progress = st.progress(0)
                    progress.progress(0.3, text="Connecting to Supabase")
                    result = upload_supabase(
                        connection_string=connection_string,
                        schema=schema_name or "public",
                        session_id=supabase_session_id if supabase_session_id else None,
                        project_name=project_name or None
                    )
                    progress.progress(0.9, text="Importing tables")
                    render_ingestion_result(result, session_id_input=supabase_session_id)
                    progress.progress(1.0, text="Completed")
                    status.update(label="Import complete", state="complete")


def render_manipulation_tab():
    """Render the Data Manipulation tab content."""
    st.header("🔧 Data Manipulation")
    st.caption("Use natural language to transform your data. Each operation creates a new version you can revisit.")

    render_onboarding_tip(
        "Try a transformation",
        [
            "Pick a table and review the current state.",
            "Type a natural language query (e.g., filter, sort, group).",
            "Execute to create a new version in the history graph."
        ],
        cta_label="Use example query",
        cta_key="cta_manipulation_example"
    )
    
    session_id = st.session_state.get("current_session_id")
    
    # Check if session exists
    if not session_id:
        render_empty_state(
            title="No data loaded yet",
            message="Upload a file in the Upload tab first. Then you can transform your data with natural language here.",
            primary_action_label="Go to Upload",
            primary_action_key="empty_manipulation_upload",
            secondary_action_label="Example queries",
            secondary_action_key="empty_manipulation_examples",
            icon="🔧",
        )
        with st.expander("💡 Example Queries (after uploading data)"):
            st.markdown("""
            - "Remove rows with missing values in the 'email' column"
            - "Sort the data by 'revenue' in descending order"
            - "Filter rows where 'age' is greater than 18"
            - "Create a new column 'full_name' by combining 'first_name' and 'last_name'"
            - "Group by 'department' and calculate average 'salary'"
            - "Drop columns 'temp1' and 'temp2'"
            """)
        return
    
    # Get session metadata and extend TTL
    metadata = get_session_metadata_for_display(session_id)
    if not metadata:
        st.error(f"❌ Session '{session_id}' not found or expired. Please upload a new file.")
        # Clear session state
        st.session_state.current_session_id = None
        if "sid" in st.query_params:
            del st.query_params["sid"]
        return
    
    # Extend session TTL on access
    try:
        requests.post(f"{SESSION_ENDPOINT}/{session_id}/extend", timeout=5)
    except:
        pass  # Non-critical, continue anyway
    
    # Session Info Card
    card_open("card-elevated")
    st.subheader("📋 Session Information")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Session ID", session_id[:12] + "..." if len(session_id) > 12 else session_id)
    with col2:
        file_name = metadata.get("file_name", "Unknown")
        st.metric("File Name", file_name[:20] + "..." if len(file_name) > 20 else file_name)
    with col3:
        st.metric("Tables", metadata.get("table_count", 0))
    with col4:
        created_at = metadata.get("created_at", 0)
        if created_at:
            dt = datetime.fromtimestamp(created_at)
            st.metric("Created", dt.strftime("%H:%M:%S"))
    
    st.divider()
    
    # Get current tables
    tables_data = get_session_tables_for_display(session_id)
    if not tables_data:
        st.error("❌ Could not load tables from session.")
        return
    
    # Display current state metrics
    st.subheader("📊 Current Data State")
    tables = tables_data.get("tables", {})
    if tables:
        # Show metrics for first table (or allow selection if multiple)
        table_names = list(tables.keys())
        selected_table = st.selectbox("Select Table", table_names, key="selected_table_manipulation")
        
        if selected_table:
            table_info = tables[selected_table]
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Rows", f"{table_info.get('row_count', 0):,}")
            with col2:
                st.metric("Columns", table_info.get('column_count', 0))
            with col3:
                st.metric("Table Name", selected_table)
    
    card_close()
    
    # Version History Graph Section
    card_open("card-elevated")
    st.subheader("📜 Version History")
    st.caption("Track transformations over time. Filter versions and branch safely.")
    
    def _format_version_label(node: Dict, current_version: str) -> str:
        vid = node.get("id", "unknown")
        op = node.get("operation") or node.get("label", "Operation")
        ts = node.get("timestamp")
        ts_text = ""
        if ts:
            try:
                ts_text = datetime.fromtimestamp(ts).strftime("%H:%M:%S")
            except Exception:
                ts_text = ""
        if vid == current_version:
            return f"{vid} (current) - {op} {ts_text}".strip()
        return f"{vid} - {op} {ts_text}".strip()
    
    def _normalize_graph(graph: Dict, current_version: str, search_text: str, keep_last_n: int) -> Dict:
        nodes = graph.get("nodes", [])
        edges = graph.get("edges", [])
        
        # Sort nodes by timestamp (newest first)
        nodes_sorted = sorted(nodes, key=lambda n: n.get("timestamp", 0), reverse=True)
        if keep_last_n:
            nodes_sorted = nodes_sorted[:keep_last_n]
        
        if search_text:
            search_text_lower = search_text.lower()
            nodes_sorted = [
                n for n in nodes_sorted
                if search_text_lower in (n.get("operation", "") or n.get("label", "")).lower()
            ]
        
        node_ids = {n.get("id") for n in nodes_sorted}
        edges_filtered = [e for e in edges if e.get("from") in node_ids and e.get("to") in node_ids]
        
        return {"nodes": nodes_sorted, "edges": edges_filtered}
    
    try:
        response = requests.get(f"{FASTAPI_URL}/api/session/{session_id}/versions", timeout=5)
        response.raise_for_status()
        graph_data = response.json().get("graph", {"nodes": [], "edges": []})
    except Exception:
        st.info("No version history yet. Perform operations to build the graph.")
        graph_data = {"nodes": [], "edges": []}
    
    # Filters and layout
    if graph_data.get("nodes"):
        filter_col, info_col = st.columns([2, 3])
        with filter_col:
            st.markdown("**Filters**")
            keep_last_n = st.number_input(
                "Show last N versions",
                min_value=1,
                max_value=200,
                value=min(30, len(graph_data.get("nodes", []))),
                help="Limit the number of versions to improve readability"
            )
            search_text = st.text_input(
                "Search operation text",
                placeholder="e.g., filter, sort, missing"
            )
        with info_col:
            current_version = metadata.get("current_version", "v0")
            st.markdown(f"**Current version:** `{current_version}`")
            st.caption("Select a version to view details and branch.")
        
        graph_data = _normalize_graph(graph_data, current_version, search_text, keep_last_n)
        
        view_mode = st.radio(
            "View",
            ["Graph view", "Timeline view"],
            key="manipulation_version_view",
            horizontal=True,
            label_visibility="collapsed",
        )
    
    # Render graph or timeline if nodes exist
    if graph_data.get("nodes"):
        current_version = metadata.get("current_version", "v0")
        if st.session_state.get("manipulation_version_view", "Graph view") == "Timeline view":
            # Timeline view: horizontal version cards
            st.caption("Click Branch to create a new branch from that version.")
            nodes_list = graph_data.get("nodes", [])
            # Show up to 8 in a row, then next row
            chunk = 4
            for i in range(0, len(nodes_list), chunk):
                cols = st.columns(min(chunk, len(nodes_list) - i))
                for j, node in enumerate(nodes_list[i : i + chunk]):
                    with cols[j]:
                        vid = node.get("id", "?")
                        op = (node.get("operation") or node.get("label", "Operation"))[:40]
                        ts = node.get("timestamp")
                        ts_text = datetime.fromtimestamp(ts).strftime("%H:%M") if ts else ""
                        is_current = vid == current_version
                        st.markdown(f"**{vid}**" + (" *(current)*" if is_current else ""))
                        st.caption(op + (" …" if len((node.get("operation") or "") or (node.get("label") or "")) > 40 else ""))
                        st.caption(ts_text)
                        if st.button("Branch", key=f"timeline_branch_{vid}", type="secondary"):
                            try:
                                r = requests.post(
                                    f"{FASTAPI_URL}/api/session/{session_id}/branch",
                                    json={"version_id": vid},
                                    timeout=10,
                                )
                                if r.status_code == 200:
                                    st.success(f"Branched to {vid}")
                                    st.rerun()
                                else:
                                    st.error("Branch failed")
                            except Exception as e:
                                st.error(str(e))
            st.markdown("---")
        else:
            # Graph view
            dot = graphviz.Digraph(comment='Version History')
            dot.attr(rankdir='LR')
            dot.attr('node', shape='box', style='rounded,filled', fillcolor='lightblue')
            for node in graph_data.get("nodes", []):
                label = _format_version_label(node, current_version)
                is_current = node.get("id") == current_version
                fill = "lightgreen" if is_current else "lightblue"
                dot.node(node["id"], label, fillcolor=fill)
            for edge in graph_data.get("edges", []):
                dot.edge(edge["from"], edge["to"], label=edge.get("label", ""))
            st.graphviz_chart(dot.source)
            col1, col2 = st.columns([2, 2])
            with col1:
                version_options = [n["id"] for n in graph_data.get("nodes", [])]
                selected_version = st.selectbox(
                    "Select version",
                    options=version_options,
                    index=version_options.index(current_version) if current_version in version_options else 0,
                    help="Pick a version to view details or branch from."
                )
            with col2:
                version_node = next((n for n in graph_data.get("nodes", []) if n["id"] == selected_version), None)
                if version_node:
                    op_text = version_node.get("operation", "N/A")
                    ts = version_node.get("timestamp")
                    ts_text = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S") if ts else "N/A"
                    st.markdown("**Version Details**")
                    st.write(f"**Operation:** {op_text}")
                    if version_node.get("query"):
                        st.write(f"**Query:** {version_node.get('query')}")
                    st.write(f"**Created:** {ts_text}")
            col1, col2 = st.columns([3, 1])
            with col1:
                confirm_branch = st.checkbox(
                    "Confirm branch to selected version",
                    value=False,
                    help="Confirm before changing the active version"
                )
            with col2:
                branch_button = st.button("🌿 Branch", type="secondary", help="Create a new branch from the selected version")
            if branch_button:
                if selected_version == current_version:
                    st.info("You are already on this version.")
                elif not confirm_branch:
                    st.warning("Please confirm the branch action first.")
                else:
                    with st.spinner("Branching to selected version..."):
                        try:
                            branch_response = requests.post(
                                f"{FASTAPI_URL}/api/session/{session_id}/branch",
                                json={"version_id": selected_version},
                                timeout=10
                            )
                            if branch_response.status_code == 200:
                                st.success(f"✅ Branched to {selected_version}. New operations will start from here.")
                                st.rerun()
                            else:
                                st.error("Failed to branch to version.")
                        except Exception as e:
                            st.error(f"Error branching: {e}")
            if selected_version:
                with st.expander(f"📋 Version Details: {selected_version}"):
                    version_node = next((n for n in graph_data.get("nodes", []) if n["id"] == selected_version), None)
                    if version_node:
                        st.write(f"**Operation:** {version_node.get('operation', 'N/A')}")
                        if version_node.get('query'):
                            st.write(f"**Query:** {version_node.get('query')}")
                        if version_node.get('timestamp'):
                            dt = datetime.fromtimestamp(version_node['timestamp'])
                            st.write(f"**Created:** {dt.strftime('%Y-%m-%d %H:%M:%S')}")
            with st.expander("🗑️ Prune Versions"):
                col1, col2 = st.columns([2, 1])
                with col1:
                    keep_n = st.number_input(
                        "Keep last N versions",
                        min_value=1,
                        max_value=100,
                        value=len(graph_data.get("nodes", [])),
                        help="Prune old versions, keeping only the most recent N"
                    )
                with col2:
                    prune_button = st.button("Prune", type="secondary", help="Remove old versions and keep the most recent N")
                if prune_button:
                    with st.spinner("Pruning versions..."):
                        try:
                            prune_response = requests.post(
                                f"{FASTAPI_URL}/api/session/{session_id}/prune_versions",
                                json={"keep_last_n": int(keep_n)},
                                timeout=10
                            )
                            if prune_response.status_code == 200:
                                st.success(f"✅ Pruned versions. Kept last {keep_n}.")
                                st.rerun()
                            else:
                                st.error("Failed to prune versions.")
                        except Exception as e:
                            st.error(f"Error pruning: {e}")
    else:
        st.info("📝 Upload a file and perform operations to see version history.")
    
    card_close()
    
    # Natural Language Query Input
    card_open("card-elevated")
    st.subheader("💬 Natural Language Query")
    st.caption("Describe the transformation you want. You can chain multiple steps in one sentence.")
    query = st.text_area(
        "Describe what you want to do with the data:",
        placeholder="e.g., Remove rows with missing values in the 'email' column, then sort by 'revenue' descending",
        height=100,
        key="nl_query_input"
    )
    st.caption("Try:")
    sug_a, sug_b, sug_c = st.columns(3)
    with sug_a:
        if st.button("Remove missing values", key="sug_missing"):
            st.session_state["nl_query_input"] = "Remove rows with missing values"
            st.rerun()
    with sug_b:
        if st.button("Sort by column descending", key="sug_sort"):
            st.session_state["nl_query_input"] = "Sort by revenue descending"
            st.rerun()
    with sug_c:
        if st.button("Group and aggregate", key="sug_group"):
            st.session_state["nl_query_input"] = "Group by department and calculate average salary"
            st.rerun()
    
    # Quick action chips
    st.markdown("**Quick actions**")
    chip1, chip2, chip3, chip4 = st.columns(4)
    with chip1:
        if st.button("Remove missing", key="quick_remove_missing"):
            st.session_state["nl_query_input"] = "Remove rows with missing values"
            st.rerun()
    with chip2:
        if st.button("Sort desc", key="quick_sort_desc"):
            st.session_state["nl_query_input"] = "Sort by revenue descending"
            st.rerun()
    with chip3:
        if st.button("Group avg", key="quick_group_avg"):
            st.session_state["nl_query_input"] = "Group by department and calculate average salary"
            st.rerun()
    with chip4:
        if st.button("Create column", key="quick_create_col"):
            st.session_state["nl_query_input"] = "Create a new column full_name by combining first_name and last_name"
            st.rerun()
    
    col1, col2 = st.columns([1, 4])
    with col1:
        execute_button = st.button("🚀 Execute Query", type="primary", width='stretch', help="Run the query and update the data version")
    
    # Operation History
    st.divider()
    st.subheader("📜 Operation History")
    
    col1, col2 = st.columns([4, 1])
    with col1:
        history_count = len(st.session_state.operation_history)
        st.caption(f"Total operations: {history_count}")
    with col2:
        clear_history_button = st.button("🗑️ Clear History", width='stretch', help="Clear operation history from this session")
    
    # Handle clear history
    if clear_history_button:
        st.session_state.operation_history = []
        st.success("✅ History cleared.")
        st.rerun()
    
    # Display operation history
    if st.session_state.operation_history:
        with st.expander("View Operation History", expanded=False):
            for idx, op in enumerate(reversed(st.session_state.operation_history[-10:]), 1):
                dt = datetime.fromtimestamp(op["timestamp"])
                version_id = op.get("version_id", "")
                version_text = f" [{version_id}]" if version_id else ""
                st.text(f"{idx}. [{dt.strftime('%H:%M:%S')}]{version_text} {op.get('description', op.get('operation', 'Unknown'))}")
    
    card_close()
    
    # Execute query
    if execute_button and query:
        if not OPENAI_API_KEY:
            st.error("❌ OPENAI_API_KEY environment variable is required for data manipulation.")
            st.info("Please set it with: `export OPENAI_API_KEY='your-key-here'`")
            return
        
        # Validate session still exists
        if not get_session_metadata_for_display(session_id):
            st.error(f"❌ Session '{session_id}' not found or expired. Please upload a new file.")
            return
        
        # Execute query
        with st.status("🤔 Processing your query...", expanded=True) as status:
            progress = st.progress(0)
            try:
                progress.progress(0.2, text="Sending query to analysis engine")
                result = analyze_data_sync(session_id, query)
                
                if result.get("success"):
                    # Wait a bit for MCP server to update Redis
                    time.sleep(2)  # Increased wait time for Redis update
                    progress.progress(0.7, text="Updating session state")
                    
                    # Verify the update was successful by checking if data changed
                    new_tables_data = get_session_tables_for_display(session_id)
                    if not new_tables_data:
                        st.warning("⚠️ Could not verify data update. Please refresh manually.")
                    
                    # Create new version after successful operation
                    try:
                        # Get current version from metadata
                        current_metadata = get_session_metadata_for_display(session_id)
                        current_vid = current_metadata.get("current_version", "v0") if current_metadata else "v0"
                        
                        # Get graph to determine next version number
                        graph_response = requests.get(f"{FASTAPI_URL}/api/session/{session_id}/versions", timeout=5)
                        if graph_response.status_code == 200:
                            graph_data = graph_response.json().get("graph", {"nodes": []})
                            # Generate new version ID
                            new_vid = f"v{len(graph_data.get('nodes', []))}"
                        else:
                            # Fallback: use UUID short
                            new_vid = f"v_{str(uuid.uuid4())[:8]}"
                        
                        # Extract operation description from query (first 50 chars)
                        operation_desc = query[:50] + "..." if len(query) > 50 else query
                        
                        # Save new version
                        save_version_response = requests.post(
                            f"{FASTAPI_URL}/api/session/{session_id}/save_version",
                            json={
                                "version_id": new_vid,
                                "operation": operation_desc,
                                "query": query
                            },
                            timeout=10
                        )
                        
                        if save_version_response.status_code == 200:
                            logger.info(f"Created version {new_vid} for session {session_id}")
                        else:
                            logger.warning(f"Failed to save version {new_vid}: {save_version_response.text}")
                    except Exception as e:
                        logger.error(f"Error creating version: {e}")
                        # Continue anyway - versioning failure shouldn't block the operation
                    
                    # Add to operation history with version ID
                    st.session_state.operation_history.append({
                        "timestamp": time.time(),
                        "operation": "QUERY",
                        "description": query,
                        "response": result.get("response", ""),
                        "version_id": new_vid if 'new_vid' in locals() else None
                    })
                    
                    progress.progress(1.0, text="Completed")
                    status.update(label="Operation completed", state="complete")
                    st.success("✅ Operation completed successfully!")
                    st.info("💡 Data has been updated. Scroll down to see the changes.")
                    
                    # Show response
                    response_text = result.get("response", "")
                    if response_text:
                        with st.expander("📝 Operation Details", expanded=True):
                            st.markdown(response_text)
                    
                    # Refresh the page to show updated data
                    st.rerun()
                else:
                    error_msg = result.get("error", "Unknown error occurred")
                    status.update(label="Operation failed", state="error")
                    st.error(f"❌ Operation failed: {error_msg}")
                    st.info("💡 You can try again with a different query.")
                    
            except Exception as e:
                status.update(label="Operation failed", state="error")
                st.error(f"❌ Unexpected error: {str(e)}")
                st.exception(e)
    
    st.divider()
    
    # Current Data Explorer
    st.subheader("📊 Current Data Explorer")
    if tables and selected_table:
        full_df = get_full_table_dataframe(session_id, selected_table)
        if full_df is not None and not full_df.empty:
            filtered_df = render_advanced_table(
                full_df,
                key_prefix=f"current_full_{selected_table}",
                height=320,
                page_size_default=10
            )
            
            # Download button
            export_df = filtered_df if filtered_df is not None else full_df
            csv = export_df.to_csv(index=False)
            st.download_button(
                label="📥 Download Current Data as CSV",
                data=csv,
                file_name=f"{selected_table}_current.csv",
                mime="text/csv"
            )
        else:
            st.info("Full table data not available.")


def _render_sidebar_session_block():
    """Render compact session block in sidebar when current_session_id is set."""
    session_id = st.session_state.get("current_session_id")
    if not session_id:
        return
    metadata = get_session_metadata_for_display(session_id)
    if not metadata:
        return
    file_name = metadata.get("file_name", "Current session")
    if isinstance(file_name, str) and len(file_name) > 24:
        file_name = file_name[:21] + "..."
    table_count = metadata.get("table_count", 0)
    created_at = metadata.get("created_at")
    last_modified = ""
    if created_at:
        try:
            if isinstance(created_at, (int, float)):
                from datetime import datetime
                last_modified = datetime.fromtimestamp(created_at).strftime("%b %d, %H:%M")
            else:
                last_modified = str(created_at)[:16]
        except Exception:
            pass
    st.subheader("📂 Current data")
    st.caption(file_name)
    st.caption(f"Tables: {table_count}" + (f" · {last_modified}" if last_modified else ""))
    col_switch, col_upload = st.columns(2)
    with col_switch:
        if st.button("Switch data", key="sidebar_switch_data", help="Clear session and choose another dataset"):
            cleanup_current_session()
            st.rerun()
    with col_upload:
        if st.button("Upload new", key="sidebar_upload_new", help="Clear session; use Upload tab to add new data"):
            cleanup_current_session()
            st.rerun()
    st.divider()


def main():
    """Main Streamlit application."""
    
    # Initialize session state
    initialize_session_state()

    # Apply theme and keyboard shortcuts
    apply_theme_script(_resolve_theme_choice(st.session_state.ui_theme))
    inject_keyboard_shortcuts()

    # Shortcut overlays driven by query params
    if "shortcuts" in st.query_params:
        with st.expander("⌨️ Keyboard Shortcuts", expanded=True):
            st.markdown("""
            **Global Shortcuts**
            - `?` → Toggle this panel
            - `Cmd/Ctrl + K` → Command palette (quick actions)
            - `Cmd/Ctrl + Enter` → Execute query (when focused)
            - `Esc` → Close dialogs/expanders
            """)
            if st.button("Close", key="close_shortcuts"):
                del st.query_params["shortcuts"]
                st.rerun()
    if "command_palette" in st.query_params:
        with st.expander("🧭 Command Palette", expanded=True):
            st.markdown("Quick actions to speed up your workflow.")
            cp1, cp2, cp3 = st.columns(3)
            with cp1:
                st.button("📤 Upload file", key="cp_upload")
            with cp2:
                st.button("🔧 Run transformation", key="cp_transform")
            with cp3:
                st.button("📈 Build chart", key="cp_chart")
            if st.button("Close", key="close_cp"):
                del st.query_params["command_palette"]
                st.rerun()
    
    # Accessibility: Skip link target
    st.markdown(
        '<a class="skip-link" href="#main-content" aria-label="Skip to main content">Skip to main content</a>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div id="main-content" class="content-fade-in" role="main" aria-label="Main content"></div>',
        unsafe_allow_html=True,
    )

    # Header
    st.markdown('<div class="main-header">📊 Data Analyst Platform</div>', unsafe_allow_html=True)
    st.markdown("Upload your data files and manipulate them with natural language queries!")
    
    # Sidebar
    with st.sidebar:
        st.header("⚙️ Settings")

        # Compact session block when data is loaded
        _render_sidebar_session_block()

        st.subheader("🎨 Theme")
        st.session_state.ui_theme = st.selectbox(
            "Choose theme",
            ["Auto", "Light", "Dark"],
            index=["Auto", "Light", "Dark"].index(st.session_state.ui_theme),
            help="Auto uses your system setting.",
            key="theme_select"
        )
        
        # API Health Check
        st.subheader("API Status")
        api_ok = check_api_health()
        if api_ok:
            st.session_state["last_api_ok"] = True
            st.success("✅ FastAPI server is running")
            st.markdown('<span class="status-badge">Online</span>', unsafe_allow_html=True)
        else:
            # If the health check fails transiently, keep the app usable.
            was_ok = st.session_state.get("last_api_ok", False)
            if was_ok:
                st.warning("⚠️ FastAPI health check failed (temporary).")
            else:
                st.error("❌ FastAPI server is not running")
            st.markdown('<span class="status-badge">Offline</span>', unsafe_allow_html=True)
            st.warning("Please start the FastAPI server:\n```bash\npython main.py\n```")
        
        # MCP Server Status
        st.subheader("MCP Server Status")
        if OPENAI_API_KEY:
            st.success("✅ OpenAI API key configured")
            st.caption("Key detected and ready for queries.")
        else:
            st.warning("⚠️ OPENAI_API_KEY not set")
            st.caption("Required for Data Manipulation tab")
        
        # API Configuration
        config = get_api_config()
        if config:
            st.subheader("📋 Configuration")
            st.info(f"Max file size: {config.get('max_file_size_mb', 'N/A')} MB")
            st.info(f"Max tables per file: {config.get('max_tables_per_file', 'N/A')}")
            
            supported = config.get('supported_formats', {})
            if supported:
                st.write("**Supported formats:**")
                for fmt, exts in supported.items():
                    st.write(f"- {fmt.upper()}: {', '.join(exts)}")

        st.subheader("🚀 Onboarding")
        if st.toggle("Show onboarding tips", value=st.session_state.show_onboarding, key="onboarding_toggle"):
            st.session_state.show_onboarding = True
        else:
            st.session_state.show_onboarding = False
        
        st.divider()
        st.caption("Made with ❤️ for data analysts")
    
    # Main content area with tabs
    tab1, tab2, tab3, tab4 = st.tabs(["📤 Upload", "🔧 Data Manipulation", "📈 Visualization Centre", "💬 Chatbot"])
    
    with tab1:
        render_upload_tab()
    
    with tab2:
        render_manipulation_tab()
    
    with tab3:
        render_visualization_tab()
    
    with tab4:
        render_chatbot_tab()


if __name__ == "__main__":
    main()

