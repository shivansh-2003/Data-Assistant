"""Session data loader adapted for InsightBot."""

import logging
from typing import Dict, List, Optional, Any
import pandas as pd
import requests

from redis_db import RedisStore

logger = logging.getLogger(__name__)

# Session endpoint configuration
FASTAPI_URL = "https://data-assistant-m4kl.onrender.com"
SESSION_ENDPOINT = f"{FASTAPI_URL}/api/session"


class SessionLoader:
    """Loader for session data from Redis storage."""
    
    def __init__(self, redis_store: Optional[RedisStore] = None):
        """
        Initialize SessionLoader.
        
        Args:
            redis_store: Optional RedisStore instance (creates default if None)
        """
        self.store = redis_store or RedisStore()
        self.logger = logging.getLogger(__name__)
    
    def load_session_dataframes(self, session_id: str) -> Dict[str, pd.DataFrame]:
        """
        Load all DataFrames from Redis session storage.
        
        Args:
            session_id: Session ID to load data from
            
        Returns:
            Dictionary mapping table names to DataFrames
            
        Raises:
            ValueError: If session not found
        """
        tables = self.store.load_session(session_id)
        
        if tables is None:
            raise ValueError(f"Session '{session_id}' not found or expired")
        
        self.logger.info(f"Loaded {len(tables)} tables from session {session_id}")
        return tables
    
    def load_full_dataframes(self, session_id: str) -> Dict[str, pd.DataFrame]:
        """
        Load full DataFrames (not just preview) via API.
        
        Args:
            session_id: Session ID
            
        Returns:
            Dictionary of full DataFrames
        """
        try:
            response = requests.get(
                f"{SESSION_ENDPOINT}/{session_id}/tables",
                params={"format": "full"},
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            
            tables = {}
            for table_info in data.get("tables", []):
                table_name = table_info.get("table_name")
                # Full data would be base64 encoded - decode if needed
                # For now, use Redis loader
                pass
            
            # Fallback to Redis loader (already has full data)
            return self.load_session_dataframes(session_id)
            
        except Exception as e:
            self.logger.warning(f"Could not load full dataframes via API: {e}")
            return self.load_session_dataframes(session_id)
    
    def get_session_schema(self, session_id: str) -> Dict[str, Any]:
        """
        Get schema information for session tables.
        
        Args:
            session_id: Session ID
            
        Returns:
            Dictionary with schema information
        """
        metadata = self.store.get_metadata(session_id)
        
        if metadata is None:
            raise ValueError(f"Metadata not found for session '{session_id}'")
        
        # Try to load actual tables to get accurate schema
        try:
            tables = self.store.load_session(session_id)
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
            self.logger.warning(f"Could not load tables for schema, using metadata: {e}")
            # Fallback to metadata
            return {
                "tables": metadata.get("tables", {}),
                "metadata": metadata
            }
    
    def get_operation_history(self, session_id: str, streamlit_session_state: Any = None) -> List[Dict[str, Any]]:
        """
        Retrieve operation history from Streamlit session state.
        
        Args:
            session_id: Session ID (for future use if storing in Redis)
            streamlit_session_state: Streamlit session state object
            
        Returns:
            List of operation dictionaries (last 10 operations)
        """
        if streamlit_session_state is None:
            return []
        
        operation_history = getattr(streamlit_session_state, "operation_history", [])
        
        # Return last 10 operations
        return operation_history[-10:] if operation_history else []
    
    def get_session_summary(self, session_id: str) -> Dict[str, Any]:
        """
        Get a summary of session data for context.
        
        Args:
            session_id: Session ID
            
        Returns:
            Dictionary with session summary
        """
        try:
            metadata = self.store.get_metadata(session_id)
            tables = self.store.load_session(session_id)
            
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
                        "sample_data": df.head(3).to_dict('records') if not df.empty else []
                    }
            
            if metadata:
                summary["file_name"] = metadata.get("file_name", "Unknown")
                summary["file_type"] = metadata.get("file_type", "Unknown")
                summary["created_at"] = metadata.get("created_at")
            
            return summary
        except Exception as e:
            self.logger.error(f"Error getting session summary: {e}")
            return {
                "session_id": session_id,
                "error": str(e)
            }


def prepare_state_dataframes(session_id: str, streamlit_session_state: Any = None) -> Dict[str, Any]:
    """
    Prepare DataFrames and context for graph state.
    
    Args:
        session_id: Session ID
        streamlit_session_state: Streamlit session state (optional)
        
    Returns:
        Dictionary with df_dict, schema, and operation_history
    """
    loader = SessionLoader()
    
    try:
        dfs = loader.load_session_dataframes(session_id)
        schema = loader.get_session_schema(session_id)
        history = loader.get_operation_history(session_id, streamlit_session_state)
        
        return {
            "df_dict": dfs,
            "schema": schema,
            "operation_history": history
        }
    except Exception as e:
        logger.error(f"Error preparing state dataframes: {e}")
        return {
            "df_dict": {},
            "schema": {},
            "operation_history": []
        }


# Create default instance for backward compatibility
_default_loader = SessionLoader()

