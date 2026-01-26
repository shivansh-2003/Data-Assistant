"""
FastAPI application with endpoints for file ingestion and session management.
Stores processed DataFrames in Upstash Redis with automatic TTL expiration.
Now supports MCP server integration via HTTP API with full DataFrame serialization.
"""

# Critical: Import FastAPI first to ensure app can be created even if other imports fail
from fastapi import FastAPI, UploadFile, File, HTTPException, Form, Query
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import logging
import os
import uuid
import time
import base64
import pickle
import json
import pandas as pd

import sys
from pathlib import Path
from typing import Optional, Dict, Any
from urllib.parse import urlparse
from pydantic import BaseModel
import httpx
# Lazy-load langfuse to reduce memory usage
try:
    from langfuse import observe
except ImportError:
    # Fallback if langfuse is not available
    def observe(*args, **kwargs):
        def decorator(func):
            return func
        return decorator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Lazy-load heavy dependencies to reduce memory usage at startup
# These will be initialized on first use, not at import time
_default_handler = None
_default_store = None

def get_default_handler():
    """Lazy-load IngestionHandler to avoid loading heavy dependencies at import time."""
    global _default_handler
    if _default_handler is None:
        from ingestion.ingestion_handler import IngestionHandler
        _default_handler = IngestionHandler()
        logger.info("IngestionHandler initialized (lazy-loaded)")
    return _default_handler

def get_default_store():
    """Lazy-load RedisStore to avoid connection attempts at import time."""
    global _default_store
    if _default_store is None:
        from redis_db import RedisStore
        _default_store = RedisStore()
        logger.info("RedisStore initialized (lazy-loaded)")
    return _default_store

# Import config modules (make optional to prevent import failures)
try:
    from ingestion.config import IngestionConfig
except ImportError:
    logger.warning("IngestionConfig not available")
    IngestionConfig = None

try:
    from ingestion.supabase_handler import load_supabase_tables
except ImportError:
    logger.warning("load_supabase_tables not available")
    load_supabase_tables = None

try:
    from redis_db.constants import KEY_SESSION_GRAPH
except ImportError:
    logger.warning("KEY_SESSION_GRAPH not available")
    KEY_SESSION_GRAPH = None

# MCP server - lazy loaded to reduce memory usage at startup
# Initialize with safe defaults
mcp_available = False
mcp_app = None

def load_mcp_server():
    """Lazy-load MCP server only when needed to reduce memory usage at startup."""
    global mcp_available, mcp_app
    if mcp_app is not None:
        return mcp_app
    
    try:
        from data_mcp.data import mcp
        
        # Create ASGI app from MCP server
        # path="/mcp" creates routes at /mcp within the app
        # When mounted at /data, final endpoint will be /data/mcp
        mcp_app = mcp.http_app(path="/mcp")
        mcp_available = True
        logger.info("✅ MCP server module loaded successfully (lazy-loaded)")
        return mcp_app
    except ImportError as e:
        logger.warning(f"⚠️ Failed to import MCP server: {e}")
        logger.info("MCP server functionality will be unavailable - continuing without it")
        mcp_available = False
        mcp_app = None
        return None
    except Exception as e:
        logger.warning(f"⚠️ Error initializing MCP server: {e}")
        logger.info("MCP server functionality will be unavailable - continuing without it")
        mcp_available = False
        mcp_app = None
        return None

# Load MCP server if enabled (optional for memory-constrained deployments)
if os.getenv("ENABLE_MCP", "true").lower() == "true":
    try:
        load_mcp_server()
    except Exception as e:
        logger.warning(f"MCP server unavailable: {e}")

# Initialize FastAPI app - MUST succeed for uvicorn to work
# Create app immediately - this is the most critical part
app = FastAPI(
    title="Data Analyst Platform - Ingestion API",
    description="API for ingesting files and managing session data in Redis",
    version="1.1.0"
)

# CORS middleware - wrap in try/except to prevent crashes
try:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
except Exception as e:
    logger.warning(f"Failed to add CORS middleware: {e}")

