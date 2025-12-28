"""
FastAPI application with endpoints for file ingestion.
Main entry point for the Data Analyst Platform ingestion service.
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
from redis_db.redis_store import (
    save_session_tables,
    load_session_tables,
    delete_session,
    get_session_metadata,
    session_exists,
    create_empty_session,
    extend_session_ttl,
    list_active_sessions
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
    description="API for ingesting and processing data files (CSV, Excel, PDF, Images)",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
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
        "endpoints": {
            "file_upload": "/api/ingestion/file-upload",
            "health": "/health",
            "config": "/api/ingestion/config",
            "create_session": "/api/session/create",
            "session_tables": "/api/session/{session_id}/tables",
            "session_metadata": "/api/session/{session_id}/metadata",
            "extend_session": "/api/session/{session_id}/extend",
            "list_sessions": "/api/session/list",
            "delete_session": "/api/session/{session_id}"
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "ingestion-api"
    }


@app.post("/api/ingestion/file-upload")
async def file_upload(
    file: UploadFile = File(...),
    file_type: Optional[str] = Form(None),
    session_id: Optional[str] = Form(None)
):
    """Upload and process a file (CSV, Excel, PDF, or Image)."""
    temp_file_path = None
    
    try:
        file_content = await file.read()
        file_size = len(file_content)
        
        if file_size > IngestionConfig.MAX_FILE_SIZE:
            max_mb = IngestionConfig.MAX_FILE_SIZE / (1024 * 1024)
            raise HTTPException(status_code=413, 
                              detail=f"File size ({file_size / (1024 * 1024):.2f}MB) exceeds maximum ({max_mb}MB)")
        
        if file_size < 1:
            raise HTTPException(status_code=400, detail="File is empty or too small")
        
        IngestionConfig.ensure_temp_dir()
        temp_file_path = os.path.join(IngestionConfig.TEMP_DIR, f"{session_id or 'temp'}_{file.filename}")
        
        with open(temp_file_path, "wb") as f:
            f.write(file_content)
        
        logger.info(f"Uploaded: {file.filename} ({file_size} bytes)")
        
        # Generate session_id if not provided, or create empty session if provided but doesn't exist
        if not session_id:
            session_id = str(uuid.uuid4())
            logger.info(f"Generated new session_id: {session_id}")
        elif not session_exists(session_id):
            # Session ID provided but doesn't exist - create empty session first
            logger.info(f"Creating new session {session_id} as it doesn't exist")
            create_empty_session(session_id, {
                "file_name": file.filename,
                "created_via": "file_upload"
            })
        
        result = process_file(temp_file_path, file_type, file.content_type)
        
        response_data = {
            "success": result["success"],
            "metadata": result["metadata"],
            "tables": [{
                "table_index": idx,
                "row_count": len(df),
                "column_count": len(df.columns),
                "columns": list(df.columns),
                "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
                "preview": df.head(10).to_dict(orient="records"),
                "attributes": dict(df.attrs) if hasattr(df, 'attrs') else {}
            } for idx, df in enumerate(result["tables"])]
        }
        
        # Save to Redis if ingestion was successful
        if result["success"] and result["tables"]:
            try:
                # Create tables dictionary with smart naming
                tables_dict = {}
                for idx, df in enumerate(result["tables"]):
                    # Use sheet_name from attrs if available, otherwise use table_0, table_1, etc.
                    if hasattr(df, 'attrs') and 'sheet_name' in df.attrs:
                        table_name = df.attrs['sheet_name']
                    elif len(result["tables"]) == 1:
                        table_name = "current"
                    else:
                        table_name = f"table_{idx}"
                    
                    tables_dict[table_name] = df
                
                # Enhanced metadata with session info
                enhanced_metadata = {
                    **result["metadata"],
                    "session_id": session_id,
                    "file_name": file.filename,
                    "table_count": len(tables_dict),
                    "table_names": list(tables_dict.keys())
                }
                
                # Save to Redis
                if save_session_tables(session_id, tables_dict, enhanced_metadata):
                    logger.info(f"Saved {len(tables_dict)} tables to Redis for session {session_id}")
                    response_data["session_id"] = session_id
                    response_data["redis_stored"] = True
                    # Extend TTL on successful save (sliding window)
                    extend_session_ttl(session_id)
                else:
                    logger.warning(f"Failed to save session {session_id} to Redis")
                    response_data["redis_stored"] = False
                    
            except Exception as e:
                logger.error(f"Error saving to Redis: {e}", exc_info=True)
                response_data["redis_stored"] = False
                # Don't fail the request if Redis save fails
        else:
            response_data["session_id"] = session_id
        
        return JSONResponse(content=response_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing file: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to process file: {e}")
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except Exception as e:
                logger.warning(f"Failed to remove temp file: {e}")


@app.get("/api/ingestion/config")
async def get_config():
    """
    Get current ingestion configuration (without sensitive data).
    
    Returns:
        Configuration information
    """
    return {
        "max_file_size_mb": IngestionConfig.MAX_FILE_SIZE / (1024 * 1024),
        "supported_formats": {k: list(v) for k, v in IngestionConfig.FILE_TYPES.items()},
        "max_tables_per_file": IngestionConfig.MAX_TABLES_PER_FILE
    }


# ============================================================================
# Session Management Endpoints
# ============================================================================

@app.post("/api/session/create")
async def create_session(session_id: Optional[str] = Form(None)):
    """
    Create a new empty session.
    
    Args:
        session_id: Optional session identifier (UUID generated if not provided)
        
    Returns:
        Dictionary with session_id and creation status
    """
    try:
        # Generate session_id if not provided
        if not session_id:
            session_id = str(uuid.uuid4())
            logger.info(f"Generated new session_id: {session_id}")
        
        # Check if session already exists
        if session_exists(session_id):
            return JSONResponse(
                status_code=409,
                content={
                    "success": False,
                    "error": f"Session '{session_id}' already exists",
                    "session_id": session_id
                }
            )
        
        # Create empty session
        metadata = {
            "created_at": time.time(),
            "created_via": "api",
            "table_count": 0,
            "table_names": []
        }
        
        if create_empty_session(session_id, metadata):
            return JSONResponse(content={
                "success": True,
                "session_id": session_id,
                "message": f"Session '{session_id}' created successfully",
                "metadata": metadata
            })
        else:
            raise HTTPException(status_code=500, detail="Failed to create session")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating session: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create session: {str(e)}")


@app.get("/api/session/list")
async def list_sessions():
    """
    List all active sessions.
    
    Returns:
        List of active sessions with their metadata
    """
    try:
        sessions = list_active_sessions()
        return JSONResponse(content={
            "success": True,
            "count": len(sessions),
            "sessions": sessions
        })
        
    except Exception as e:
        logger.error(f"Error listing sessions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list sessions: {str(e)}")


@app.get("/api/session/{session_id}/tables")
async def get_session_tables(session_id: str):
    """
    Get preview of all tables in a session.
    
    Args:
        session_id: Unique session identifier
        
    Returns:
        Dictionary mapping table names to preview data (first 10 rows)
    """
    try:
        tables = load_session_tables(session_id)
        if not tables:
            raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
        
        # Extend TTL on access (sliding window)
        extend_session_ttl(session_id)
        
        response = {
            "session_id": session_id,
            "table_count": len(tables),
            "tables": {
                name: {
                    "row_count": len(df),
                    "column_count": len(df.columns),
                    "columns": list(df.columns),
                    "preview": df.head(10).to_dict(orient="records")
                }
                for name, df in tables.items()
            }
        }
        return JSONResponse(content=response)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error loading session tables: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to load session tables: {str(e)}")


@app.get("/api/session/{session_id}/metadata")
async def get_session_metadata_endpoint(session_id: str):
    """
    Get metadata for a session.
    
    Args:
        session_id: Unique session identifier
        
    Returns:
        Session metadata dictionary
    """
    try:
        metadata = get_session_metadata(session_id)
        if not metadata:
            raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
        
        # Extend TTL on access (sliding window)
        extend_session_ttl(session_id)
        
        return JSONResponse(content={
            "session_id": session_id,
            "metadata": metadata
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error loading session metadata: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to load session metadata: {str(e)}")


@app.post("/api/session/{session_id}/extend")
async def extend_session(session_id: str):
    """
    Extend session TTL (sliding window - resets expiration time).
    
    Args:
        session_id: Unique session identifier
        
    Returns:
        Success message with new expiration info
    """
    try:
        if not session_exists(session_id):
            raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
        
        if extend_session_ttl(session_id):
            return JSONResponse(content={
                "success": True,
                "session_id": session_id,
                "message": f"Session '{session_id}' TTL extended successfully"
            })
        else:
            raise HTTPException(status_code=500, detail="Failed to extend session TTL")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error extending session: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to extend session: {str(e)}")


@app.delete("/api/session/{session_id}")
async def drop_session(session_id: str):
    """
    Manually delete a session and all its data.
    
    Args:
        session_id: Unique session identifier
        
    Returns:
        Success message
    """
    try:
        if delete_session(session_id):
            return JSONResponse(content={
                "success": True,
                "message": f"Session '{session_id}' deleted successfully"
            })
        else:
            raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found or already deleted")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting session: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to delete session: {str(e)}")


if __name__ == "__main__":
    # Run the FastAPI application
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=True
    )

