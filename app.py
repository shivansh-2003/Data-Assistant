"""
Streamlit application for Data Analyst Platform.
Connects to FastAPI ingestion endpoint and displays uploaded data.
"""

import streamlit as st
import requests
import pandas as pd
from typing import Dict, List
import json

# FastAPI endpoint configuration
FASTAPI_URL = "http://localhost:8000"
UPLOAD_ENDPOINT = f"{FASTAPI_URL}/api/ingestion/file-upload"
HEALTH_ENDPOINT = f"{FASTAPI_URL}/health"
CONFIG_ENDPOINT = f"{FASTAPI_URL}/api/ingestion/config"

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


def main():
    """Main Streamlit application."""
    # Header
    st.markdown('<div class="main-header">📊 Data Analyst Platform</div>', unsafe_allow_html=True)
    st.markdown("Upload your data files (CSV, Excel, PDF, Images) and explore them instantly!")
    
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
    
    # Main content area
    st.header("📤 Upload File")
    
    # File uploader
    uploaded_file = st.file_uploader(
        "Choose a file to upload",
        type=['csv', 'xlsx', 'xls', 'pdf', 'png', 'jpg', 'jpeg', 'tiff', 'bmp'],
        help="Supported formats: CSV, Excel, PDF, Images"
    )
    
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


if __name__ == "__main__":
    main()

