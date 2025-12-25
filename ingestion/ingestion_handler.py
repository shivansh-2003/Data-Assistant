"""Main ingestion handler providing unified interface for all file types."""

import time
import logging
from typing import Dict, List, Optional
from .csv_handler import process_csv
from .excel_handler import process_excel
from .image_handler import process_image
from .pdf_handler import process_pdf
from .config import IngestionConfig

logger = logging.getLogger(__name__)

_HANDLERS = {
    "csv": process_csv,
    "excel": process_excel,
    "image": process_image,
    "pdf": process_pdf
}


def process_file(file_path: str, file_type: Optional[str] = None, 
                 mime_type: Optional[str] = None) -> Dict:
    """Main entry point for file processing. Routes to appropriate handler."""
    start_time = time.time()
    errors = []
    tables = []
    
    try:
        detected_file_type = file_type.lower() if file_type else IngestionConfig.get_file_type(file_path, mime_type)
        
        if detected_file_type == "unknown":
            return _error_result(detected_file_type, time.time() - start_time, file_path,
                               [IngestionConfig.ERROR_UNSUPPORTED_TYPE.format(file_type=detected_file_type)])
        
        validation = IngestionConfig.validate_file(file_path)
        if not validation["valid"]:
            return _error_result(detected_file_type, time.time() - start_time, file_path, [validation["error"]])
        
        logger.info(f"Processing {detected_file_type} file: {file_path}")
        
        if detected_file_type not in _HANDLERS:
            return _error_result(detected_file_type, time.time() - start_time, file_path,
                               [IngestionConfig.ERROR_UNSUPPORTED_TYPE.format(file_type=detected_file_type)])
        
        try:
            tables = _HANDLERS[detected_file_type](file_path)
        except ImportError as e:
            errors.append(f"Required library not installed: {e}")
        except (ValueError, Exception) as e:
            errors.append(str(e))
            logger.error(f"Error processing file: {e}", exc_info=True)
        
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
        
        logger.info(f"{'Successfully' if result['success'] else 'Partially'} processed: "
                   f"{len(tables)} tables in {processing_time:.2f}s")
        return result
        
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return _error_result("unknown", time.time() - start_time, file_path, [str(e)])


def _error_result(file_type: str, processing_time: float, file_path: str, errors: List[str]) -> Dict:
    """Helper to create error result dictionary."""
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


def process_files(file_paths: List[str], file_types: Optional[List[str]] = None) -> List[Dict]:
    """Process multiple files and return results for each."""
    return [process_file(fp, file_types[i] if file_types and i < len(file_types) else None) 
            for i, fp in enumerate(file_paths)]

