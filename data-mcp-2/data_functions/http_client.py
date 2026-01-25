"""
HTTP Client for MCP Server to communicate with Ingestion API.
Handles loading and saving DataFrames via HTTP requests with base64 pickle serialization.
"""

import os
import base64
import pickle
import requests
import pandas as pd
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

# Configuration
INGESTION_API_URL = "https://data-assistant-m4kl.onrender.com"
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))


class IngestionAPIClient:
    """HTTP client for communicating with the ingestion API."""
    
    def __init__(self, base_url: str = None, timeout: int = None):
        """
        Initialize the HTTP client.
        
        Args:
            base_url: Base URL for the ingestion API (defaults to INGESTION_API_URL env var)
            timeout: Request timeout in seconds (defaults to REQUEST_TIMEOUT env var)
        """
        self.base_url = base_url or INGESTION_API_URL
        self.timeout = timeout or REQUEST_TIMEOUT
        self.session = requests.Session()
        
    def _serialize_dataframes(self, tables_dict: Dict[str, pd.DataFrame]) -> str:
        """
        Serialize DataFrames dictionary to base64-encoded pickle string.
        
        Args:
            tables_dict: Dictionary mapping table names to DataFrames
            
        Returns:
            Base64-encoded pickle string
        """
        try:
            # Pickle the DataFrames dictionary
            pickle_bytes = pickle.dumps(tables_dict)
            # Encode to base64 string
            base64_string = base64.b64encode(pickle_bytes).decode('utf-8')
            return base64_string
        except Exception as e:
            logger.error(f"Failed to serialize DataFrames: {e}")
            raise
    
    def _deserialize_dataframes(self, base64_string: str) -> Dict[str, pd.DataFrame]:
        """
        Deserialize base64-encoded pickle string to DataFrames dictionary.
        
        Args:
            base64_string: Base64-encoded pickle string
            
        Returns:
            Dictionary mapping table names to DataFrames
        """
        try:
            # Decode from base64
            pickle_bytes = base64.b64decode(base64_string.encode('utf-8'))
            # Unpickle to DataFrames dictionary
            tables_dict = pickle.loads(pickle_bytes)
            return tables_dict
        except Exception as e:
            logger.error(f"Failed to deserialize DataFrames: {e}")
            raise
    
    def load_tables_from_api(self, session_id: str) -> Optional[Dict[str, pd.DataFrame]]:
        """
        Load all tables from a session via HTTP API.
        
        Args:
            session_id: Unique session identifier
            
        Returns:
            Dictionary mapping table names to DataFrames, or None if session not found
        """
        try:
            url = f"{self.base_url}/api/session/{session_id}/tables"
            params = {"format": "full"}  # Request full DataFrame data
            
            logger.info(f"Loading tables from session {session_id} via HTTP")
            response = self.session.get(url, params=params, timeout=self.timeout)
            
            if response.status_code == 404:
                logger.warning(f"Session {session_id} not found")
                return None
                
            response.raise_for_status()
            
            data = response.json()
            
            # Extract base64-encoded DataFrames
            tables_dict = {}
            for table_info in data.get("tables", []):
                table_name = table_info.get("table_name")
                base64_data = table_info.get("data")
                
                if table_name and base64_data:
                    # Deserialize single DataFrame from base64 pickle
                    try:
                        pickle_bytes = base64.b64decode(base64_data.encode('utf-8'))
                        df = pickle.loads(pickle_bytes)
                        if isinstance(df, pd.DataFrame):
                            tables_dict[table_name] = df
                        else:
                            logger.warning(f"Deserialized data for table '{table_name}' is not a DataFrame")
                    except Exception as e:
                        logger.error(f"Failed to deserialize table '{table_name}': {e}")
                        raise
            
            logger.info(f"Successfully loaded {len(tables_dict)} tables from session {session_id}")
            return tables_dict
            
        except requests.exceptions.RequestException as e:
            logger.error(f"HTTP error loading tables from session {session_id}: {e}")
            raise
        except Exception as e:
            logger.error(f"Error loading tables from session {session_id}: {e}")
            raise
    
    def save_tables_to_api(
        self, 
        session_id: str, 
        tables_dict: Dict[str, pd.DataFrame],
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Save tables to a session via HTTP API.
        
        Args:
            session_id: Unique session identifier
            tables_dict: Dictionary mapping table names to DataFrames
            metadata: Optional session metadata
            
        Returns:
            True if successful, False otherwise
        """
        try:
            url = f"{self.base_url}/api/session/{session_id}/tables"
            
            # Prepare the payload with serialized DataFrames
            tables_data = {}
            for table_name, df in tables_dict.items():
                # Serialize each DataFrame individually (not as a dict)
                pickle_bytes = pickle.dumps(df)
                base64_data = base64.b64encode(pickle_bytes).decode('utf-8')
                
                tables_data[table_name] = {
                    "data": base64_data,
                    "row_count": len(df),
                    "column_count": len(df.columns),
                    "columns": list(df.columns),
                    "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()}
                }
            
            payload = {
                "tables": tables_data,
                "metadata": metadata or {}
            }
            
            logger.info(f"Saving {len(tables_dict)} tables to session {session_id} via HTTP")
            response = self.session.put(url, json=payload, timeout=self.timeout)
            
            response.raise_for_status()
            
            result = response.json()
            success = result.get("success", False)
            
            if success:
                logger.info(f"Successfully saved tables to session {session_id}")
            else:
                logger.error(f"Failed to save tables to session {session_id}: {result.get('error', 'Unknown error')}")
            
            return success
            
        except requests.exceptions.RequestException as e:
            logger.error(f"HTTP error saving tables to session {session_id}: {e}")
            raise
        except Exception as e:
            logger.error(f"Error saving tables to session {session_id}: {e}")
            raise
    
    def get_session_metadata(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get metadata for a session.
        
        Args:
            session_id: Unique session identifier
            
        Returns:
            Session metadata dictionary, or None if session not found
        """
        try:
            url = f"{self.base_url}/api/session/{session_id}/metadata"
            
            logger.info(f"Getting metadata for session {session_id}")
            response = self.session.get(url, timeout=self.timeout)
            
            if response.status_code == 404:
                return None
                
            response.raise_for_status()
            
            data = response.json()
            return data.get("metadata")
            
        except requests.exceptions.RequestException as e:
            logger.error(f"HTTP error getting metadata for session {session_id}: {e}")
            raise
        except Exception as e:
            logger.error(f"Error getting metadata for session {session_id}: {e}")
            raise
    
    def session_exists(self, session_id: str) -> bool:
        """
        Check if a session exists.
        
        Args:
            session_id: Unique session identifier
            
        Returns:
            True if session exists, False otherwise
        """
        try:
            metadata = self.get_session_metadata(session_id)
            return metadata is not None
        except Exception as e:
            logger.error(f"Error checking if session {session_id} exists: {e}")
            return False


# Global client instance (can be imported and used across modules)
ingestion_client = IngestionAPIClient()


def get_ingestion_client() -> IngestionAPIClient:
    """Get the global ingestion API client instance."""
    return ingestion_client