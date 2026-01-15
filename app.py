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
from datetime import datetime
from data_visualization import render_visualization_tab
from chatbot.streamlit_ui import render_chatbot_tab

logger = logging.getLogger(__name__)

# FastAPI endpoint configuration
FASTAPI_URL = "http://0.0.0.0:8001"
UPLOAD_ENDPOINT = f"{FASTAPI_URL}/api/ingestion/file-upload"
HEALTH_ENDPOINT = f"{FASTAPI_URL}/health"
CONFIG_ENDPOINT = f"{FASTAPI_URL}/api/ingestion/config"
SESSION_ENDPOINT = f"{FASTAPI_URL}/api/session"

# MCP Configuration
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://127.0.0.1:8000")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")  # Fallback to gpt-4o if gpt-5.1 not available

# Page configuration
st.set_page_config(
    page_title="Data Analyst Platform",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
    <style>
    :root {
        --primary: #1f77b4;
        --primary-600: #18639b;
        --primary-50: #e9f2fb;
        --accent: #ff7f0e;
        --success: #22c55e;
        --warning: #f59e0b;
        --error: #ef4444;
        --text: #111827;
        --muted: #6b7280;
        --border: #e5e7eb;
        --card-bg: #ffffff;
        --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.06);
        --shadow-md: 0 8px 20px rgba(0, 0, 0, 0.08);
        --radius-sm: 8px;
        --radius-md: 12px;
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
        font-size: 2.4rem;
        font-weight: 700;
        color: var(--primary);
        margin-bottom: 0.5rem;
        letter-spacing: -0.5px;
    }
    .section-title {
        font-size: 1.25rem;
        font-weight: 600;
        margin: 0.5rem 0 0.75rem 0;
        color: var(--text);
    }
    .section-subtitle {
        color: var(--muted);
        font-size: 0.95rem;
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
    }
    .card {
        background: var(--card-bg);
        border: 1px solid var(--border);
        border-radius: var(--radius-md);
        padding: 16px;
        box-shadow: var(--shadow-sm);
    }

    /* Streamlit component styling */
    .stButton > button {
        border-radius: 10px;
        font-weight: 600;
        transition: all 120ms ease-in-out;
    }
    .stButton > button:focus {
        outline: 2px solid var(--primary);
        outline-offset: 2px;
    }
    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: var(--shadow-sm);
    }
    div[data-testid="stMetric"] {
        background: var(--card-bg);
        border: 1px solid var(--border);
        border-radius: var(--radius-sm);
        padding: 10px 12px;
        box-shadow: var(--shadow-sm);
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

    /* Responsive adjustments */
    @media (max-width: 768px) {
        .main-header {
            font-size: 1.8rem;
        }
        div[data-testid="stMetric"] {
            padding: 8px 10px;
        }
        .stButton > button {
            width: 100%;
        }
        div[data-testid="stHorizontalBlock"] {
            flex-direction: column;
            gap: 0.75rem;
        }
    }
    </style>
""", unsafe_allow_html=True)


def check_api_health() -> bool:
    """Check if FastAPI server is running."""
    try:
        response = requests.get(HEALTH_ENDPOINT, timeout=2)
        return response.status_code == 200
    except:
        return False


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




def display_table_info(table_info: Dict, table_index: int):
    """Display information about a single table."""
    st.subheader(f"📋 Table {table_index + 1}")
    
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
    
    # Display preview data
    if table_info.get('preview'):
        st.subheader("👀 Data Preview (First 10 rows)")
        preview_df = pd.DataFrame(table_info['preview'])
        st.dataframe(preview_df, width='stretch', height=400)
        
        # Download button for full data
        csv = preview_df.to_csv(index=False)
        st.download_button(
            label=f"📥 Download Table {table_index + 1} as CSV",
            data=csv,
            file_name=f"table_{table_index + 1}.csv",
            mime="text/csv",
            key=f"download_{table_index}"
        )


def render_ingestion_result(result: Dict, session_id_input: Optional[str] = None):
    """Render ingestion results for file, URL, or Supabase imports."""
    if result.get("success"):
        save_session_id(result.get("session_id"))
        st.success("✅ File processed successfully!")
        
        metadata = result.get("metadata", {})
        st.markdown("---")
        st.header("📈 Processing Results")
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("File Type", metadata.get("file_type", "unknown").upper())
        with col2:
            st.metric("Tables Found", metadata.get("table_count", 0))
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
            st.header(f"📊 Extracted Tables ({len(tables)})")
            
            if len(tables) > 1:
                tab_names = [f"Table {i+1}" for i in range(len(tables))]
                tabs = st.tabs(tab_names)
                
                for idx, tab in enumerate(tabs):
                    with tab:
                        display_table_info(tables[idx], idx)
            else:
                display_table_info(tables[0], 0)
        else:
            st.warning("No tables found in the uploaded file.")
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
    
    # Operation history
    if "operation_history" not in st.session_state:
        st.session_state.operation_history = []


def render_upload_tab():
    """Render the Upload tab content."""
    st.header("📤 Upload File")
    st.caption("Upload a file to start exploring your data. We will extract tables and prepare them for analysis.")
    
    # Quick steps
    step1, step2, step3 = st.columns(3)
    with step1:
        st.markdown("**1. Upload**")
        st.caption("CSV, Excel, PDF, or image files")
    with step2:
        st.markdown("**2. Process**")
        st.caption("We extract tables and metadata")
    with step3:
        st.markdown("**3. Explore**")
        st.caption("Visualize and query your data")
    
    # File uploader
    uploaded_file = st.file_uploader(
        "Choose a file to upload",
        type=['csv', 'xlsx', 'xls', 'pdf', 'png', 'jpg', 'jpeg', 'tiff', 'bmp'],
        help="Supported formats: CSV, Excel, PDF, Images"
    )
    st.caption("Tip: For large files, prefer CSV or Excel for faster processing.")
    
    # Detect file clear/removal - cleanup Redis
    current_file_id = uploaded_file.file_id if uploaded_file else None
    if st.session_state.last_file_id and current_file_id != st.session_state.last_file_id:
        # File was removed or changed - cleanup old session
        cleanup_current_session()
    st.session_state.last_file_id = current_file_id
    
    # Optional file type hint
    file_type_hint = st.selectbox(
        "File Type (Optional - Auto-detected if not specified)",
        ["Auto-detect", "csv", "excel", "pdf", "image"],
        help="Manually specify file type if auto-detection fails"
    )
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
            with st.spinner("Uploading and processing file..."):
                # Upload file
                result = upload_file(uploaded_file, file_type, session_id if session_id else None)
                
                render_ingestion_result(result, session_id_input=session_id)
    
    else:
        # No file uploaded - cleanup any existing session
        cleanup_current_session()
        
        # Show instructions when no file is uploaded
        st.info("👆 Please upload a file to get started")
        
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
            - **PDF**: Multi-page PDFs with tables (requires Docling)
            - **Images**: PNG, JPEG, TIFF, BMP with tables (requires Docling)
            
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
            help="Paste a direct link to a CSV, Excel, PDF, or image file"
        )
        url_file_type_hint = st.selectbox(
            "File Type (Optional - Auto-detected if not specified)",
            ["Auto-detect", "csv", "excel", "pdf", "image"],
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
                with st.spinner("Downloading and processing URL..."):
                    result = upload_url(url_input, url_file_type, url_session_id if url_session_id else None)
                    render_ingestion_result(result, session_id_input=url_session_id)

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
                with st.spinner("Connecting to Supabase and importing tables..."):
                    result = upload_supabase(
                        connection_string=connection_string,
                        schema=schema_name or "public",
                        session_id=supabase_session_id if supabase_session_id else None,
                        project_name=project_name or None
                    )
                    render_ingestion_result(result, session_id_input=supabase_session_id)


def render_manipulation_tab():
    """Render the Data Manipulation tab content."""
    st.header("🔧 Data Manipulation")
    st.caption("Use natural language to transform your data. Each operation creates a new version you can revisit.")
    
    session_id = st.session_state.get("current_session_id")
    
    # Check if session exists
    if not session_id:
        st.warning("⚠️ No active session found. Please upload a file in the Upload tab first.")
        st.info("💡 After uploading a file, you can manipulate your data using natural language queries here.")
        
        # Show example queries
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
    
    st.divider()
    
    # Version History Graph Section
    st.subheader("📜 Version History Graph")
    st.caption("Track transformations over time. Branch from any version to explore alternatives.")
    
    try:
        response = requests.get(f"{FASTAPI_URL}/api/session/{session_id}/versions", timeout=5)
        response.raise_for_status()
        graph_data = response.json().get("graph", {"nodes": [], "edges": []})
    except Exception as e:
        st.info("No version history yet. Perform operations to build the graph.")
        graph_data = {"nodes": [], "edges": []}
    
    # Render graph if nodes exist
    if graph_data.get("nodes"):
        # Create Graphviz graph
        dot = graphviz.Digraph(comment='Version History')
        dot.attr(rankdir='LR')  # Left to right layout
        dot.attr('node', shape='box', style='rounded,filled', fillcolor='lightblue')
        
        # Add nodes
        for node in graph_data.get("nodes", []):
            label = node.get("label", node.get("id", "Unknown"))
            dot.node(node["id"], label)
        
        # Add edges
        for edge in graph_data.get("edges", []):
            label = edge.get("label", "")
            dot.edge(edge["from"], edge["to"], label=label)
        
        # Display graph
        st.graphviz_chart(dot.source)
        
        # Branching controls
        col1, col2 = st.columns([3, 1])
        with col1:
            version_options = [n["id"] for n in graph_data.get("nodes", [])]
            current_version = metadata.get("current_version", "v0")
            selected_version = st.selectbox(
                "Branch to version",
                options=version_options,
                index=version_options.index(current_version) if current_version in version_options else 0,
                help="Select a version to branch from. New operations will start from this version."
            )
        
        with col2:
            branch_button = st.button("🌿 Branch", type="secondary", help="Create a new branch from the selected version")
        
        if branch_button and selected_version != current_version:
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
        
        # Version details expander
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
        
        # Pruning controls
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
    
    st.divider()
    
    # Natural Language Query Input
    st.subheader("💬 Natural Language Query")
    st.caption("Describe the transformation you want. You can chain multiple steps in one sentence.")
    query = st.text_area(
        "Describe what you want to do with the data:",
        placeholder="e.g., Remove rows with missing values in the 'email' column, then sort by 'revenue' descending",
        height=100,
        key="nl_query_input"
    )
    
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
        with st.spinner("🤔 Processing your query... This may take a moment."):
            try:
                result = analyze_data_sync(session_id, query)
                
                if result.get("success"):
                    # Wait a bit for MCP server to update Redis
                    time.sleep(2)  # Increased wait time for Redis update
                    
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
                    st.error(f"❌ Operation failed: {error_msg}")
                    st.info("💡 You can try again with a different query.")
                    
            except Exception as e:
                st.error(f"❌ Unexpected error: {str(e)}")
                st.exception(e)
    
    st.divider()
    
    # Current Data Preview
    st.subheader("👀 Current Data Preview")
    if tables and selected_table:
        table_info = tables[selected_table]
        preview_data = table_info.get("preview", [])
        if preview_data:
            preview_df = pd.DataFrame(preview_data)
            st.dataframe(preview_df, width='stretch', height=400)
            
            # Download button
            csv = preview_df.to_csv(index=False)
            st.download_button(
                label="📥 Download Current Data as CSV",
                data=csv,
                file_name=f"{selected_table}_current.csv",
                mime="text/csv"
            )
        else:
            st.info("No preview data available.")


def main():
    """Main Streamlit application."""
    
    # Initialize session state
    initialize_session_state()
    
    # Accessibility: Skip link target
    st.markdown('<a class="skip-link" href="#main-content">Skip to main content</a>', unsafe_allow_html=True)
    st.markdown('<div id="main-content"></div>', unsafe_allow_html=True)

    # Header
    st.markdown('<div class="main-header">📊 Data Analyst Platform</div>', unsafe_allow_html=True)
    st.markdown("Upload your data files and manipulate them with natural language queries!")
    
    # Sidebar
    with st.sidebar:
        st.header("⚙️ Settings")
        
        # API Health Check
        st.subheader("API Status")
        if check_api_health():
            st.success("✅ FastAPI server is running")
            st.markdown('<span class="status-badge">Online</span>', unsafe_allow_html=True)
        else:
            st.error("❌ FastAPI server is not running")
            st.markdown('<span class="status-badge">Offline</span>', unsafe_allow_html=True)
            st.warning("Please start the FastAPI server:\n```bash\npython main.py\n```")
            st.stop()
        
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

