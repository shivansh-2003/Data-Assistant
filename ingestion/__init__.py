"""
Ingestion module for processing various file formats (CSV, Excel, Images).
Provides unified interface for table extraction and data ingestion.
"""

from typing import Optional, List

from .ingestion_handler import IngestionHandler
from .image_handler import ImageHandler
from .config import IngestionConfig

# Create default instances for backward compatibility
_default_handler = IngestionHandler()

# Backward compatibility functions (using default instances)
def process_file(file_path: str, file_type: Optional[str] = None, 
                 mime_type: Optional[str] = None):
    """Process a file and return results. Uses default IngestionHandler instance."""
    return _default_handler.process_file(file_path, file_type, mime_type)

def process_files(file_paths: List[str], file_types: Optional[List[str]] = None):
    """Process multiple files. Uses default IngestionHandler instance."""
    return _default_handler.process_files(file_paths, file_types)

# Export individual handlers for direct access if needed
from .csv_handler import process_csv
from .excel_handler import process_excel

# Backward compatibility for image handler
_default_image_handler = ImageHandler()
def process_image(file_path: str):
    """Process an image file. Uses default ImageHandler instance."""
    return _default_image_handler.process_image(file_path)

__version__ = "1.0.0"

__all__ = [
    "IngestionHandler",
    "ImageHandler",
    "process_file",
    "process_files",
    "IngestionConfig",
    "process_csv",
    "process_excel",
    "process_image"
]
