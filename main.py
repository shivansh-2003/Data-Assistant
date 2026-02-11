"""
FastAPI application for file ingestion and session management.
Stores DataFrames in Redis with automatic TTL expiration.
"""

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
from typing import Optional, Dict, Any
from urllib.parse import urlparse
from pydantic import BaseModel
import httpx

# Optional imports with fallbacks

from langfuse import observe
from ingestion.config import IngestionConfig
from ingestion.supabase_handler import load_supabase_tables
from redis_db.constants import KEY_SESSION_GRAPH

KEY_SESSION_GRAPH = None

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Lazy-loaded dependencies
_default_handler = None
_default_store = None
mcp_available = False
mcp_app = None

def get_default_handler():
    global _default_handler
    if _default_handler is None:
        from ingestion.ingestion_handler import IngestionHandler
        _default_handler = IngestionHandler()
    return _default_handler

def get_default_store():
    global _default_store
    if _default_store is None:
        from redis_db import RedisStore
        _default_store = RedisStore()
    return _default_store

# ============================================================================
# Pydantic Models - Request/Response Schemas
# ============================================================================

class UrlIngestionRequest(BaseModel):
    """Request model for URL-based file ingestion."""
    url: str
    file_type: Optional[str] = None
    session_id: Optional[str] = None

class SupabaseIngestionRequest(BaseModel):
    """Request model for Supabase database import."""
    connection_string: str
    db_schema: str = "public"  # Renamed from 'schema' to avoid shadowing
    session_id: Optional[str] = None
    project_name: Optional[str] = None

# ============================================================================
# FastAPI Application Initialization
# ============================================================================

