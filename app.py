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
from datetime import datetime
from data_visualization import render_visualization_tab

# FastAPI endpoint configuration
FASTAPI_URL = "http://localhost:8001"
UPLOAD_ENDPOINT = f"{FASTAPI_URL}/api/ingestion/file-upload"
HEALTH_ENDPOINT = f"{FASTAPI_URL}/health"
CONFIG_ENDPOINT = f"{FASTAPI_URL}/api/ingestion/config"
SESSION_ENDPOINT = f"{FASTAPI_URL}/api/session"

# MCP Configuration
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://127.0.0.1:8000/mcp")
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
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        margin-bottom: 1rem;
    }
    .success-box {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        margin: 1rem 0;
    }
    .error-box {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #f8d7da;
        border: 1px solid #f5c6cb;
        margin: 1rem 0;
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
    
    # File uploader
    uploaded_file = st.file_uploader(
        "Choose a file to upload",
        type=['csv', 'xlsx', 'xls', 'pdf', 'png', 'jpg', 'jpeg', 'tiff', 'bmp'],
        help="Supported formats: CSV, Excel, PDF, Images"
    )
    
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
            upload_button = st.button("🚀 Upload & Process", type="primary")
        
        if upload_button:
            with st.spinner("Uploading and processing file..."):
                # Upload file
                result = upload_file(uploaded_file, file_type, session_id if session_id else None)
                
                # Display results
                if result.get("success"):
                    # Store session_id for cleanup later (in both state and URL)
                    save_session_id(result.get("session_id"))
                    st.success("✅ File processed successfully!")
                    
                    # Display metadata
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
                        if session_id:
                            st.metric("Session ID", session_id[:8] + "...")
                    
                    # Display errors if any
                    errors = metadata.get("errors", [])
                    if errors:
                        st.warning(f"⚠️ Warnings: {len(errors)} issue(s) encountered")
                        with st.expander("View Warnings"):
                            for error in errors:
                                st.text(f"• {error}")
                    
                    st.markdown("---")
                    
                    # Display each table
                    tables = result.get("tables", [])
                    if tables:
                        st.header(f"📊 Extracted Tables ({len(tables)})")
                        
                        # Create tabs for each table
                        if len(tables) > 1:
                            tab_names = [f"Table {i+1}" for i in range(len(tables))]
                            tabs = st.tabs(tab_names)
                            
                            for idx, tab in enumerate(tabs):
                                with tab:
                                    display_table_info(tables[idx], idx)
                        else:
                            # Single table - no tabs needed
                            display_table_info(tables[0], 0)
                    else:
                        st.warning("No tables found in the uploaded file.")
                
                else:
                    # Display error
                    error_msg = result.get("error", "Unknown error occurred")
                    st.error(f"❌ Failed to process file: {error_msg}")
                    
                    # Show metadata if available
                    metadata = result.get("metadata", {})
                    if metadata.get("errors"):
                        with st.expander("Error Details"):
                            for error in metadata["errors"]:
                                st.text(f"• {error}")
    
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


def render_manipulation_tab():
    """Render the Data Manipulation tab content."""
    st.header("🔧 Data Manipulation")
    
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
    
    # Natural Language Query Input
    st.subheader("💬 Natural Language Query")
    query = st.text_area(
        "Describe what you want to do with the data:",
        placeholder="e.g., Remove rows with missing values in the 'email' column, then sort by 'revenue' descending",
        height=100,
        key="nl_query_input"
    )
    
    col1, col2 = st.columns([1, 4])
    with col1:
        execute_button = st.button("🚀 Execute Query", type="primary", width='stretch')
    
    # Operation History
    st.divider()
    st.subheader("📜 Operation History")
    
    col1, col2 = st.columns([4, 1])
    with col1:
        history_count = len(st.session_state.operation_history)
        st.caption(f"Total operations: {history_count}")
    with col2:
        clear_history_button = st.button("🗑️ Clear History", width='stretch', help="Clear operation history")
    
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
                st.text(f"{idx}. [{dt.strftime('%H:%M:%S')}] {op.get('description', op.get('operation', 'Unknown'))}")
    
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
                    
                    # Add to operation history
                    st.session_state.operation_history.append({
                        "timestamp": time.time(),
                        "operation": "QUERY",
                        "description": query,
                        "response": result.get("response", "")
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
        else:
            st.error("❌ FastAPI server is not running")
            st.warning("Please start the FastAPI server:\n```bash\npython main.py\n```")
            st.stop()
        
        # MCP Server Status
        st.subheader("MCP Server Status")
        if OPENAI_API_KEY:
            st.success("✅ OpenAI API key configured")
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
    tab1, tab2, tab3 = st.tabs(["📤 Upload", "🔧 Data Manipulation", "📈 Visualization Centre"])
    
    with tab1:
        render_upload_tab()
    
    with tab2:
        render_manipulation_tab()
    
    with tab3:
        render_visualization_tab()


if __name__ == "__main__":
    main()

