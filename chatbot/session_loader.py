"""Session data loader for chatbot module."""

import logging
from typing import Dict, List, Optional, Any
import pandas as pd

from redis_db.redis_store import load_session, get_metadata

logger = logging.getLogger(__name__)


def load_session_dataframes(session_id: str) -> Dict[str, pd.DataFrame]:
    """
    Load all DataFrames from Redis session storage.
    
    Args:
        session_id: Session ID to load data from
        
    Returns:
        Dictionary mapping table names to DataFrames
        
    Raises:
        ValueError: If session not found
    """
    tables = load_session(session_id)
    
    if tables is None:
        raise ValueError(f"Session '{session_id}' not found or expired")
    
    logger.info(f"Loaded {len(tables)} tables from session {session_id}")
    return tables


def get_session_schema(session_id: str) -> Dict[str, Any]:
    """
    Get schema information for session tables.
    
    Args:
        session_id: Session ID
        
    Returns:
        Dictionary with schema information:
        {
            "tables": {
                "table_name": {
                    "columns": [str],
                    "dtypes": {str: str},
                    "row_count": int,
                    "column_count": int
                }
            }
        }
    """
    metadata = get_metadata(session_id)
    
    if metadata is None:
        raise ValueError(f"Metadata not found for session '{session_id}'")
    
    # Try to load actual tables to get accurate schema
    try:
        tables = load_session(session_id)
        schema_info = {
            "tables": {}
        }
        
        if tables:
            for table_name, df in tables.items():
                schema_info["tables"][table_name] = {
                    "columns": list(df.columns),
                    "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
                    "row_count": len(df),
                    "column_count": len(df.columns),
                    "numeric_columns": list(df.select_dtypes(include=['number']).columns),
                    "categorical_columns": list(df.select_dtypes(exclude=['number', 'datetime']).columns),
                    "datetime_columns": list(df.select_dtypes(include=['datetime']).columns)
                }
        
        return schema_info
    except Exception as e:
        logger.warning(f"Could not load tables for schema, using metadata: {e}")
        # Fallback to metadata
        return {
            "tables": metadata.get("tables", {}),
            "metadata": metadata
        }


def get_operation_history(session_id: str, streamlit_session_state: Any) -> List[Dict[str, Any]]:
    """
    Retrieve operation history from Streamlit session state.
    
    Args:
        session_id: Session ID (for future use if storing in Redis)
        streamlit_session_state: Streamlit session state object
        
    Returns:
        List of operation dictionaries (last 10 operations)
    """
    operation_history = getattr(streamlit_session_state, "operation_history", [])
    
    # Return last 10 operations
    return operation_history[-10:] if operation_history else []


def get_session_summary(session_id: str) -> Dict[str, Any]:
    """
    Get a summary of session data for context.
    
    Args:
        session_id: Session ID
        
    Returns:
        Dictionary with session summary
    """
    try:
        metadata = get_metadata(session_id)
        tables = load_session(session_id)
        
        summary = {
            "session_id": session_id,
            "table_count": len(tables) if tables else 0,
            "tables": {}
        }
        
        if tables:
            for table_name, df in tables.items():
                summary["tables"][table_name] = {
                    "row_count": len(df),
                    "column_count": len(df.columns),
                    "columns": list(df.columns),
                    "sample_data": df.head(5).to_dict('records') if not df.empty else []
                }
        
        if metadata:
            summary["file_name"] = metadata.get("file_name", "Unknown")
            summary["file_type"] = metadata.get("file_type", "Unknown")
            summary["created_at"] = metadata.get("created_at")
        
        return summary
    except Exception as e:
        logger.error(f"Error getting session summary: {e}")
        return {
            "session_id": session_id,
            "error": str(e)
        }