# CRITICAL: Create app FIRST to ensure it always exists (for Render deployment)
app = FastAPI(title="Data Analyst Platform", version="1.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# Add minimal health check IMMEDIATELY (before MCP loading)
@app.get("/ping")
async def ping():
    return {"status": "ok", "timestamp": time.time()}

@app.get("/health")
async def health_check():
    redis_status = get_default_store().is_connected()
    return {"status": "healthy", "redis_connected": redis_status, "mcp_available": mcp_available}

# Now try to load MCP (non-blocking, with error handling)
mcp_http_app = None
if os.getenv("ENABLE_MCP", "true").lower() == "true":
    logger.info("Attempting to load MCP server...")
    from data_mcp.data import mcp
    mcp_http_app = mcp.http_app(path="/mcp")
    mcp_available = True
    logger.info("✅ MCP server loaded successfully")
    
    # Mount MCP server if loaded successfully
    app.mount("/data", mcp_http_app)
    logger.info("🔧 MCP server mounted at /data/mcp")

# Helper functions
def _generate_session_id(session_id: Optional[str]) -> str:
    return str(uuid.uuid4()) if not session_id or session_id.lower() == "string" else session_id

def _get_temp_dir():
    if IngestionConfig:
        IngestionConfig.ensure_temp_dir()
        return IngestionConfig.TEMP_DIR
    temp_dir = "/tmp/data-assistant"
    os.makedirs(temp_dir, exist_ok=True)
    return temp_dir

def _build_response_and_store(session_id: str, result: Dict[str, Any], file_name: str, file_type_override: Optional[str] = None, source: Optional[str] = None) -> Dict[str, Any]:
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
            table_name = (df.attrs.get("sheet_name") or df.attrs.get("table_name") or 
                         ("current" if len(result["tables"]) == 1 else f"table_{idx}"))
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
        
        store = get_default_store()
        if store.save_session(session_id, tables_dict, session_metadata):
            response_data["redis_stored"] = True
            if store.save_version(session_id, "v0", tables_dict):
                store.update_graph(session_id, parent_vid=None, new_vid="v0", operation="Initial Upload", query=None)
        else:
            response_data["redis_stored"] = False
    
    return response_data

# Endpoints
@app.get("/")
async def root():
    return {
        "message": "Data Analyst Platform",
        "version": "1.1.0",
        "redis_connected": get_default_store().is_connected(),
        "endpoints": {
            "file_upload": "/api/ingestion/file-upload",
            "url_upload": "/api/ingestion/url-upload",
            "supabase_import": "/api/ingestion/supabase-import",
            "health": "/health",
            "session_tables": "GET /api/session/{session_id}/tables",
            "session_delete": "DELETE /api/session/{session_id}"
        }
    }

@app.get("/test-mcp")
async def test_mcp():
    is_production = os.getenv("RENDER") or os.getenv("ENVIRONMENT") == "production"
    base_url = os.getenv("RENDER_EXTERNAL_URL", "https://data-assistant-m4kl.onrender.com") if is_production else f"http://localhost:{int(os.getenv('PORT', 10000))}"
    return {"mcp_mounted": mcp_available, "endpoint": "/data/mcp", "url": f"{base_url}/data/mcp"}

# File Upload Endpoints
@app.post("/api/ingestion/file-upload")
@observe(name="api_file_upload", as_type="span")
async def file_upload(file: UploadFile = File(...), file_type: Optional[str] = Form(None), session_id: Optional[str] = Form(None)):
    temp_file_path = None
    file_content = await file.read()
    file_size = len(file_content)
    
    if IngestionConfig and file_size > IngestionConfig.MAX_FILE_SIZE:
        max_mb = IngestionConfig.MAX_FILE_SIZE / (1024 * 1024)
        raise HTTPException(status_code=413, detail=f"File size ({file_size / (1024 * 1024):.2f}MB) exceeds maximum ({max_mb}MB)")
    
    if file_size < 1:
        raise HTTPException(status_code=400, detail="File is empty")
    
    session_id = _generate_session_id(session_id)
    temp_file_path = os.path.join(_get_temp_dir(), f"{session_id}_{file.filename}")
    
    with open(temp_file_path, "wb") as f:
        f.write(file_content)
    
    result = get_default_handler().process_file(temp_file_path, file_type, file.content_type)
    response_data = _build_response_and_store(session_id, result, file.filename, source="file_upload")
    
    if temp_file_path and os.path.exists(temp_file_path):
        os.remove(temp_file_path)
    
    return JSONResponse(content=response_data)

@app.post("/api/ingestion/url-upload")
@observe(name="api_url_upload", as_type="span")
async def url_upload(request: UrlIngestionRequest):
    temp_file_path = None
    session_id = _generate_session_id(request.session_id)
    parsed = urlparse(request.url)
    if parsed.scheme not in {"http", "https"}:
        raise HTTPException(status_code=400, detail="Only http/https URLs are supported")
    
    filename = os.path.basename(parsed.path) or "downloaded_file"
    temp_file_path = os.path.join(_get_temp_dir(), f"{session_id}_{filename}")
    
    async with httpx.AsyncClient(follow_redirects=True, timeout=60) as client:
        response = await client.get(request.url)
        response.raise_for_status()
        content = response.content
    
    max_size = IngestionConfig.MAX_FILE_SIZE if IngestionConfig else 100 * 1024 * 1024
    if len(content) > max_size:
        raise HTTPException(status_code=413, detail=f"File size exceeds maximum ({max_size / (1024 * 1024)}MB)")
    if len(content) < 1:
        raise HTTPException(status_code=400, detail="Downloaded file is empty")
    
    with open(temp_file_path, "wb") as f:
        f.write(content)
    
    result = get_default_handler().process_file(temp_file_path, request.file_type, response.headers.get("content-type"))
    response_data = _build_response_and_store(session_id, result, filename, source="url_upload")
    
    if temp_file_path and os.path.exists(temp_file_path):
        os.remove(temp_file_path)
    
    return JSONResponse(content=response_data)

@app.post("/api/ingestion/supabase-import")
@observe(name="api_supabase_import", as_type="span")
async def supabase_import(request: SupabaseIngestionRequest):
    if not load_supabase_tables:
        raise HTTPException(status_code=503, detail="Supabase import not available")
    session_id = _generate_session_id(request.session_id)
    tables = load_supabase_tables(connection_string=request.connection_string, schema=request.db_schema)
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
    response_data = _build_response_and_store(session_id, result, request.project_name or "supabase", file_type_override="supabase", source="supabase")
    return JSONResponse(content=response_data)

# Session Management
@app.get("/api/sessions")
async def get_all_sessions():
    sessions = get_default_store().list_sessions()
    return JSONResponse(content={"success": True, "count": len(sessions), "sessions": sessions})

@app.get("/api/session/{session_id}/tables")
async def get_session_tables(session_id: str, format: str = Query("summary", pattern="^(summary|full)$")):
    store = get_default_store()
    tables = store.load_session(session_id)
    if tables is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    
    store.extend_ttl(session_id)
    
    if format == "full":
        response = {"session_id": session_id, "table_count": len(tables), "tables": []}
        for name, df in tables.items():
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
        response = {"session_id": session_id, "table_count": len(tables), "tables": {}}
        for name, df in tables.items():
            response["tables"][name] = {
                "row_count": len(df),
                "column_count": len(df.columns),
                "columns": list(df.columns),
                "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
                "preview": df.head(10).to_dict(orient="records")
            }
        return JSONResponse(content=response)

@app.get("/api/session/{session_id}/metadata")
async def get_session_metadata(session_id: str):
    store = get_default_store()
    metadata = store.get_metadata(session_id)
    if metadata is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    store.extend_ttl(session_id)
    return JSONResponse(content={"session_id": session_id, "metadata": metadata})

@app.put("/api/session/{session_id}/tables")
async def update_session_tables(session_id: str, request_data: dict):
    store = get_default_store()
    if not store.session_exists(session_id):
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    
    tables_data = request_data.get("tables", {})
    metadata_updates = request_data.get("metadata", {})
    
    if not tables_data:
        raise HTTPException(status_code=400, detail="No tables provided in request")
    
    tables_dict = {}
    for table_name, table_info in tables_data.items():
        base64_data = table_info.get("data")
        if not base64_data:
            raise HTTPException(status_code=400, detail=f"Missing data for table '{table_name}'")
        
        pickle_bytes = base64.b64decode(base64_data.encode('utf-8'))
        df = pickle.loads(pickle_bytes)
        if not isinstance(df, pd.DataFrame):
            raise ValueError(f"Deserialized data for table '{table_name}' is not a DataFrame")
        tables_dict[table_name] = df
    
    existing_metadata = store.get_metadata(session_id) or {}
    updated_metadata = {**existing_metadata, **metadata_updates, "last_updated": time.time(), "updated_by": "mcp_server"}
    
    if store.save_session(session_id, tables_dict, updated_metadata):
        store.extend_ttl(session_id)
        return JSONResponse(content={
            "success": True,
            "message": f"Session '{session_id}' updated successfully",
            "table_count": len(tables_dict),
            "tables_updated": list(tables_dict.keys())
        })
    else:
        raise HTTPException(status_code=500, detail="Failed to save session to Redis")

@app.delete("/api/session/{session_id}")
async def delete_session_endpoint(session_id: str):
    store = get_default_store()
    if not store.session_exists(session_id):
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    
    if store.delete_session(session_id):
        return JSONResponse(content={"success": True, "message": f"Session '{session_id}' deleted successfully"})
    else:
        raise HTTPException(status_code=500, detail="Failed to delete session")

@app.post("/api/session/{session_id}/extend")
async def extend_session_ttl(session_id: str):
    store = get_default_store()
    if not store.session_exists(session_id):
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    
    if store.extend_ttl(session_id):
        return JSONResponse(content={"success": True, "message": f"Session '{session_id}' TTL extended"})
    else:
        raise HTTPException(status_code=500, detail="Failed to extend TTL")

@app.get("/api/ingestion/config")
async def get_config():
    if IngestionConfig:
        return {
            "max_file_size_mb": IngestionConfig.MAX_FILE_SIZE / (1024 * 1024),
            "supported_formats": {k: list(v) for k, v in IngestionConfig.FILE_TYPES.items()},
            "max_tables_per_file": IngestionConfig.MAX_TABLES_PER_FILE
        }
    else:
        return {"max_file_size_mb": 100, "supported_formats": {"csv": [".csv"], "excel": [".xlsx", ".xls"]}, "max_tables_per_file": 10}

# Version Management
@app.get("/api/session/{session_id}/versions")
async def get_session_versions(session_id: str):
    store = get_default_store()
    if not store.session_exists(session_id):
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    
    graph = store.get_graph(session_id)
    store.extend_ttl(session_id)
    return JSONResponse(content={"success": True, "graph": graph})

@app.get("/api/session/{session_id}/version/{version_id}")
async def get_version_tables(session_id: str, version_id: str):
    store = get_default_store()
    if not store.session_exists(session_id):
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    
    tables = store.load_version(session_id, version_id)
    if tables is None:
        raise HTTPException(status_code=404, detail=f"Version '{version_id}' not found")
    
    store.extend_ttl(session_id)
    response = {"session_id": session_id, "version_id": version_id, "table_count": len(tables), "tables": {}}
    for name, df in tables.items():
        response["tables"][name] = {
            "row_count": len(df),
            "column_count": len(df.columns),
            "columns": list(df.columns),
            "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
            "preview": df.head(10).to_dict(orient="records")
        }
    return JSONResponse(content=response)

@app.post("/api/session/{session_id}/branch")
async def create_branch(session_id: str, request_data: Dict[str, Any]):
    store = get_default_store()
    if not store.session_exists(session_id):
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    
    version_id = request_data.get("version_id")
    if not version_id:
        raise HTTPException(status_code=400, detail="version_id is required")
    
    tables = store.load_version(session_id, version_id)
    if tables is None:
        raise HTTPException(status_code=404, detail=f"Version '{version_id}' not found")
    
    metadata = store.get_metadata(session_id) or {}
    if store.save_session(session_id, tables, metadata):
        store.set_current_version(session_id, version_id)
        store.extend_ttl(session_id)
        return JSONResponse(content={"success": True, "message": f"Branched to {version_id}", "version_id": version_id})
    else:
        raise HTTPException(status_code=500, detail="Failed to save session")

@app.post("/api/session/{session_id}/save_version")
async def save_version_endpoint(session_id: str, request_data: Dict[str, Any]):
    store = get_default_store()
    if not store.session_exists(session_id):
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    
    version_id = request_data.get("version_id")
    operation = request_data.get("operation", "Operation")
    query = request_data.get("query")
    
    if not version_id:
        raise HTTPException(status_code=400, detail="version_id is required")
    
    tables = store.load_session(session_id)
    if tables is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' tables not found")
    
    current_vid = store.get_current_version(session_id) or "v0"
    if store.save_version(session_id, version_id, tables):
        store.update_graph(session_id, parent_vid=current_vid, new_vid=version_id, operation=operation, query=query)
        store.set_current_version(session_id, version_id)
        return JSONResponse(content={"success": True, "message": f"Version {version_id} saved", "version_id": version_id})
    else:
        raise HTTPException(status_code=500, detail="Failed to save version")

@app.delete("/api/session/{session_id}/version/{version_id}")
async def delete_version_endpoint(session_id: str, version_id: str):
    store = get_default_store()
    if not store.session_exists(session_id):
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    
    if store.delete_version(session_id, version_id):
        graph = store.get_graph(session_id)
        graph["nodes"] = [n for n in graph["nodes"] if n["id"] != version_id]
        graph["edges"] = [e for e in graph["edges"] if e["from"] != version_id and e["to"] != version_id]
        
        if KEY_SESSION_GRAPH:
            key = KEY_SESSION_GRAPH.format(sid=session_id)
            store.redis.setex(key, store.session_ttl, json.dumps(graph))
        
        return JSONResponse(content={"success": True, "message": f"Version {version_id} deleted"})
    else:
        raise HTTPException(status_code=404, detail=f"Version '{version_id}' not found")

@app.post("/api/session/{session_id}/prune_versions")
async def prune_versions_endpoint(session_id: str, request_data: Optional[Dict[str, Any]] = None):
    store = get_default_store()
    if not store.session_exists(session_id):
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    
    keep_last_n = request_data.get("keep_last_n") if request_data else None
    if keep_last_n is None:
        return JSONResponse(content={"success": True, "message": "No pruning limit specified, keeping all versions"})
    
    graph = store.get_graph(session_id)
    nodes = graph.get("nodes", [])
    
    if len(nodes) <= keep_last_n:
        return JSONResponse(content={"success": True, "message": f"Only {len(nodes)} versions exist, no pruning needed"})
    
    nodes_sorted = sorted(nodes, key=lambda n: n.get("timestamp", 0), reverse=True)
    to_keep = {n["id"] for n in nodes_sorted[:keep_last_n]}
    to_delete = [n["id"] for n in nodes_sorted[keep_last_n:]]
    
    deleted_count = 0
    for vid in to_delete:
        if store.delete_version(session_id, vid):
            deleted_count += 1
    
    graph["nodes"] = [n for n in nodes if n["id"] in to_keep]
    graph["edges"] = [e for e in graph["edges"] if e["from"] in to_keep and e["to"] in to_keep]
    
    if KEY_SESSION_GRAPH:
        key = KEY_SESSION_GRAPH.format(sid=session_id)
        store.redis.setex(key, store.session_ttl, json.dumps(graph))
    
    return JSONResponse(content={
        "success": True,
        "message": f"Pruned {deleted_count} versions, kept {len(to_keep)}",
        "deleted_count": deleted_count,
        "kept_count": len(to_keep)
    })

if __name__ == "__main__":

    port = int(os.getenv("PORT", 10000))
    print(f"Starting server on 0.0.0.0:{port}")
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False, log_level="info")