# Add startup event to log when app is ready
@app.on_event("startup")
async def startup_event():
    """Log startup information when app is ready."""
    port = int(os.getenv("PORT", 10000))  # Render default is 10000
    is_production = os.getenv("RENDER") or os.getenv("ENVIRONMENT") == "production"
    env_type = 'Production (Render)' if is_production else 'Local Development'
    
    logger.info("=" * 60)
    logger.info(f"🚀 FastAPI server started - {env_type}")
    logger.info(f"📊 Server running on port {port}")
    logger.info(f"🏥 Health: /health")
    logger.info(f"📚 Docs: /docs")
    logger.info(f"🔧 MCP Endpoint: /data/mcp (available: {mcp_available})")
    logger.info("=" * 60)

# Add minimal test endpoint first (before any other endpoints)
@app.get("/ping")
async def ping():
    """Minimal health check endpoint that doesn't depend on any services."""
    return {"status": "ok", "message": "Server is running"}

# Mount MCP server at /data endpoint (if available)
if mcp_available and mcp_app:
    app.mount("/data", mcp_app)
    logger.info("MCP server mounted at /data/mcp")

@app.get("/test-mcp")
async def test_mcp():
    """Test endpoint to verify MCP server is accessible."""
    is_production = os.getenv("RENDER") or os.getenv("ENVIRONMENT") == "production"
    if is_production:
        base_url = os.getenv("RENDER_EXTERNAL_URL", "https://data-assistant-m4kl.onrender.com")
        mcp_url = f"{base_url}/data/mcp"
    else:
        port = int(os.getenv("PORT", 10000))
        mcp_url = f"http://localhost:{port}/data/mcp"
    
    return {
        "mcp_mounted": mcp_available,
        "endpoint": "/data/mcp",
        "environment": "production" if is_production else "development",
        "message": f"MCP server is {'available' if mcp_available else 'unavailable'} at {mcp_url}" if mcp_available else "MCP server module not loaded"
    }

