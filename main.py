"""
FastAPI application for file ingestion and session management.
Stores DataFrames in Redis with automatic TTL expiration.
"""

# =============================================================================
# stdlib
# =============================================================================
import base64
import json
import logging
import os
import pickle
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, Optional

# =============================================================================
# Third-party — load .env first so every subsequent import sees the right env vars
# =============================================================================
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env", override=False)

from log_setup import setup_logging
setup_logging()

import pandas as pd
import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from langfuse import observe
from pydantic import BaseModel

# =============================================================================
# Local
# =============================================================================
from ingestion.config import IngestionConfig
from redis_db.constants import KEY_SESSION_GRAPH
from data_mcp.data_functions.df_codec import encode_df, decode_df

# =============================================================================
# MCP — side-effect imports must fire before mcp.http_app() is called.
# Do NOT wrap these in try/except: import failures must be loud and visible.
# Resources registered with URI templates appear under list_resource_templates,
# NOT list_resources — this is correct FastMCP 2.x behaviour.
# =============================================================================
from data_mcp.data import mcp
import data_mcp.resources        # noqa: F401 — registers @mcp.resource (as templates)
import data_mcp.prompt_workflows  # noqa: F401 — registers @mcp.prompt

# =============================================================================
# Logging
# =============================================================================
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Per-operation latency ceilings (seconds).  Exceeded → WARNING in logs.
# ---------------------------------------------------------------------------
_BENCHMARKS: dict[str, float] = {
    "api.save_version":              1.00,
    "api.save_version.snapshot":     0.30,
    "api.save_version.update_graph": 0.50,
    "api.branch":                    0.50,
    "api.branch.restore":            0.30,
}


def _perf_warn(name: str, elapsed: float, session_id: str = "") -> None:
    threshold = _BENCHMARKS.get(name)
    if threshold and elapsed > threshold:
        logger.warning(
            "[PERF][SLOW] %-40s  session=%s  %.3fs elapsed  (benchmark: %.3fs  |  %.1fx over)",
            name, session_id, elapsed, threshold, elapsed / threshold,
        )

# Confirm MCP registration immediately so startup logs show what is wired up.
logger.info(
    "MCP registration — tools: %d | prompts: %d | resource-templates: %d  "
    "| prompts=%s | templates=%s",
    len(mcp._tool_manager._tools),
    len(mcp._prompt_manager._prompts),
    len(mcp._resource_manager._templates),
    list(mcp._prompt_manager._prompts.keys()),
    list(mcp._resource_manager._templates.keys()),
)

# =============================================================================
# Module-level state
# =============================================================================
_default_handler = None
_default_store   = None
mcp_available    = False
mcp_http_app     = None

# =============================================================================
# Lazy-loaded singletons
# =============================================================================

def get_default_handler():
    global _default_handler
    if _default_handler is None:
        from ingestion.ingestion_handler import IngestionHandler
        _default_handler = IngestionHandler()
    return _default_handler


def get_default_store():
    global _default_store
    if _default_store is None:
        from redis_db import get_session_store
        _default_store = get_session_store()
    return _default_store

# =============================================================================
# Pydantic models
# =============================================================================


# =============================================================================
# MCP HTTP app — must be created before FastAPI so its lifespan is available
# =============================================================================

if os.getenv("ENABLE_MCP", "true").lower() == "true":
    try:
        logger.info("Attempting to load MCP server...")
        mcp_http_app = mcp.http_app(path="/mcp")
        mcp_available = True
        logger.info("✅ MCP server loaded successfully")
    except Exception as e:
        logger.exception("MCP server failed to load: %s", e)

# =============================================================================
# Application lifespan
# =============================================================================

@asynccontextmanager
async def _app_lifespan(app: FastAPI):
    """Redis connectivity check + FastMCP Streamable HTTP session manager."""
    store = get_default_store()
    # R-1: surface which Redis backend is actually wired up so deployment
    # mistakes (e.g. accidentally falling back to Upstash REST) are obvious
    # in the logs from the moment the server boots.
    from redis_db.constants import use_redis_cloud_kv
    backend = "cloud" if use_redis_cloud_kv() else "upstash-rest"
    backend_class = type(store).__name__
    logger.info(
        "[REDIS] backend=%s  store=%s  connected=%s",
        backend, backend_class, store.is_connected(),
    )
    if store.is_connected():
        logger.info("Redis session store: connected — session tables will persist.")
    else:
        logger.error(
            "Redis session store: NOT connected. Configure Redis in your project .env "
            "(e.g. REDIS_URL or REDIS_HOST + REDIS_PASSWORD; otherwise Upstash REST URL/token). "
            "Uploads may return 200 with redis_stored=false; "
            "GET /api/session/.../tables will 404."
        )
    if mcp_http_app is not None:
        async with mcp_http_app.lifespan(mcp_http_app):
            yield
    else:
        yield

