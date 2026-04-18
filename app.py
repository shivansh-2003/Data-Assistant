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
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env", override=False)

import asyncio
import time
import uuid
import logging
import graphviz
import base64
import pickle
from datetime import datetime
from log_setup import setup_logging
setup_logging()

from data_visualization import render_visualization_tab
from data_visualization.cache_invalidation import on_data_changed
from chatbot.streamlit_ui import render_chatbot_tab
from components.data_table import render_advanced_table
from components.empty_state import render_empty_state
from observability.langfuse_client import update_trace_context

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Per-operation latency ceilings (seconds).  Exceeded → WARNING in logs.
# ---------------------------------------------------------------------------
_BENCHMARKS: dict[str, float] = {
    "app.analyze_data_sync":        15.0,
    "app.analyze_data_sync.llm":    12.0,
    "app.post_op.cache_clear":       0.05,
    "app.post_op.save_version_http": 1.50,
    "app.branch_http":               1.00,
}


def _perf_warn(name: str, elapsed: float, session_id: str = "") -> None:
    """Emit a SLOW warning if elapsed exceeds the benchmark ceiling."""
    threshold = _BENCHMARKS.get(name)
    if threshold and elapsed > threshold:
        logger.warning(
            "[PERF][SLOW] %-40s  session=%s  %.3fs elapsed  (benchmark: %.3fs  |  %.1fx over)",
            name, session_id, elapsed, threshold, elapsed / threshold,
        )

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

# FastAPI endpoint configuration (use 127.0.0.1 for client requests — 0.0.0.0 is invalid as a destination)
# Must match the port where uvicorn runs (see main.py PORT, default 8000).
# FASTAPI_URL = os.getenv("FASTAPI_URL", "https://data-assistant-hj5f.onrender.com")
FASTAPI_URL = os.getenv("FASTAPI_URL", "http://127.0.0.1:8000").rstrip("/")
HTTP_TIMEOUT = int(os.getenv("HTTP_CLIENT_TIMEOUT", "30"))
HTTP_TIMEOUT_LONG = int(os.getenv("HTTP_CLIENT_TIMEOUT_LONG", "120"))
# PERF_LOG=1: logs analyze_data_sync and post-op (cache clear + save_version) timings.
# Manual Tier-1 checks: (1) Execute a manipulation query — watch logs; (2) Branch to an older
# version — session restores, no duplicate version ids; (3) Prune if available — rerun graph,
# confirm next version id matches node count.
PERF_LOG = os.getenv("PERF_LOG", "").lower() in ("1", "true", "yes")
UPLOAD_ENDPOINT = f"{FASTAPI_URL}/api/ingestion/file-upload"
HEALTH_ENDPOINT = f"{FASTAPI_URL}/health"
CONFIG_ENDPOINT = f"{FASTAPI_URL}/api/ingestion/config"
SESSION_ENDPOINT = f"{FASTAPI_URL}/api/session"

