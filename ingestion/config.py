"""Configuration settings for the ingestion module."""

import os
from typing import Dict
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


class IngestionConfig:
    """Centralized configuration for ingestion module."""
    
    # Environment Variables
    MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", 100 * 1024 * 1024))
    TEMP_DIR = os.getenv("TEMP_DIR", "/tmp/data-assistant")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL_NAME = os.getenv("GEMINI_MODEL_NAME", "gemini-2.5-flash")
    MAX_TABLES_PER_FILE = 100
    
    # File Type Mappings
    FILE_TYPES = {
        "csv": {".csv", ".tsv"},
        "excel": {".xlsx", ".xls", ".xlsm"},
        "pdf": {".pdf"},
        "image": {".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp"}
    }
    MIME_TYPES = {
        "csv": {"text/csv", "text/plain", "application/csv"},
        "excel": {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "application/vnd.ms-excel", "application/excel"},
        "pdf": {"application/pdf"},
        "image": {"image/png", "image/jpeg", "image/tiff", "image/bmp"}
    }
    
    # Processing Options
    CSV_ENCODINGS = ["utf-8", "latin-1", "iso-8859-1", "cp1252"]
    CSV_DELIMITERS = [",", ";", "\t", "|"]
    CSV_SAMPLE_SIZE = 1000
    EXCEL_ENGINE = "openpyxl"
    EXCEL_HEADER_ROW = 0
    
    # Error Messages
    ERROR_UNSUPPORTED_TYPE = "Unsupported file type: {file_type}"
    ERROR_NO_TABLES_FOUND = "No tables found in file"
    
    @classmethod
    def get_file_type(cls, file_path: str, mime_type: str = None) -> str:
        """Determine file type from extension and MIME type."""
        ext = Path(file_path).suffix.lower()
        for file_type, extensions in cls.FILE_TYPES.items():
            if ext in extensions:
                return file_type
        if mime_type:
            for file_type, mimes in cls.MIME_TYPES.items():
                if mime_type in mimes:
                    return file_type
        return "unknown"
    
    @classmethod
    def validate_file(cls, file_path: str) -> Dict:
        """Validate file before processing."""
        if not os.path.exists(file_path):
            return {"valid": False, "error": f"File not found: {file_path}"}
        
        size = os.path.getsize(file_path)
        if size < 1:
            return {"valid": False, "error": "File is empty or too small"}
        if size > cls.MAX_FILE_SIZE:
            return {"valid": False, "error": f"File size exceeds maximum allowed size of {cls.MAX_FILE_SIZE / (1024*1024)}MB"}
        
        return {"valid": True, "error": None}
    
    @classmethod
    def ensure_temp_dir(cls) -> str:
        """Ensure temporary directory exists and return its path."""
        Path(cls.TEMP_DIR).mkdir(parents=True, exist_ok=True)
        return cls.TEMP_DIR