# =============================================================================
# FastAPI application
# =============================================================================

# CRITICAL: lifespan runs the MCP session manager; mounting alone is not enough.
app = FastAPI(
    title="Data Analyst Platform",
    version="1.1.0",
    lifespan=_app_lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if mcp_http_app is not None:
    app.mount("/data", mcp_http_app)
    logger.info("🔧 MCP server mounted at /data/mcp")

# =============================================================================
# Helpers
# =============================================================================

def _generate_session_id(session_id: Optional[str]) -> str:
    return (
        str(uuid.uuid4())
        if not session_id or session_id.lower() == "string"
        else session_id
    )


def _get_temp_dir() -> str:
    if IngestionConfig:
        IngestionConfig.ensure_temp_dir()
        return IngestionConfig.TEMP_DIR
    temp_dir = "/tmp/data-assistant"
    os.makedirs(temp_dir, exist_ok=True)
    return temp_dir


def _build_response_and_store(
    session_id: str,
    result: Dict[str, Any],
    file_name: str,
    file_type_override: Optional[str] = None,
    source: Optional[str] = None,
) -> Dict[str, Any]:
    response_data: Dict[str, Any] = {
        "success": result["success"],
        "session_id": session_id,
        "metadata": result["metadata"],
        "tables": [],
    }
    if file_type_override:
        response_data["metadata"]["file_type"] = file_type_override

    if result["success"] and result["tables"]:
        tables_dict: Dict[str, Any] = {}
        for idx, df in enumerate(result["tables"]):
            table_name = (
                df.attrs.get("sheet_name")
                or df.attrs.get("table_name")
                or ("current" if len(result["tables"]) == 1 else f"table_{idx}")
            )
            tables_dict[table_name] = df
            response_data["tables"].append({
                "table_name": table_name,
                "row_count": len(df),
                "column_count": len(df.columns),
                "columns": list(df.columns),
                "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
                "preview": df.head(5).to_dict(orient="records"),
            })

        session_metadata = {
            "file_name": file_name,
            "file_type": response_data["metadata"]["file_type"],
            "table_count": len(tables_dict),
            "table_names": list(tables_dict.keys()),
            "created_at": time.time(),
            "processing_time": result["metadata"]["processing_time"],
            "current_version": "v0",
        }
        if source:
            session_metadata["source"] = source

        store = get_default_store()
        if store.save_session(session_id, tables_dict, session_metadata):
            response_data["redis_stored"] = True
            if store.save_version(session_id, "v0", tables_dict):
                store.update_graph(
                    session_id, parent_vid=None, new_vid="v0",
                    operation="Initial Upload", query=None,
                )
        else:
            response_data["redis_stored"] = False
            response_data["redis_error"] = (
                "Redis not connected. Set REDIS_URL or REDIS_HOST + REDIS_PASSWORD in .env "
                "(or Upstash UPSTASH_REDIS_REST_URL + UPSTASH_REDIS_REST_TOKEN), then restart the API."
                if not store.is_connected()
                else "Redis save failed (see API logs). Common causes: payload too "
                     "large for Upstash, or transient REST error."
            )

    return response_data

# =============================================================================
# Routes — infrastructure
# =============================================================================

@app.get("/ping")
async def ping():
    return {"status": "ok", "timestamp": time.time()}


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "redis_connected": get_default_store().is_connected(),
        "mcp_available": mcp_available,
    }


@app.get("/")
async def root():
    return {
        "message": "Data Analyst Platform",
        "version": "1.1.0",
        "redis_connected": get_default_store().is_connected(),
        "endpoints": {
            "file_upload": "/api/ingestion/file-upload",
"health": "/health",
            "debug_redis": "/api/debug/redis",
            "session_tables": "GET /api/session/{session_id}/tables",
            "session_delete": "DELETE /api/session/{session_id}",
        },
    }


@app.get("/test-mcp")
async def test_mcp():
    is_production = os.getenv("RENDER") or os.getenv("ENVIRONMENT") == "production"
    base_url = (
        os.getenv("RENDER_EXTERNAL_URL", "https://data-assistant-hj5f.onrender.com")
        if is_production
        else f"http://localhost:{int(os.getenv('PORT', 8000))}"
    )
    return {
        "mcp_mounted": mcp_available,
        "endpoint": "/data/mcp",
        "url": f"{base_url}/data/mcp",
    }