@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "message": "Data Analyst Platform - Ingestion API",
        "version": "1.1.0",
        "redis_connected": get_default_store().is_connected(),
        "endpoints": {
            "file_upload": "/api/ingestion/file-upload",
            "url_upload": "/api/ingestion/url-upload",
            "supabase_import": "/api/ingestion/supabase-import",
            "health": "/health",
            "session_create": "POST /api/session/{session_id}/upload",
            "session_tables": "GET /api/session/{session_id}/tables",
            "session_metadata": "GET /api/session/{session_id}/metadata",
            "session_delete": "DELETE /api/session/{session_id}",
            "session_list": "GET /api/sessions",
            "session_update": "PUT /api/session/{session_id}/tables"
        },
        "features": {
            "mcp_integration": True,
            "full_serialization": True,
            "ttl_management": True
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    try:
        redis_status = get_default_store().is_connected()
    except Exception as e:
        logger.warning(f"Error checking Redis connection: {e}")
        redis_status = False
    
    return {
        "status": "healthy",
        "service": "ingestion-api",
        "redis_connected": redis_status,
        "version": "1.1.0",
        "mcp_available": mcp_available,
        "app_loaded": True
    }


# ============================================================================
# File Upload & Session Creation
# ============================================================================

class UrlIngestionRequest(BaseModel):
    url: str
    file_type: Optional[str] = None
    session_id: Optional[str] = None


class SupabaseIngestionRequest(BaseModel):
    connection_string: str
    schema: str = "public"
    session_id: Optional[str] = None
    project_name: Optional[str] = None


def _build_response_and_store(
    session_id: str,
    result: Dict[str, Any],
    file_name: str,
    file_type_override: Optional[str] = None,
    source: Optional[str] = None
) -> Dict[str, Any]:
    """Build response payload and persist session data to Redis."""
    response_data = {
        "success": result["success"],
        "session_id": session_id,
        "metadata": result["metadata"],
        "tables": []
    }
    if file_type_override:
        response_data["metadata"]["file_type"] = file_type_override
    
    if result["success"] and result["tables"]:
        tables_dict = {}
        for idx, df in enumerate(result["tables"]):
            if hasattr(df, "attrs") and "sheet_name" in df.attrs:
                table_name = df.attrs["sheet_name"]
            elif hasattr(df, "attrs") and "table_name" in df.attrs:
                table_name = df.attrs["table_name"]
            elif len(result["tables"]) == 1:
                table_name = "current"
            else:
                table_name = f"table_{idx}"
            
            tables_dict[table_name] = df
            response_data["tables"].append({
                "table_name": table_name,
                "row_count": len(df),
                "column_count": len(df.columns),
                "columns": list(df.columns),
                "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
                "preview": df.head(5).to_dict(orient="records")
            })
        
        session_metadata = {
            "file_name": file_name,
            "file_type": response_data["metadata"]["file_type"],
            "table_count": len(tables_dict),
            "table_names": list(tables_dict.keys()),
            "created_at": time.time(),
            "processing_time": result["metadata"]["processing_time"],
            "current_version": "v0"
        }
        if source:
            session_metadata["source"] = source
        
        if get_default_store().save_session(session_id, tables_dict, session_metadata):
            response_data["redis_stored"] = True
            logger.info(f"Session {session_id} stored in Redis with {len(tables_dict)} tables")
            
            if get_default_store().save_version(session_id, "v0", tables_dict):
                get_default_store().update_graph(
                    session_id,
                    parent_vid=None,
                    new_vid="v0",
                    operation="Initial Upload",
                    query=None
                )
                logger.info(f"Created initial version v0 for session {session_id}")
        else:
            response_data["redis_stored"] = False
            logger.warning(f"Failed to store session {session_id} in Redis")
    
    return response_data


def _generate_session_id(session_id: Optional[str]) -> str:
    """Generate a session ID if not provided or placeholder."""
    if not session_id or session_id.lower() == "string":
        return str(uuid.uuid4())
    return session_id


@app.post("/api/ingestion/file-upload")
@observe(name="api_file_upload", as_type="span")
async def file_upload(
    file: UploadFile = File(...),
    file_type: Optional[str] = Form(None),
    session_id: Optional[str] = Form(None)
):
    """
    Upload and process a file. Stores DataFrames in Redis session.
    
    - If session_id not provided, generates a new UUID
    - Processed DataFrames are stored in Redis with TTL
    - Session auto-expires after 30 minutes of inactivity
    """
    temp_file_path = None
    
    try:
        # Read and validate file
        file_content = await file.read()
        file_size = len(file_content)
        
        if IngestionConfig and file_size > IngestionConfig.MAX_FILE_SIZE:
            max_mb = IngestionConfig.MAX_FILE_SIZE / (1024 * 1024)
            raise HTTPException(
                status_code=413,
                detail=f"File size ({file_size / (1024 * 1024):.2f}MB) exceeds maximum ({max_mb}MB)"
            )
        
        if file_size < 1:
            raise HTTPException(status_code=400, detail="File is empty")
        
        # Generate session_id if not provided or if placeholder value
        session_id = _generate_session_id(session_id)
        
        # Save temp file
        if IngestionConfig:
            IngestionConfig.ensure_temp_dir()
            temp_dir = IngestionConfig.TEMP_DIR
        else:
            temp_dir = "/tmp/data-assistant"
            os.makedirs(temp_dir, exist_ok=True)
        temp_file_path = os.path.join(temp_dir, f"{session_id}_{file.filename}")
        
        with open(temp_file_path, "wb") as f:
            f.write(file_content)
        
        logger.info(f"Processing file: {file.filename} ({file_size} bytes)")
        
        # Process file using ingestion handler
        result = get_default_handler().process_file(temp_file_path, file_type, file.content_type)
        
        response_data = _build_response_and_store(
            session_id=session_id,
            result=result,
            file_name=file.filename,
            source="file_upload"
        )
        return JSONResponse(content=response_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing file: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Cleanup temp file
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except Exception as e:
                logger.warning(f"Failed to remove temp file: {e}")


@app.post("/api/ingestion/url-upload")
@observe(name="api_url_upload", as_type="span")
async def url_upload(request: UrlIngestionRequest):
    """Download a file from a URL and ingest it."""
    temp_file_path = None
    
    try:
        session_id = _generate_session_id(request.session_id)
        parsed = urlparse(request.url)
        if parsed.scheme not in {"http", "https"}:
            raise HTTPException(status_code=400, detail="Only http/https URLs are supported")
        
        if IngestionConfig:
            IngestionConfig.ensure_temp_dir()
            temp_dir = IngestionConfig.TEMP_DIR
        else:
            temp_dir = "/tmp/data-assistant"
            os.makedirs(temp_dir, exist_ok=True)
        filename = os.path.basename(parsed.path) or "downloaded_file"
        temp_file_path = os.path.join(temp_dir, f"{session_id}_{filename}")
        
        async with httpx.AsyncClient(follow_redirects=True, timeout=60) as client:
            response = await client.get(request.url)
            response.raise_for_status()
            content = response.content
        
        max_size = IngestionConfig.MAX_FILE_SIZE if IngestionConfig else 100 * 1024 * 1024
        if len(content) > max_size:
            max_mb = max_size / (1024 * 1024)
            raise HTTPException(
                status_code=413,
                detail=f"File size exceeds maximum ({max_mb}MB)"
            )
        if len(content) < 1:
            raise HTTPException(status_code=400, detail="Downloaded file is empty")
        
        with open(temp_file_path, "wb") as f:
            f.write(content)
        
        mime_type = response.headers.get("content-type")
        result = get_default_handler().process_file(temp_file_path, request.file_type, mime_type)
        response_data = _build_response_and_store(
            session_id=session_id,
            result=result,
            file_name=filename,
            source="url_upload"
        )
        return JSONResponse(content=response_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing URL: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except Exception as e:
                logger.warning(f"Failed to remove temp file: {e}")


@app.post("/api/ingestion/supabase-import")
@observe(name="api_supabase_import", as_type="span")
async def supabase_import(request: SupabaseIngestionRequest):
    """Import all tables from a Supabase project using a Postgres connection string."""
    try:
        session_id = _generate_session_id(request.session_id)
        tables = load_supabase_tables(
            connection_string=request.connection_string,
            schema=request.schema
        )
        result = {
            "success": len(tables) > 0,
            "tables": tables,
            "metadata": {
                "file_type": "supabase",
                "table_count": len(tables),
                "processing_time": 0,
                "errors": [] if len(tables) > 0 else ["No tables found"],
                "file_path": request.project_name or "supabase"
            }
        }
        response_data = _build_response_and_store(
            session_id=session_id,
            result=result,
            file_name=request.project_name or "supabase",
            file_type_override="supabase",
            source="supabase"
        )
        return JSONResponse(content=response_data)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error importing Supabase tables: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Session Management Endpoints
# ============================================================================

@app.get("/api/sessions")
async def get_all_sessions():
    """List all active sessions in Redis."""
    try:
        sessions = get_default_store().list_sessions()
        return JSONResponse(content={
            "success": True,
            "count": len(sessions),
            "sessions": sessions
        })
    except Exception as e:
        logger.error(f"Error listing sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/session/{session_id}/tables")
async def get_session_tables(
    session_id: str, 
    format: str = Query("summary", regex="^(summary|full)$")
):
    """
    Get all tables from a session.
    Extends session TTL on access.
    
    Query Parameters:
        format: "summary" (default) for table metadata, "full" for serialized DataFrames
    """
    try:
        tables = get_default_store().load_session(session_id)
        
        if tables is None:
            raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
        
        # Extend TTL on access
        get_default_store().extend_ttl(session_id)
        
        if format == "full":
            # Return full serialized DataFrames for MCP integration
            response = {
                "session_id": session_id,
                "table_count": len(tables),
                "tables": []
            }
            
            for name, df in tables.items():
                # Serialize DataFrame to base64-encoded pickle
                pickle_bytes = pickle.dumps(df)
                base64_data = base64.b64encode(pickle_bytes).decode('utf-8')
                
                response["tables"].append({
                    "table_name": name,
                    "data": base64_data,
                    "row_count": len(df),
                    "column_count": len(df.columns),
                    "columns": list(df.columns),
                    "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()}
                })
            
            return JSONResponse(content=response)
        else:
            # Return summary format (default, backward compatible)
            response = {
                "session_id": session_id,
                "table_count": len(tables),
                "tables": {}
            }
            
            for name, df in tables.items():
                response["tables"][name] = {
                    "row_count": len(df),
                    "column_count": len(df.columns),
                    "columns": list(df.columns),
                    "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
                    "preview": df.head(10).to_dict(orient="records")
                }
            
            return JSONResponse(content=response)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error loading session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/session/{session_id}/metadata")
async def get_session_metadata(session_id: str):
    """Get session metadata."""
    try:
        metadata = get_default_store().get_metadata(session_id)
        
        if metadata is None:
            raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
        
        # Extend TTL on access
        get_default_store().extend_ttl(session_id)
        
        return JSONResponse(content={
            "session_id": session_id,
            "metadata": metadata
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting metadata: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/session/{session_id}/tables")
async def update_session_tables(
    session_id: str,
    request_data: dict
):
    """
    Update tables in a session with serialized DataFrames.
    Used by MCP server to save manipulated data back to Redis.
    
    Request Body:
        {
            "tables": {
                "table_name": {
                    "data": "base64_encoded_pickle_data",
                    "row_count": 100,
                    "column_count": 5,
                    "columns": ["col1", "col2"],
                    "dtypes": {"col1": "int64", "col2": "object"}
                }
            },
            "metadata": {
                "updated_at": 1234567890,
                "updated_by": "mcp_server",
                "operation_count": 5
            }
        }
    """
    try:
        if not get_default_store().session_exists(session_id):
            raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
        
        tables_data = request_data.get("tables", {})
        metadata_updates = request_data.get("metadata", {})
        
        if not tables_data:
            raise HTTPException(status_code=400, detail="No tables provided in request")
        
        # Deserialize the tables from base64-encoded pickle
        tables_dict = {}
        for table_name, table_info in tables_data.items():
            base64_data = table_info.get("data")
            if not base64_data:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Missing data for table '{table_name}'"
                )
            
            try:
                # Decode base64 and unpickle DataFrame
                pickle_bytes = base64.b64decode(base64_data.encode('utf-8'))
                df = pickle.loads(pickle_bytes)
                
                if not isinstance(df, pd.DataFrame):
                    raise ValueError(f"Deserialized data for table '{table_name}' is not a DataFrame")
                
                tables_dict[table_name] = df
                
            except Exception as e:
                logger.error(f"Failed to deserialize table '{table_name}': {e}")
                raise HTTPException(
                    status_code=400,
                    detail=f"Failed to deserialize table '{table_name}': {str(e)}"
                )
        
        # Get existing metadata and merge updates
        existing_metadata = get_default_store().get_metadata(session_id) or {}
        updated_metadata = {**existing_metadata, **metadata_updates}
        updated_metadata["last_updated"] = time.time()
        updated_metadata["updated_by"] = "mcp_server"
        
        # Save to Redis
        if get_default_store().save_session(session_id, tables_dict, updated_metadata):
            # Extend TTL on successful update
            get_default_store().extend_ttl(session_id)
            
            logger.info(f"Successfully updated session {session_id} with {len(tables_dict)} tables")
            return JSONResponse(content={
                "success": True,
                "message": f"Session '{session_id}' updated successfully",
                "table_count": len(tables_dict),
                "tables_updated": list(tables_dict.keys())
            })
        else:
            logger.error(f"Failed to save session {session_id} to Redis")
            raise HTTPException(status_code=500, detail="Failed to save session to Redis")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating session tables: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/session/{session_id}")
async def delete_session_endpoint(session_id: str):
    """
    Delete a session and wipe all its data from Redis.
    """
    try:
        if not get_default_store().session_exists(session_id):
            raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
        
        if get_default_store().delete_session(session_id):
            logger.info(f"Session {session_id} deleted from Redis")
            return JSONResponse(content={
                "success": True,
                "message": f"Session '{session_id}' deleted successfully"
            })
        else:
            raise HTTPException(status_code=500, detail="Failed to delete session")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/session/{session_id}/extend")
async def extend_session_ttl(session_id: str):
    """Extend session TTL (keeps session alive longer)."""
    try:
        if not get_default_store().session_exists(session_id):
            raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
        
        if get_default_store().extend_ttl(session_id):
            return JSONResponse(content={
                "success": True,
                "message": f"Session '{session_id}' TTL extended"
            })
        else:
            raise HTTPException(status_code=500, detail="Failed to extend TTL")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error extending TTL: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/ingestion/config")
async def get_config():
    """Get ingestion configuration."""
    if IngestionConfig:
        return {
            "max_file_size_mb": IngestionConfig.MAX_FILE_SIZE / (1024 * 1024),
            "supported_formats": {k: list(v) for k, v in IngestionConfig.FILE_TYPES.items()},
            "max_tables_per_file": IngestionConfig.MAX_TABLES_PER_FILE
        }
    else:
        return {
            "max_file_size_mb": 100,
            "supported_formats": {"csv": [".csv"], "excel": [".xlsx", ".xls"]},
            "max_tables_per_file": 10
        }


# ============================================================================
# Version Management Endpoints
# ============================================================================

@app.get("/api/session/{session_id}/versions")
async def get_session_versions(session_id: str):
    """
    Get all versions and graph structure for a session.
    
    Returns:
        Graph structure with nodes and edges
    """
    try:
        if not get_default_store().session_exists(session_id):
            raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
        
        graph = get_default_store().get_graph(session_id)
        
        # Extend TTL on access
        get_default_store().extend_ttl(session_id)
        
        return JSONResponse(content={
            "success": True,
            "graph": graph
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting versions for {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/session/{session_id}/version/{version_id}")
async def get_version_tables(session_id: str, version_id: str):
    """
    Get a specific version's tables (summary format).
    
    Used for previewing version data.
    """
    try:
        if not get_default_store().session_exists(session_id):
            raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
        
        tables = get_default_store().load_version(session_id, version_id)
        
        if tables is None:
            raise HTTPException(status_code=404, detail=f"Version '{version_id}' not found")
        
        # Extend TTL on access
        get_default_store().extend_ttl(session_id)
        
        # Return summary format
        response = {
            "session_id": session_id,
            "version_id": version_id,
            "table_count": len(tables),
            "tables": {}
        }
        
        for name, df in tables.items():
            response["tables"][name] = {
                "row_count": len(df),
                "column_count": len(df.columns),
                "columns": list(df.columns),
                "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
                "preview": df.head(10).to_dict(orient="records")
            }
        
        return JSONResponse(content=response)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error loading version {version_id} for {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/session/{session_id}/branch")
async def create_branch(session_id: str, request_data: Dict[str, Any]):
    """
    Switch to a version (branch) by copying its tables to main session.
    
    Request Body:
        {"version_id": "v1"}
    """
    try:
        if not get_default_store().session_exists(session_id):
            raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
        
        version_id = request_data.get("version_id")
        if not version_id:
            raise HTTPException(status_code=400, detail="version_id is required")
        
        # Load version tables
        tables = get_default_store().load_version(session_id, version_id)
        if tables is None:
            raise HTTPException(status_code=404, detail=f"Version '{version_id}' not found")
        
        # Get existing metadata
        metadata = get_default_store().get_metadata(session_id) or {}
        
        # Overwrite main session with version data
        if get_default_store().save_session(session_id, tables, metadata):
            # Set current version
            get_default_store().set_current_version(session_id, version_id)
            
            # Extend TTL
            get_default_store().extend_ttl(session_id)
            
            logger.info(f"Branched session {session_id} to version {version_id}")
            return JSONResponse(content={
                "success": True,
                "message": f"Branched to {version_id}",
                "version_id": version_id
            })
        else:
            raise HTTPException(status_code=500, detail="Failed to save session")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error branching to version: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/session/{session_id}/save_version")
async def save_version_endpoint(session_id: str, request_data: Dict[str, Any]):
    """
    Save current session tables as a new version.
    
    Request Body:
        {
            "version_id": "v1",
            "operation": "Filtered rows",
            "query": "Filter rows where age > 18"
        }
    """
    try:
        if not get_default_store().session_exists(session_id):
            raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
        
        version_id = request_data.get("version_id")
        operation = request_data.get("operation", "Operation")
        query = request_data.get("query")
        
        if not version_id:
            raise HTTPException(status_code=400, detail="version_id is required")
        
        # Get current session tables
        tables = get_default_store().load_session(session_id)
        if tables is None:
            raise HTTPException(status_code=404, detail=f"Session '{session_id}' tables not found")
        
        # Get current version from metadata
        current_vid = get_default_store().get_current_version(session_id) or "v0"
        
        # Save as new version
        if get_default_store().save_version(session_id, version_id, tables):
            # Update graph
            get_default_store().update_graph(
                session_id,
                parent_vid=current_vid,
                new_vid=version_id,
                operation=operation,
                query=query
            )
            
            # Set as current version
            get_default_store().set_current_version(session_id, version_id)
            
            logger.info(f"Saved version {version_id} for session {session_id}")
            return JSONResponse(content={
                "success": True,
                "message": f"Version {version_id} saved",
                "version_id": version_id
            })
        else:
            raise HTTPException(status_code=500, detail="Failed to save version")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving version: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/session/{session_id}/version/{version_id}")
async def delete_version_endpoint(session_id: str, version_id: str):
    """
    Delete a specific version and remove it from the graph.
    
    Used for manual pruning.
    """
    try:
        if not get_default_store().session_exists(session_id):
            raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
        
        # Delete version data
        if get_default_store().delete_version(session_id, version_id):
            # Remove from graph
            graph = get_default_store().get_graph(session_id)
            graph["nodes"] = [n for n in graph["nodes"] if n["id"] != version_id]
            graph["edges"] = [e for e in graph["edges"] if e["from"] != version_id and e["to"] != version_id]
            
            # Save updated graph
            key = KEY_SESSION_GRAPH.format(sid=session_id)
            get_default_store().redis.setex(key, get_default_store().session_ttl, json.dumps(graph))
            
            logger.info(f"Deleted version {version_id} for session {session_id}")
            return JSONResponse(content={
                "success": True,
                "message": f"Version {version_id} deleted"
            })
        else:
            raise HTTPException(status_code=404, detail=f"Version '{version_id}' not found")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting version: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/session/{session_id}/prune_versions")
async def prune_versions_endpoint(session_id: str, request_data: Optional[Dict[str, Any]] = None):
    """
    Prune old versions, keeping only the most recent N.
    
    Request Body (optional):
        {"keep_last_n": 50}
    """
    try:
        if not get_default_store().session_exists(session_id):
            raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
        
        keep_last_n = None
        if request_data:
            keep_last_n = request_data.get("keep_last_n")
        
        if keep_last_n is None:
            return JSONResponse(content={
                "success": True,
                "message": "No pruning limit specified, keeping all versions"
            })
        
        # Get graph
        graph = get_default_store().get_graph(session_id)
        nodes = graph.get("nodes", [])
        
        if len(nodes) <= keep_last_n:
            return JSONResponse(content={
                "success": True,
                "message": f"Only {len(nodes)} versions exist, no pruning needed"
            })
        
        # Sort nodes by timestamp (newest first)
        nodes_sorted = sorted(nodes, key=lambda n: n.get("timestamp", 0), reverse=True)
        
        # Keep last N, delete the rest
        to_keep = {n["id"] for n in nodes_sorted[:keep_last_n]}
        to_delete = [n["id"] for n in nodes_sorted[keep_last_n:]]
        
        # Delete versions
        deleted_count = 0
        for vid in to_delete:
            if get_default_store().delete_version(session_id, vid):
                deleted_count += 1
        
        # Update graph
        graph["nodes"] = [n for n in nodes if n["id"] in to_keep]
        graph["edges"] = [e for e in graph["edges"] if e["from"] in to_keep and e["to"] in to_keep]
        
        # Save updated graph
        key = KEY_SESSION_GRAPH.format(sid=session_id)
        get_default_store().redis.setex(key, get_default_store().session_ttl, json.dumps(graph))
        
        logger.info(f"Pruned {deleted_count} versions for session {session_id}")
        return JSONResponse(content={
            "success": True,
            "message": f"Pruned {deleted_count} versions, kept {len(to_keep)}",
            "deleted_count": deleted_count,
            "kept_count": len(to_keep)
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error pruning versions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Safety check: ensure app is always defined (required for uvicorn import)
# This MUST be at module level for uvicorn to work
if 'app' not in globals() or app is None:
    logger.error("CRITICAL: FastAPI app was not created!")
    app = FastAPI(title="Data Analyst Platform", version="1.1.0")

if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))  # Render default is 10000
    print(f"Starting server on 0.0.0.0:{port}")
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False, log_level="info")