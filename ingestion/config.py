"""
Configuration settings for the ingestion module.
Handles all environment variables, file type mappings, and processing parameters.
"""

import os
from typing import Dict, List
from pathlib import Path


class IngestionConfig:
    """Centralized configuration for ingestion module."""
    
    # Environment Variables
    DOCLING_API_KEY: str = os.getenv("DOCLING_API_KEY", "")
    MAX_FILE_SIZE: int = int(os.getenv("MAX_FILE_SIZE", 100 * 1024 * 1024))  # 100MB default
    TEMP_DIR: str = os.getenv("TEMP_DIR", "/tmp/data-assistant")
    
    # File Type Mappings
    CSV_EXTENSIONS: List[str] = [".csv", ".tsv"]
    EXCEL_EXTENSIONS: List[str] = [".xlsx", ".xls", ".xlsm"]
    PDF_EXTENSIONS: List[str] = [".pdf"]
    IMAGE_EXTENSIONS: List[str] = [".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp"]
    
    # MIME Types
    CSV_MIME_TYPES: List[str] = [
        "text/csv",
        "text/plain",
        "application/csv"
    ]
    EXCEL_MIME_TYPES: List[str] = [
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-excel",
        "application/excel"
    ]
    PDF_MIME_TYPES: List[str] = ["application/pdf"]
    IMAGE_MIME_TYPES: List[str] = [
        "image/png",
        "image/jpeg",
        "image/tiff",
        "image/bmp"
    ]
    
    # Docling Configuration
    DOCLING_OCR_ENABLED: bool = True
    DOCLING_TABLE_EXTRACTION_MODE: str = "auto"  # auto, structured, unstructured
    DOCLING_LAYOUT_PRESERVATION: bool = True
    DOCLING_MIN_TABLE_CONFIDENCE: float = 0.5
    
    # Pandas Read Options
    CSV_ENCODINGS: List[str] = ["utf-8", "latin-1", "iso-8859-1", "cp1252"]
    CSV_DELIMITERS: List[str] = [",", ";", "\t", "|"]
    CSV_SAMPLE_SIZE: int = 1000  # Rows to sample for auto-detection
    
    # Excel Read Options
    EXCEL_ENGINE: str = "openpyxl"  # or "xlrd" for .xls
    EXCEL_SHEET_NAME: str = None  # None = all sheets
    EXCEL_HEADER_ROW: int = 0  # 0-based index
    
    # Error Messages
    ERROR_FILE_TOO_LARGE: str = "File size exceeds maximum allowed size of {max_size}MB"
    ERROR_UNSUPPORTED_TYPE: str = "Unsupported file type: {file_type}"
    ERROR_FILE_NOT_FOUND: str = "File not found: {file_path}"
    ERROR_PROCESSING_FAILED: str = "Failed to process file: {error}"
    ERROR_NO_TABLES_FOUND: str = "No tables found in file"
    
    # Validation Rules
    MIN_FILE_SIZE: int = 1  # 1 byte minimum
    MAX_TABLES_PER_FILE: int = 100  # Prevent processing too many tables
    
    @classmethod
    def get_file_type(cls, file_path: str, mime_type: str = None) -> str:
        """
        Determine file type from extension and MIME type.
        
        Args:
            file_path: Path to the file
            mime_type: Optional MIME type string
            
        Returns:
            File type: 'csv', 'excel', 'pdf', 'image', or 'unknown'
        """
        path = Path(file_path)
        extension = path.suffix.lower()
        
        # Check by extension first
        if extension in cls.CSV_EXTENSIONS:
            return "csv"
        elif extension in cls.EXCEL_EXTENSIONS:
            return "excel"
        elif extension in cls.PDF_EXTENSIONS:
            return "pdf"
        elif extension in cls.IMAGE_EXTENSIONS:
            return "image"
        
        # Check by MIME type if provided
        if mime_type:
            if mime_type in cls.CSV_MIME_TYPES:
                return "csv"
            elif mime_type in cls.EXCEL_MIME_TYPES:
                return "excel"
            elif mime_type in cls.PDF_MIME_TYPES:
                return "pdf"
            elif mime_type in cls.IMAGE_MIME_TYPES:
                return "image"
        
        return "unknown"
    
    @classmethod
    def validate_file(cls, file_path: str) -> Dict[str, any]:
        """
        Validate file before processing.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Dict with 'valid' (bool) and 'error' (str) keys
        """
        if not os.path.exists(file_path):
            return {
                "valid": False,
                "error": cls.ERROR_FILE_NOT_FOUND.format(file_path=file_path)
            }
        
        file_size = os.path.getsize(file_path)
        
        if file_size < cls.MIN_FILE_SIZE:
            return {
                "valid": False,
                "error": "File is empty or too small"
            }
        
        if file_size > cls.MAX_FILE_SIZE:
            max_mb = cls.MAX_FILE_SIZE / (1024 * 1024)
            return {
                "valid": False,
                "error": cls.ERROR_FILE_TOO_LARGE.format(max_size=max_mb)
            }
        
        return {"valid": True, "error": None}
    
    @classmethod
    def ensure_temp_dir(cls) -> str:
        """Ensure temporary directory exists and return its path."""
        Path(cls.TEMP_DIR).mkdir(parents=True, exist_ok=True)
        return cls.TEMP_DIR