@app.get("/api/debug/mcp-state")
async def debug_mcp_state():
    """
    Shows every prompt, resource-template, and tool registered on the shared
    FastMCP instance.

    Resources with URI templates (e.g. session://{session_id}/…) appear under
    'resource_templates', NOT 'resources' — this is correct FastMCP 2.x behaviour.
    The MCP Inspector surfaces them via list_resource_templates, not list_resources.
    If 'prompts' is empty here, restart the server so the side-effect imports fire.
    """
    return {
        "mcp_available": mcp_available,
        "tools": list(mcp._tool_manager._tools.keys()),
        "prompts": list(mcp._prompt_manager._prompts.keys()),
        "resource_templates": list(mcp._resource_manager._templates.keys()),
        "resources_static": list(mcp._resource_manager._resources.keys()),
    }

# =============================================================================
# Routes — ingestion config
# =============================================================================

@app.get("/api/ingestion/config")
async def get_config():
    if IngestionConfig:
        return {
            "max_file_size_mb": IngestionConfig.MAX_FILE_SIZE / (1024 * 1024),
            "supported_formats": {k: list(v) for k, v in IngestionConfig.FILE_TYPES.items()},
            "max_tables_per_file": IngestionConfig.MAX_TABLES_PER_FILE,
        }
    return {
        "max_file_size_mb": 100,
        "supported_formats": {"csv": [".csv"], "excel": [".xlsx", ".xls"]},
        "max_tables_per_file": 10,
    }

# =============================================================================
# Routes — ingestion
# =============================================================================

@app.post("/api/ingestion/file-upload")
@observe(name="api_file_upload", as_type="span")
async def file_upload(
    file: UploadFile = File(...),
    file_type: Optional[str] = Form(None),
    session_id: Optional[str] = Form(None),
):
    file_content = await file.read()
    file_size = len(file_content)

    if IngestionConfig and file_size > IngestionConfig.MAX_FILE_SIZE:
        max_mb = IngestionConfig.MAX_FILE_SIZE / (1024 * 1024)
        raise HTTPException(
            status_code=413,
            detail=f"File size ({file_size / (1024 * 1024):.2f}MB) exceeds maximum ({max_mb}MB)",
        )
    if file_size < 1:
        raise HTTPException(status_code=400, detail="File is empty")

    session_id = _generate_session_id(session_id)
    temp_file_path = os.path.join(_get_temp_dir(), f"{session_id}_{file.filename}")

    with open(temp_file_path, "wb") as f:
        f.write(file_content)

    result = get_default_handler().process_file(temp_file_path, file_type, file.content_type)
    response_data = _build_response_and_store(session_id, result, file.filename, source="file_upload")

    if os.path.exists(temp_file_path):
        os.remove(temp_file_path)

    return JSONResponse(content=response_data)



# =============================================================================
# Routes — session management
# =============================================================================

@app.get("/api/sessions")
async def get_all_sessions():
    sessions = get_default_store().list_sessions()
    return JSONResponse(content={"success": True, "count": len(sessions), "sessions": sessions})


@app.get("/api/session/{session_id}/tables")
async def get_session_tables(
    session_id: str,
    format: str = Query("summary", pattern="^(summary|full)$"),
):
    store = get_default_store()
    tables = store.load_session(session_id)
    if tables is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")

    store.extend_ttl(session_id)

    if format == "full":
        # T-5: Arrow IPC for the body (with pickle fallback inside encode_df)
        # gives us a versioned wire format the client can decode either way.
        table_list = []
        for name, df in tables.items():
            table_list.append({
                "table_name": name,
                "data": encode_df(df),
                "row_count": len(df),
                "column_count": len(df.columns),
                "columns": list(df.columns),
                "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
            })
        return JSONResponse(content={
            "session_id": session_id,
            "table_count": len(tables),
            "tables": table_list,
        })

    tables_summary = {
        name: {
            "row_count": len(df),
            "column_count": len(df.columns),
            "columns": list(df.columns),
            "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
            "preview": df.head(10).to_dict(orient="records"),
        }
        for name, df in tables.items()
    }
    return JSONResponse(content={
        "session_id": session_id,
        "table_count": len(tables),
        "tables": tables_summary,
    })


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

    tables_dict: Dict[str, Any] = {}
    for table_name, table_info in tables_data.items():
        base64_data = table_info.get("data")
        if not base64_data:
            raise HTTPException(status_code=400, detail=f"Missing data for table '{table_name}'")
        # T-5: decode_df sniffs the AR1:/PK1:/legacy prefix and dispatches.
        df = decode_df(base64_data)
        if not isinstance(df, pd.DataFrame):
            raise ValueError(f"Deserialized data for table '{table_name}' is not a DataFrame")
        tables_dict[table_name] = df

    updated_metadata = {
        **(store.get_metadata(session_id) or {}),
        **metadata_updates,
        "last_updated": time.time(),
        "updated_by": "mcp_server",
    }

    if store.save_session(session_id, tables_dict, updated_metadata):
        store.extend_ttl(session_id)
        return JSONResponse(content={
            "success": True,
            "message": f"Session '{session_id}' updated successfully",
            "table_count": len(tables_dict),
            "tables_updated": list(tables_dict.keys()),
        })
    raise HTTPException(status_code=500, detail="Failed to save session to Redis")