# MCP Configuration
# MCP_SERVER_URL = "https://data-assistant-hj5f.onrender.com/data/mcp"
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", f"{FASTAPI_URL}/data/mcp")
OPENAI_API_KEY = get_secret("openai.api_key", "OPENAI_API_KEY")
OPENAI_MODEL = get_secret("openai.model", "OPENAI_MODEL", "gpt-4o")

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
    .hero-section {
        background: linear-gradient(135deg, var(--glass-bg) 0%, var(--primary-50) 100%);
        border: 1px solid var(--glass-border);
        border-radius: var(--radius-lg);
        padding: 1.5rem 1.5rem 1.25rem;
        margin-bottom: 1rem;
        box-shadow: var(--shadow-sm);
    }
    .skeleton {
        background: linear-gradient(90deg, var(--border) 25%, var(--card-bg) 50%, var(--border) 75%);
        background-size: 200% 100%;
        animation: skeletonShine 1.2s ease-in-out infinite;
        border-radius: var(--radius-sm);
    }
    @keyframes skeletonShine {
        0% { background-position: 200% 0; }
        100% { background-position: -200% 0; }
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
    /* Respect user motion preference */
    @media (prefers-reduced-motion: reduce) {
        *, *::before, *::after {
            animation-duration: 0.01ms !important;
            animation-iteration-count: 1 !important;
            transition-duration: 0.01ms !important;
        }
    }
    </style>
""", unsafe_allow_html=True)


def card_open(class_name: str = "card-elevated", aria_label: str | None = None):
    """Render opening div for a card wrapper. Call card_close() after content."""
    attr = f' aria-label="{aria_label}"' if aria_label else ""
    st.markdown(f'<div class="{class_name}" role="region"{attr}>', unsafe_allow_html=True)


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

    Benchmark target: < 15 s end-to-end (LLM is ~3-12 s; non-LLM overhead
    should be < 2 s).  Set PERF_LOG=1 to activate threshold warnings.

    Args:
        session_id: Session ID containing the data in Redis
        query: Natural language query describing what to do with the data

    Returns:
        Dict with 'success', 'response', and optional 'error' keys
    """
    import time as _t

    t0 = _t.perf_counter()
    logger.info(
        "[PERF] app.analyze_data_sync START  session=%s  query_len=%d",
        session_id, len(query),
    )
    try:
        # Import here to avoid issues if mcp_client not available
        from mcp_client import analyze_data

        # Run async function in sync context
        response = asyncio.run(analyze_data(session_id, query))
        elapsed = _t.perf_counter() - t0
        logger.info(
            "[PERF] app.analyze_data_sync END  session=%s  duration=%.3fs  status=success",
            session_id, elapsed,
        )
        _perf_warn("app.analyze_data_sync", elapsed, session_id)
        return {"success": True, "response": response}
    except Exception as e:
        elapsed = _t.perf_counter() - t0
        logger.error(
            "[PERF] app.analyze_data_sync END  session=%s  duration=%.3fs  status=error  error=%s",
            session_id, elapsed, type(e).__name__,
        )
        logger.debug("analyze_data_sync traceback:", exc_info=True)
        return {"success": False, "error": str(e)}


@st.cache_data(ttl=30, show_spinner=False)
def get_session_tables_for_display(session_id: str) -> Optional[Dict]:
    """
    Fetch current tables from session for display.
    Cached for 30s so the sidebar and manipulation tab don't hit the API
    on every Streamlit rerender.
    """
    try:
        response = requests.get(
            f"{SESSION_ENDPOINT}/{session_id}/tables",
            params={"format": "summary"},
            timeout=HTTP_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return None


@st.cache_data(ttl=30, show_spinner=False)
def get_session_metadata_for_display(session_id: str) -> Optional[Dict]:
    """
    Fetch session metadata.
    Cached for 30s — the sidebar calls this on every page render, so without
    caching it would add a round-trip to Render.com on every widget interaction.
    """
    try:
        response = requests.get(
            f"{SESSION_ENDPOINT}/{session_id}/metadata",
            timeout=HTTP_TIMEOUT,
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
            timeout=HTTP_TIMEOUT,
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
    card_open("card-elevated hero-section")
    st.markdown('<p class="section-subtitle" style="margin-top:0;">Upload Your Data</p>', unsafe_allow_html=True)
    st.markdown('<h1 class="main-header">📤 Upload Your Data</h1>', unsafe_allow_html=True)
    st.markdown('<p class="section-subtitle">Drag & drop or click to upload. We will extract tables and prepare them for analysis.</p>', unsafe_allow_html=True)

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
    session_id = st.text_input("Session ID (Optional)", help="Optional session identifier for tracking")
    upload_button = False
    if uploaded_file is not None:
        col1, col2 = st.columns([1, 4])
        with col1:
            upload_button = st.button(
                "🚀 Upload & Process",
                type="primary",
                help="Upload the file and extract tables for analysis"
            )
    card_close()
    
    # Detect file clear/removal - cleanup Redis
    current_file_id = uploaded_file.file_id if uploaded_file else None
    if st.session_state.last_file_id and current_file_id != st.session_state.last_file_id:
        # File was removed or changed - cleanup old session
        cleanup_current_session()
        st.session_state.last_ingestion_result = None
        st.session_state.last_ingestion_file_id = None
    st.session_state.last_file_id = current_file_id
    
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
    elif uploaded_file is None:
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



@st.cache_data(ttl=15, show_spinner=False)
def _fetch_version_graph(session_id: str) -> dict:
    """Cached fetch of the version history graph. TTL=15s for near-realtime feel."""
    response = requests.get(
        f"{FASTAPI_URL}/api/session/{session_id}/versions", timeout=5
    )
    response.raise_for_status()
    return response.json().get("graph", {"nodes": [], "edges": []})


def render_manipulation_tab():
    """Render the Data Manipulation tab content."""
    st.markdown("## 🔧 Data Manipulation")

    session_id = st.session_state.get("current_session_id")

    # ── Guard: no session ────────────────────────────────────────────────────
    if not session_id:
        render_empty_state(
            title="No data loaded yet",
            message="Upload a file in the Upload tab first.",
            primary_action_label="Go to Upload",
            primary_action_key="empty_manipulation_upload",
            icon="🔧",
        )
        return

    # ── Load metadata ────────────────────────────────────────────────────────
    metadata = get_session_metadata_for_display(session_id)
    if not metadata:
        st.error(f"❌ Session '{session_id}' not found or expired. Please upload a new file.")
        st.session_state.current_session_id = None
        if "sid" in st.query_params:
            del st.query_params["sid"]
        return

    # Extend TTL once per minute (no HTTP on every widget interaction)
    _extend_key = f"_last_extend_{session_id}"
    if time.time() - st.session_state.get(_extend_key, 0) > 60:
        try:
            requests.post(f"{SESSION_ENDPOINT}/{session_id}/extend", timeout=5)
        except Exception:
            pass
        st.session_state[_extend_key] = time.time()

    # ── Load tables ──────────────────────────────────────────────────────────
    tables_data = get_session_tables_for_display(session_id)
    if not tables_data:
        st.error("❌ Could not load tables from session.")
        return
    tables = tables_data.get("tables", {})
    table_names = list(tables.keys())

    # ── STATUS BAR — one compact line replacing two full cards ───────────────
    file_name    = metadata.get("file_name", "Unknown")
    current_ver  = metadata.get("current_version", "v0")

    sb_left, sb_mid, sb_right = st.columns([4, 3, 3])
    with sb_left:
        st.markdown(
            f"**📄 {file_name}** &nbsp;·&nbsp; `{current_ver}`",
            help=f"Session: {session_id}",
        )
    with sb_mid:
        if len(table_names) == 1:
            selected_table = table_names[0]
            tinfo = tables[selected_table]
            st.caption(
                f"{tinfo.get('row_count', 0):,} rows · {tinfo.get('column_count', 0)} cols"
            )
        else:
            selected_table = st.selectbox(
                "Table",
                table_names,
                key="selected_table_manipulation",
                label_visibility="collapsed",
            )
    with sb_right:
        if len(table_names) > 1 and selected_table:
            tinfo = tables.get(selected_table, {})
            st.caption(
                f"{tinfo.get('row_count', 0):,} rows · {tinfo.get('column_count', 0)} cols"
            )
    # ensure selected_table is always set even for single-table sessions
    if len(table_names) == 1:
        selected_table = table_names[0]

    st.divider()
    
    # ── Version History ──────────────────────────────────────────────────────
    card_open("card-elevated", aria_label="Version history")
    st.subheader("📜 Version History")

    # ── helper: one-shot branch call (shared by all branch buttons) ──────────
    def _do_branch(target_vid: str) -> None:
        _tb0 = time.perf_counter()
        logger.info(
            "[PERF] app.branch_http START  session=%s  target_version=%s",
            session_id, target_vid,
        )
        try:
            r = requests.post(
                f"{FASTAPI_URL}/api/session/{session_id}/branch",
                json={"version_id": target_vid},
                timeout=HTTP_TIMEOUT_LONG,
            )
            _tb = time.perf_counter() - _tb0
            logger.info(
                "[PERF] app.branch_http END  session=%s  target_version=%s  "
                "status=%d  duration=%.3fs",
                session_id, target_vid, r.status_code, _tb,
            )
            _benchmark_warn("app.branch_http", _tb, session_id)
            if r.status_code == 200:
                get_full_table_dataframe.clear()
                get_session_tables_for_display.clear()
                get_session_metadata_for_display.clear()
                _fetch_version_graph.clear()
                st.toast(f"✅ Switched to {target_vid}", icon="🌿")
                st.rerun()
            else:
                st.error(f"Branch failed (HTTP {r.status_code})")
        except Exception as exc:
            st.error(f"Error switching version: {exc}")

    def _normalize_graph(graph: Dict, current_version: str, search_text: str, keep_last_n: int) -> Dict:
        nodes = graph.get("nodes", [])
        edges = graph.get("edges", [])
        nodes_sorted = sorted(nodes, key=lambda n: n.get("timestamp", 0), reverse=True)
        if keep_last_n:
            nodes_sorted = nodes_sorted[:keep_last_n]
        if search_text:
            sl = search_text.lower()
            nodes_sorted = [
                n for n in nodes_sorted
                if sl in (n.get("operation", "") or n.get("label", "")).lower()
                or sl in (n.get("query", "") or "").lower()
                or sl in n.get("id", "").lower()
            ]
        node_ids = {n.get("id") for n in nodes_sorted}
        edges_filtered = [e for e in edges if e.get("from") in node_ids and e.get("to") in node_ids]
        return {"nodes": nodes_sorted, "edges": edges_filtered}

    try:
        graph_data = _fetch_version_graph(session_id)
    except Exception:
        graph_data = {"nodes": [], "edges": []}

    # Keep node count in session_state so execute-query can derive next vid cheaply
    st.session_state[f"_version_graph_node_count_{session_id}"] = len(graph_data.get("nodes", []))

    current_version = metadata.get("current_version", "v0")
    nodes_all = graph_data.get("nodes", [])

    if not nodes_all:
        st.info("No versions yet. Run a query above to create the first snapshot.")
    else:
        # ── TOP BAR: quick-switch + search ───────────────────────────────────
        qs_col, srch_col, n_col = st.columns([3, 3, 2])
        with qs_col:
            # Build options sorted newest-first; current version shown as default
            sorted_nodes = sorted(nodes_all, key=lambda n: n.get("timestamp", 0), reverse=True)
            qs_options = [n["id"] for n in sorted_nodes]

            def _qs_label(vid: str) -> str:
                node = next((n for n in sorted_nodes if n["id"] == vid), {})
                op = (node.get("operation") or node.get("label", ""))[:35]
                ts = node.get("timestamp")
                ts_str = datetime.fromtimestamp(ts).strftime("%H:%M") if ts else ""
                suffix = " ← current" if vid == current_version else ""
                return f"{vid}  {ts_str}  {op}{suffix}"

            default_idx = qs_options.index(current_version) if current_version in qs_options else 0
            quick_pick = st.selectbox(
                "⚡ Jump to version",
                options=qs_options,
                index=default_idx,
                format_func=_qs_label,
                key="vh_quick_pick",
                help="Pick any version and click Switch — no confirmation needed.",
            )
        with srch_col:
            search_text = st.text_input(
                "🔍 Filter list",
                placeholder="operation, query keyword, version id…",
                key="vh_search",
                label_visibility="visible",
            )
        with n_col:
            keep_last_n = st.number_input(
                "Show last N",
                min_value=1,
                max_value=500,
                value=min(50, len(nodes_all)),
                key="vh_keep_n",
                help="Limit rows shown in the list below.",
            )

        # One-click Switch button for the quick-pick selection
        sw_col, info_col = st.columns([2, 5])
        with sw_col:
            if quick_pick == current_version:
                st.button(
                    "✅ Already here",
                    key="vh_qs_switch",
                    disabled=True,
                    use_container_width=True,
                )
            else:
                if st.button(
                    f"🌿 Switch to {quick_pick}",
                    key="vh_qs_switch",
                    type="primary",
                    use_container_width=True,
                    help="Instantly switch the active session to this version.",
                ):
                    with st.spinner(f"Switching to {quick_pick}…"):
                        _do_branch(quick_pick)
        with info_col:
            picked_node = next((n for n in nodes_all if n["id"] == quick_pick), {})
            if picked_node:
                op = picked_node.get("operation") or picked_node.get("label", "")
                q  = picked_node.get("query", "")
                ts = picked_node.get("timestamp")
                ts_str = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S") if ts else "—"
                st.markdown(
                    f"**{quick_pick}** &nbsp;·&nbsp; {ts_str}  \n"
                    f"*{op}*" + (f"  \n`{q[:120]}`" if q else ""),
                    help="Details of the selected version.",
                )

        st.divider()

        # ── VERSION LIST — one row per version, instant Switch button ────────
        graph_data = _normalize_graph(graph_data, current_version, search_text, keep_last_n)
        nodes_filtered = graph_data.get("nodes", [])

        if not nodes_filtered:
            st.caption("No versions match the current filter.")
        else:
            # Column header
            hc1, hc2, hc3, hc4 = st.columns([1.5, 1.5, 4, 1.5])
            hc1.markdown("**Version**")
            hc2.markdown("**Time**")
            hc3.markdown("**Operation**")
            hc4.markdown("**Action**")

            for node in nodes_filtered:
                vid      = node.get("id", "?")
                op       = (node.get("operation") or node.get("label", "—"))
                q        = node.get("query", "")
                ts       = node.get("timestamp")
                ts_str   = datetime.fromtimestamp(ts).strftime("%H:%M:%S") if ts else "—"
                is_curr  = vid == current_version

                rc1, rc2, rc3, rc4 = st.columns([1.5, 1.5, 4, 1.5])

                with rc1:
                    if is_curr:
                        st.markdown(f"🟢 **{vid}**", help="This is the currently active version.")
                    else:
                        st.markdown(f"⚪ {vid}")

                with rc2:
                    st.caption(ts_str)

                with rc3:
                    display_op = op[:70] + ("…" if len(op) > 70 else "")
                    if q:
                        st.markdown(
                            f"{display_op}",
                            help=f"Query: {q}",
                        )
                    else:
                        st.markdown(display_op)

                with rc4:
                    if is_curr:
                        st.caption("current")
                    else:
                        if st.button(
                            "🌿 Switch",
                            key=f"vh_switch_{vid}",
                            type="secondary",
                            use_container_width=True,
                            help=f"Switch active session to {vid}",
                        ):
                            with st.spinner(f"Switching to {vid}…"):
                                _do_branch(vid)

        # ── Graphviz DAG (collapsible, for visual reference) ─────────────────
        st.divider()
        with st.expander("🔀 Show DAG / lineage graph", expanded=False):
            dot = graphviz.Digraph(comment="Version History")
            dot.attr(rankdir="LR")
            dot.attr("node", shape="box", style="rounded,filled", fillcolor="lightblue")
            for node in graph_data.get("nodes", []):
                vid   = node.get("id", "?")
                op    = (node.get("operation") or node.get("label", ""))[:30]
                ts    = node.get("timestamp")
                ts_s  = datetime.fromtimestamp(ts).strftime("%H:%M") if ts else ""
                label = f"{vid}\n{op}\n{ts_s}".strip()
                fill  = "lightgreen" if vid == current_version else "lightblue"
                dot.node(vid, label, fillcolor=fill)
            for edge in graph_data.get("edges", []):
                dot.edge(edge["from"], edge["to"], label=edge.get("label", ""))
            st.graphviz_chart(dot.source)

        # ── Prune (collapsible) ───────────────────────────────────────────────
        with st.expander("🗑️ Prune old versions", expanded=False):
            col1, col2 = st.columns([2, 1])
            with col1:
                keep_n = st.number_input(
                    "Keep last N versions",
                    min_value=1,
                    max_value=100,
                    value=len(nodes_all),
                    help="Delete old versions, keeping only the most recent N.",
                    key="vh_prune_n",
                )
            with col2:
                prune_button = st.button(
                    "Prune",
                    type="secondary",
                    help="Remove old versions.",
                    key="vh_prune_btn",
                )
            if prune_button:
                with st.spinner("Pruning versions..."):
                    try:
                        prune_response = requests.post(
                            f"{FASTAPI_URL}/api/session/{session_id}/prune_versions",
                            json={"keep_last_n": int(keep_n)},
                            timeout=HTTP_TIMEOUT_LONG,
                        )
                        if prune_response.status_code == 200:
                            st.success(f"✅ Pruned versions. Kept last {keep_n}.")
                            _fetch_version_graph.clear()
                            st.rerun()
                        else:
                            st.error("Failed to prune versions.")
                    except Exception as e:
                        st.error(f"Error pruning: {e}")

    card_close()
    
    # Natural Language Query Input
    # ── QUERY INPUT ──────────────────────────────────────────────────────────
    query = st.text_area(
        "💬 Describe your transformation",
        placeholder='e.g. "Filter rows where age > 18 and sort by revenue descending"',
        height=90,
        key="nl_query_input",
        label_visibility="visible",
    )

    # Four compact example chips in one row
    c1, c2, c3, c4 = st.columns(4)
    _chips = [
        ("Remove missing",  "Remove rows with missing values"),
        ("Sort descending", "Sort by revenue descending"),
        ("Group & average", "Group by department and calculate average salary"),
        ("Create column",   "Create a new column full_name by combining first_name and last_name"),
    ]
    for col, (label, val) in zip([c1, c2, c3, c4], _chips):
        with col:
            if st.button(label, key=f"chip_{label}", use_container_width=True):
                st.session_state["nl_query_input"] = val
                st.rerun()

    execute_button = st.button(
        "🚀 Execute",
        type="primary",
        use_container_width=True,
        help="Run the query and snapshot a new version",
    )

    st.divider()
    
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

                # ── PERF: LLM + MCP tool calls ──────────────────────────
                _t_llm_start = time.perf_counter()
                logger.info(
                    "[PERF] app.analyze_data_sync START  session=%s  query_len=%d",
                    session_id, len(query),
                )
                result = analyze_data_sync(session_id, query)
                _t_llm = time.perf_counter() - _t_llm_start
                logger.info(
                    "[PERF] app.analyze_data_sync END  session=%s  duration=%.3fs  status=%s",
                    session_id, _t_llm,
                    "success" if result.get("success") else "error",
                )
                _benchmark_warn("app.analyze_data_sync", _t_llm, session_id)
                # ────────────────────────────────────────────────────────

                if result.get("success"):
                    progress.progress(0.7, text="Updating session state")

                    # ── PERF: cache invalidation (should be ~0 ms) ───────
                    _t_cache_start = time.perf_counter()
                    on_data_changed()
                    get_session_tables_for_display.clear()
                    get_full_table_dataframe.clear()
                    _t_cache = time.perf_counter() - _t_cache_start
                    logger.info(
                        "[PERF] app.post_op.cache_clear  session=%s  duration=%.3fs",
                        session_id, _t_cache,
                    )
                    _benchmark_warn("app.post_op.cache_clear", _t_cache, session_id)
                    # ────────────────────────────────────────────────────

                    try:
                        _vkey = f"_version_graph_node_count_{session_id}"
                        _n = int(st.session_state.get(_vkey, 0))
                        new_vid = f"v{_n}"

                        operation_desc = query[:50] + "..." if len(query) > 50 else query

                        # ── PERF: save_version HTTP POST ─────────────────
                        _t_sv_start = time.perf_counter()
                        logger.info(
                            "[PERF] app.post_op.save_version_http START  session=%s  version=%s",
                            session_id, new_vid,
                        )
                        save_version_response = requests.post(
                            f"{FASTAPI_URL}/api/session/{session_id}/save_version",
                            json={
                                "version_id": new_vid,
                                "operation": operation_desc,
                                "query": query
                            },
                            timeout=HTTP_TIMEOUT_LONG,
                        )
                        _t_sv = time.perf_counter() - _t_sv_start
                        logger.info(
                            "[PERF] app.post_op.save_version_http END  session=%s  version=%s  "
                            "status=%d  duration=%.3fs",
                            session_id, new_vid, save_version_response.status_code, _t_sv,
                        )
                        _benchmark_warn("app.post_op.save_version_http", _t_sv, session_id)
                        # ────────────────────────────────────────────────

                        if save_version_response.status_code == 200:
                            logger.info(f"Created version {new_vid} for session {session_id}")
                            st.session_state[_vkey] = _n + 1
                            _fetch_version_graph.clear()
                            get_session_metadata_for_display.clear()
                        else:
                            logger.warning(f"Failed to save version {new_vid}: {save_version_response.text}")
                    except Exception as e:
                        logger.error(f"Error creating version: {e}")

                    # ── PERF: full operation wall-clock summary ───────────
                    _t_total = time.perf_counter() - _t_llm_start
                    logger.info(
                        "[PERF] app.execute_query TOTAL  session=%s  "
                        "llm=%.3fs  cache=%.3fs  save_version=%.3fs  wall=%.3fs",
                        session_id, _t_llm, _t_cache,
                        time.perf_counter() - _t_sv_start if '_t_sv_start' in dir() else 0.0,
                        _t_total,
                    )
                    # ────────────────────────────────────────────────────

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
    
    # ── DATA EXPLORER ────────────────────────────────────────────────────────
    st.subheader("📊 Data")
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
    st.markdown('<div class="card" role="region" aria-label="Current data session">', unsafe_allow_html=True)
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
    st.markdown("</div>", unsafe_allow_html=True)
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

        st.markdown('<div class="card" role="region" aria-label="Theme settings">', unsafe_allow_html=True)
        st.subheader("🎨 Theme")
        st.session_state.ui_theme = st.selectbox(
            "Choose theme",
            ["Auto", "Light", "Dark"],
            index=["Auto", "Light", "Dark"].index(st.session_state.ui_theme),
            help="Auto uses your system setting.",
            key="theme_select"
        )
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown('<div class="card" role="region" aria-label="API status">', unsafe_allow_html=True)
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
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown('<div class="card" role="region" aria-label="MCP server status">', unsafe_allow_html=True)
        st.subheader("MCP Server Status")
        if OPENAI_API_KEY:
            st.success("✅ OpenAI API key configured")
            st.caption("Key detected and ready for queries.")
        else:
            st.warning("⚠️ OPENAI_API_KEY not set")
            st.caption("Required for Data Manipulation tab")
        st.markdown("</div>", unsafe_allow_html=True)

        # API Configuration
        config = get_api_config()
        if config:
            st.markdown('<div class="card" role="region" aria-label="API configuration">', unsafe_allow_html=True)
            st.subheader("📋 Configuration")
            st.info(f"Max file size: {config.get('max_file_size_mb', 'N/A')} MB")
            st.info(f"Max tables per file: {config.get('max_tables_per_file', 'N/A')}")
            supported = config.get('supported_formats', {})
            if supported:
                st.write("**Supported formats:**")
                for fmt, exts in supported.items():
                    st.write(f"- {fmt.upper()}: {', '.join(exts)}")
            st.markdown("</div>", unsafe_allow_html=True)

        st.markdown('<div class="card" role="region" aria-label="Onboarding">', unsafe_allow_html=True)
        st.subheader("🚀 Onboarding")
        if st.toggle("Show onboarding tips", value=st.session_state.show_onboarding, key="onboarding_toggle"):
            st.session_state.show_onboarding = True
        else:
            st.session_state.show_onboarding = False
        st.markdown("</div>", unsafe_allow_html=True)
        
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

