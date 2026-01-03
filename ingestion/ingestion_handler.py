"""Main ingestion handler providing unified interface for all file types."""

import time
import logging
from typing import Dict, List, Optional, Callable
from .csv_handler import process_csv
from .excel_handler import process_excel
from .image_handler import ImageHandler
from .pdf_handler import process_pdf
from .config import IngestionConfig

logger = logging.getLogger(__name__)


class IngestionHandler:
    """Main handler for processing various file types and extracting tables."""
    
    def __init__(
        self,
        image_handler: Optional[ImageHandler] = None
    ):
        """
        Initialize IngestionHandler.
        
        Args:
            image_handler: Optional ImageHandler instance (creates default if None)
        """
        self.logger = logging.getLogger(__name__)
        self.image_handler = image_handler or ImageHandler()
        
        # Register handlers
        self._handlers: Dict[str, Callable] = {
            "csv": process_csv,
            "excel": process_excel,
            "image": self.image_handler.process_image,
            "pdf": process_pdf
        }
    
    def _error_result(
        self,
        file_type: str,
        processing_time: float,
        file_path: str,
        errors: List[str]
    ) -> Dict:
        """
        Helper to create error result dictionary.
        
        Args:
            file_type: Detected file type
            processing_time: Time taken to process
            file_path: Path to the file
            errors: List of error messages
            
        Returns:
            Error result dictionary
        """
        return {
            "success": False,
            "tables": [],
            "metadata": {
                "file_type": file_type,
                "table_count": 0,
                "processing_time": round(processing_time, 2),
                "errors": errors,
                "file_path": file_path
            }
        }
    
    def process_file(
        self,
        file_path: str,
        file_type: Optional[str] = None,
        mime_type: Optional[str] = None
    ) -> Dict:
        """
        Main entry point for file processing. Routes to appropriate handler.
        
        Args:
            file_path: Path to the file to process
            file_type: Optional file type hint ("csv", "excel", "pdf", "image")
            mime_type: Optional MIME type for auto-detection
            
        Returns:
            Dictionary with processing results:
            {
                "success": bool,
                "tables": List[pd.DataFrame],
                "metadata": {
                    "file_type": str,
                    "table_count": int,
                    "processing_time": float,
                    "errors": List[str],
                    "file_path": str
                }
            }
        """
        start_time = time.time()
        errors = []
        tables = []
        
        try:
            # Valid file types
            valid_types = {"csv", "excel", "pdf", "image"}
            
            # Use provided file_type only if it's valid, otherwise auto-detect
            if file_type and file_type.lower() in valid_types:
                detected_file_type = file_type.lower()
            else:
                detected_file_type = IngestionConfig.get_file_type(file_path, mime_type)
            
            if detected_file_type == "unknown":
                return self._error_result(
                    detected_file_type,
                    time.time() - start_time,
                    file_path,
                    [IngestionConfig.ERROR_UNSUPPORTED_TYPE.format(file_type=detected_file_type)]
                )
            
            validation = IngestionConfig.validate_file(file_path)
            if not validation["valid"]:
                return self._error_result(
                    detected_file_type,
                    time.time() - start_time,
                    file_path,
                    [validation["error"]]
                )
            
            self.logger.info(f"Processing {detected_file_type} file: {file_path}")
            
            if detected_file_type not in self._handlers:
                return self._error_result(
                    detected_file_type,
                    time.time() - start_time,
                    file_path,
                    [IngestionConfig.ERROR_UNSUPPORTED_TYPE.format(file_type=detected_file_type)]
                )
            
            try:
                tables = self._handlers[detected_file_type](file_path)
            except ImportError as e:
                errors.append(f"Required library not installed: {e}")
            except (ValueError, Exception) as e:
                errors.append(str(e))
                self.logger.error(f"Error processing file: {e}", exc_info=True)
            
            if not tables:
                errors.append(IngestionConfig.ERROR_NO_TABLES_FOUND)
            
            if len(tables) > IngestionConfig.MAX_TABLES_PER_FILE:
                tables = tables[:IngestionConfig.MAX_TABLES_PER_FILE]
                errors.append(f"Limited to {IngestionConfig.MAX_TABLES_PER_FILE} tables")
            
            processing_time = time.time() - start_time
            result = {
                "success": len(tables) > 0 and len(errors) == 0,
                "tables": tables,
                "metadata": {
                    "file_type": detected_file_type,
                    "table_count": len(tables),
                    "processing_time": round(processing_time, 2),
                    "errors": errors,
                    "file_path": file_path
                }
            }
            
            self.logger.info(
                f"{'Successfully' if result['success'] else 'Partially'} processed: "
                f"{len(tables)} tables in {processing_time:.2f}s"
            )
            return result
            
        except Exception as e:
            self.logger.error(f"Unexpected error: {e}", exc_info=True)
            return self._error_result("unknown", time.time() - start_time, file_path, [str(e)])
    
    def process_files(
        self,
        file_paths: List[str],
        file_types: Optional[List[str]] = None
    ) -> List[Dict]:
        """
        Process multiple files and return results for each.
        
        Args:
            file_paths: List of file paths to process
            file_types: Optional list of file type hints (same order as file_paths)
            
        Returns:
            List of result dictionaries (one per file)
        """
        return [
            self.process_file(
                fp,
                file_types[i] if file_types and i < len(file_types) else None
            )
            for i, fp in enumerate(file_paths)
        ]