@app.delete("/api/session/{session_id}")
async def delete_session_endpoint(session_id: str):
    store = get_default_store()
    if not store.session_exists(session_id):
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    if store.delete_session(session_id):
        return JSONResponse(content={
            "success": True,
            "message": f"Session '{session_id}' deleted successfully",
        })
    raise HTTPException(status_code=500, detail="Failed to delete session")


@app.post("/api/session/{session_id}/extend")
async def extend_session_ttl(session_id: str):
    store = get_default_store()
    if not store.session_exists(session_id):
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    if store.extend_ttl(session_id):
        return JSONResponse(content={
            "success": True,
            "message": f"Session '{session_id}' TTL extended",
        })
    raise HTTPException(status_code=500, detail="Failed to extend TTL")

# =============================================================================
# Routes — version management
# =============================================================================

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
    tables_summary = {
        name: {
            "row_count": len(df),
            "column_count": len(df.columns),
            "columns": list(df.columns),
            "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
            "preview": df.head(10).to_dict(orient="records"),
        }
        for name, df in tables.items()
    }
    return JSONResponse(content={
        "session_id": session_id,
        "version_id": version_id,
        "table_count": len(tables),
        "tables": tables_summary,
    })


@app.post("/api/session/{session_id}/branch")
async def create_branch(session_id: str, request_data: Dict[str, Any]):
    """
    Benchmark: < 0.5 s total.
    redis.restore_copy (Redis COPY) should be < 0.1 s.
    Fallback (load_version + save_session) can reach 1–3 s for large tables.
    """
    store = get_default_store()
    if not store.session_exists(session_id):
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")

    version_id = request_data.get("version_id")
    if not version_id:
        raise HTTPException(status_code=400, detail="version_id is required")

    _t0 = time.perf_counter()
    logger.info(
        "[PERF] api.branch START  session=%s  target_version=%s",
        session_id, version_id,
    )

    # ── restore version → current session ────────────────────────────────────
    _t_restore = time.perf_counter()
    ok = store.restore_version_as_session(session_id, version_id)
    _t_restore_elapsed = time.perf_counter() - _t_restore
    logger.info(
        "[PERF] api.branch.restore  session=%s  version=%s  duration=%.3fs  ok=%s",
        session_id, version_id, _t_restore_elapsed, ok,
    )
    _perf_warn("api.branch.restore", _t_restore_elapsed, session_id)

    if not ok:
        raise HTTPException(status_code=404, detail=f"Version '{version_id}' not found or restore failed")

    store.set_current_version(session_id, version_id)
    store.extend_ttl(session_id)

    _t_total = time.perf_counter() - _t0
    logger.info(
        "[PERF] api.branch END  session=%s  version=%s  restore=%.3fs  total=%.3fs",
        session_id, version_id, _t_restore_elapsed, _t_total,
    )
    _perf_warn("api.branch", _t_total, session_id)

    return JSONResponse(content={
        "success": True,
        "message": f"Branched to {version_id}",
        "version_id": version_id,
    })


