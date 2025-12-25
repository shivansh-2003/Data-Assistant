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
from typing import Optional

from ingestion.ingestion_handler import process_file
from ingestion.config import IngestionConfig

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
            "config": "/api/ingestion/config"
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
        
        if file_size < IngestionConfig.MIN_FILE_SIZE:
            raise HTTPException(status_code=400, detail="File is empty or too small")
        
        IngestionConfig.ensure_temp_dir()
        temp_file_path = os.path.join(IngestionConfig.TEMP_DIR, f"{session_id or 'temp'}_{file.filename}")
        
        with open(temp_file_path, "wb") as f:
            f.write(file_content)
        
        logger.info(f"Uploaded: {file.filename} ({file_size} bytes)")
        
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
        
        if session_id:
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
        "supported_formats": {
            "csv": IngestionConfig.CSV_EXTENSIONS,
            "excel": IngestionConfig.EXCEL_EXTENSIONS,
            "pdf": IngestionConfig.PDF_EXTENSIONS,
            "image": IngestionConfig.IMAGE_EXTENSIONS
        },
        "docling_enabled": IngestionConfig.DOCLING_API_KEY != "",
        "max_tables_per_file": IngestionConfig.MAX_TABLES_PER_FILE
    }


if __name__ == "__main__":
    # Run the FastAPI application
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=True
    )

