"""
FastAPI application with endpoints for file ingestion and session management.
Stores processed DataFrames in Upstash Redis with automatic TTL expiration.
"""

from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import logging
import os
import uuid
import time
from typing import Optional

from ingestion.ingestion_handler import process_file
from ingestion.config import IngestionConfig
from redis_db import (
    save_session,
    load_session,
    delete_session,
    get_metadata,
    session_exists,
    extend_ttl,
    list_sessions,
    is_connected
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Data Analyst Platform - Ingestion API",
    description="API for ingesting files and managing session data in Redis",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "message": "Data Analyst Platform - Ingestion API",
        "version": "1.0.0",
        "redis_connected": is_connected(),
        "endpoints": {
            "file_upload": "/api/ingestion/file-upload",
            "health": "/health",
            "session_create": "POST /api/session/{session_id}/upload",
            "session_tables": "GET /api/session/{session_id}/tables",
            "session_metadata": "GET /api/session/{session_id}/metadata",
            "session_delete": "DELETE /api/session/{session_id}",
            "session_list": "GET /api/sessions"
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "ingestion-api",
        "redis_connected": is_connected()
    }


# ============================================================================
# File Upload & Session Creation
# ============================================================================

@app.post("/api/ingestion/file-upload")
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
        
        if file_size > IngestionConfig.MAX_FILE_SIZE:
            max_mb = IngestionConfig.MAX_FILE_SIZE / (1024 * 1024)
            raise HTTPException(
                status_code=413,
                detail=f"File size ({file_size / (1024 * 1024):.2f}MB) exceeds maximum ({max_mb}MB)"
            )
        
        if file_size < 1:
            raise HTTPException(status_code=400, detail="File is empty")
        
        # Generate session_id if not provided or if placeholder value
        if not session_id or session_id.lower() == "string":
            session_id = str(uuid.uuid4())
        
        # Save temp file
        IngestionConfig.ensure_temp_dir()
        temp_file_path = os.path.join(IngestionConfig.TEMP_DIR, f"{session_id}_{file.filename}")
        
        with open(temp_file_path, "wb") as f:
            f.write(file_content)
        
        logger.info(f"Processing file: {file.filename} ({file_size} bytes)")
        
        # Process file using ingestion handler
        result = process_file(temp_file_path, file_type, file.content_type)
        
        # Build response
        response_data = {
            "success": result["success"],
            "session_id": session_id,
            "metadata": result["metadata"],
            "tables": []
        }
        
        # If processing successful, store in Redis
        if result["success"] and result["tables"]:
            # Create tables dictionary with naming
            tables_dict = {}
            for idx, df in enumerate(result["tables"]):
                # Use sheet_name from attrs if available
                if hasattr(df, 'attrs') and 'sheet_name' in df.attrs:
                    table_name = df.attrs['sheet_name']
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
            
            # Save to Redis
            session_metadata = {
                "file_name": file.filename,
                "file_type": result["metadata"]["file_type"],
                "table_count": len(tables_dict),
                "table_names": list(tables_dict.keys()),
                "created_at": time.time(),
                "processing_time": result["metadata"]["processing_time"]
            }
            
            if save_session(session_id, tables_dict, session_metadata):
                response_data["redis_stored"] = True
                logger.info(f"Session {session_id} stored in Redis with {len(tables_dict)} tables")
            else:
                response_data["redis_stored"] = False
                logger.warning(f"Failed to store session {session_id} in Redis")
        
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


# ============================================================================
# Session Management Endpoints
# ============================================================================

@app.get("/api/sessions")
async def get_all_sessions():
    """List all active sessions in Redis."""
    try:
        sessions = list_sessions()
        return JSONResponse(content={
            "success": True,
            "count": len(sessions),
            "sessions": sessions
        })
    except Exception as e:
        logger.error(f"Error listing sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/session/{session_id}/tables")
async def get_session_tables(session_id: str):
    """
    Get all tables from a session.
    Extends session TTL on access.
    """
    try:
        tables = load_session(session_id)
        
        if tables is None:
            raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
        
        # Extend TTL on access
        extend_ttl(session_id)
        
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
        metadata = get_metadata(session_id)
        
        if metadata is None:
            raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
        
        # Extend TTL on access
        extend_ttl(session_id)
        
        return JSONResponse(content={
            "session_id": session_id,
            "metadata": metadata
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting metadata: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/session/{session_id}")
async def delete_session_endpoint(session_id: str):
    """
    Delete a session and wipe all its data from Redis.
    """
    try:
        if not session_exists(session_id):
            raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
        
        if delete_session(session_id):
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
        if not session_exists(session_id):
            raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
        
        if extend_ttl(session_id):
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
    return {
        "max_file_size_mb": IngestionConfig.MAX_FILE_SIZE / (1024 * 1024),
        "supported_formats": {k: list(v) for k, v in IngestionConfig.FILE_TYPES.items()},
        "max_tables_per_file": IngestionConfig.MAX_TABLES_PER_FILE
    }


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