@app.post("/api/session/{session_id}/save_version")
async def save_version_endpoint(session_id: str, request_data: Dict[str, Any]):
    """
    Benchmark: < 1.0 s total.
    snapshot (Redis COPY) < 0.1 s; update_graph < 0.5 s.
    """
    store = get_default_store()
    if not store.session_exists(session_id):
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")

    version_id = request_data.get("version_id")
    operation = request_data.get("operation", "Operation")
    query = request_data.get("query")

    if not version_id:
        raise HTTPException(status_code=400, detail="version_id is required")

    _t0 = time.perf_counter()
    logger.info(
        "[PERF] api.save_version START  session=%s  version=%s",
        session_id, version_id,
    )

    current_vid = store.get_current_version(session_id) or "v0"

    # ── snapshot ──────────────────────────────────────────────────────────────
    _t_snap = time.perf_counter()
    snap_ok = store.snapshot_session_as_version(session_id, version_id)
    _t_snap_elapsed = time.perf_counter() - _t_snap
    logger.info(
        "[PERF] api.save_version.snapshot  session=%s  version=%s  duration=%.3fs  ok=%s",
        session_id, version_id, _t_snap_elapsed, snap_ok,
    )
    _perf_warn("api.save_version.snapshot", _t_snap_elapsed, session_id)

    if snap_ok:
        # ── graph update ──────────────────────────────────────────────────────
        _t_graph = time.perf_counter()
        store.update_graph(
            session_id, parent_vid=current_vid, new_vid=version_id,
            operation=operation, query=query,
        )
        _t_graph_elapsed = time.perf_counter() - _t_graph
        logger.info(
            "[PERF] api.save_version.update_graph  session=%s  version=%s  duration=%.3fs",
            session_id, version_id, _t_graph_elapsed,
        )
        _perf_warn("api.save_version.update_graph", _t_graph_elapsed, session_id)

        store.set_current_version(session_id, version_id)
        store.extend_ttl(session_id)

        _t_total = time.perf_counter() - _t0
        logger.info(
            "[PERF] api.save_version END  session=%s  version=%s  "
            "snapshot=%.3fs  graph=%.3fs  total=%.3fs",
            session_id, version_id, _t_snap_elapsed, _t_graph_elapsed, _t_total,
        )
        _perf_warn("api.save_version", _t_total, session_id)

        return JSONResponse(content={
            "success": True,
            "message": f"Version {version_id} saved",
            "version_id": version_id,
        })
    raise HTTPException(status_code=500, detail="Failed to save version")


@app.delete("/api/session/{session_id}/version/{version_id}")
async def delete_version_endpoint(session_id: str, version_id: str):
    store = get_default_store()
    if not store.session_exists(session_id):
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")

    if not store.delete_version(session_id, version_id):
        raise HTTPException(status_code=404, detail=f"Version '{version_id}' not found")

    graph = store.get_graph(session_id)
    graph["nodes"] = [n for n in graph["nodes"] if n["id"] != version_id]
    graph["edges"] = [
        e for e in graph["edges"]
        if e["from"] != version_id and e["to"] != version_id
    ]
    if store.redis:
        key = KEY_SESSION_GRAPH.format(sid=session_id)
        store.redis.setex(key, store.session_ttl, json.dumps(graph))

    return JSONResponse(content={"success": True, "message": f"Version {version_id} deleted"})


@app.post("/api/session/{session_id}/prune_versions")
async def prune_versions_endpoint(
    session_id: str,
    request_data: Optional[Dict[str, Any]] = None,
):
    store = get_default_store()
    if not store.session_exists(session_id):
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")

    keep_last_n = request_data.get("keep_last_n") if request_data else None
    if keep_last_n is None:
        return JSONResponse(content={
            "success": True,
            "message": "No pruning limit specified, keeping all versions",
        })

    graph = store.get_graph(session_id)
    nodes = graph.get("nodes", [])

    if len(nodes) <= keep_last_n:
        return JSONResponse(content={
            "success": True,
            "message": f"Only {len(nodes)} versions exist, no pruning needed",
        })

    nodes_sorted = sorted(nodes, key=lambda n: n.get("timestamp", 0), reverse=True)
    to_keep  = {n["id"] for n in nodes_sorted[:keep_last_n]}
    to_delete = [n["id"] for n in nodes_sorted[keep_last_n:]]

    deleted_count = sum(1 for vid in to_delete if store.delete_version(session_id, vid))

    graph["nodes"] = [n for n in nodes if n["id"] in to_keep]
    graph["edges"] = [
        e for e in graph["edges"]
        if e["from"] in to_keep and e["to"] in to_keep
    ]
    if store.redis:
        key = KEY_SESSION_GRAPH.format(sid=session_id)
        store.redis.setex(key, store.session_ttl, json.dumps(graph))

    return JSONResponse(content={
        "success": True,
        "message": f"Pruned {deleted_count} versions, kept {len(to_keep)}",
        "deleted_count": deleted_count,
        "kept_count": len(to_keep),
    })

# =============================================================================
# Entry point
# =============================================================================

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    print(f"Starting server on 0.0.0.0:{port}")
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False, log_level="info")
