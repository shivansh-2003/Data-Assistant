"""
Ingestion module for processing various file formats (CSV, Excel, PDF, Images).
Provides unified interface for table extraction and data ingestion.
"""

from .ingestion_handler import process_file, process_files
from .config import IngestionConfig

# Export individual handlers for direct access if needed
from .csv_handler import process_csv
from .excel_handler import process_excel
from .image_handler import process_image
from .pdf_handler import process_pdf

__version__ = "1.0.0"

__all__ = [
    "process_file",
    "process_files",
    "IngestionConfig",
    "process_csv",
    "process_excel",
    "process_image",
    "process_pdf"
]

