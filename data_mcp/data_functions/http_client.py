"""
HTTP Client for MCP Server to communicate with Ingestion API.
Handles loading and saving DataFrames via HTTP requests with base64 pickle serialization.
"""

import os
import base64
import pickle
import time as _time
import logging
import requests
import pandas as pd
from typing import Dict, Any, Optional

from .df_codec import encode_df, decode_df

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Per-operation latency ceilings (seconds).  Exceeded → WARNING in logs.
# ---------------------------------------------------------------------------
_BENCHMARKS: dict[str, float] = {
    "http.load_tables":             1.00,
    "http.load_tables.http":        0.60,
    "http.load_tables.deserialize": 0.20,
    "http.save_tables":             1.20,
    "http.save_tables.serialize":   0.20,
    "http.save_tables.http":        0.80,
}


def _perf_warn(name: str, elapsed: float, session_id: str = "") -> None:
    threshold = _BENCHMARKS.get(name)
    if threshold and elapsed > threshold:
        logger.warning(
            "[PERF][SLOW] %-40s  session=%s  %.3fs elapsed  (benchmark: %.3fs  |  %.1fx over)",
            name, session_id, elapsed, threshold, elapsed / threshold,
        )


# Configuration
# INGESTION_API_URL = "https://data-assistant-hj5f.onrender.com"
INGESTION_API_URL = "http://0.0.0.0:8000"
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
        Benchmark: < 1.0 s total (HTTP GET < 0.60 s, deserialize < 0.20 s).

        Args:
            session_id: Unique session identifier

        Returns:
            Dictionary mapping table names to DataFrames, or None if session not found
        """
        _t0 = _time.perf_counter()
        logger.info(
            "[PERF] http.load_tables START  session=%s  url=%s/api/session/%s/tables",
            session_id, self.base_url, session_id,
        )
        try:
            url = f"{self.base_url}/api/session/{session_id}/tables"
            params = {"format": "full"}

            # ── HTTP GET ──────────────────────────────────────────────────────
            _t_http = _time.perf_counter()
            response = self.session.get(url, params=params, timeout=self.timeout)
            _t_http_e = _time.perf_counter() - _t_http
            logger.info(
                "[PERF] http.load_tables.http  session=%s  status=%d  duration=%.3fs  "
                "response_kb=%.1f",
                session_id, response.status_code, _t_http_e,
                len(response.content) / 1024,
            )
            _perf_warn("http.load_tables.http", _t_http_e, session_id)

            if response.status_code == 404:
                logger.warning(f"Session {session_id} not found at {url}")
                return None

            if response.status_code != 200:
                logger.error(f"Unexpected status code {response.status_code} from {url}: {response.text}")
                response.raise_for_status()

            response.raise_for_status()
            data = response.json()
            logger.debug(f"Received response with {len(data.get('tables', []))} tables")

            # ── deserialize ───────────────────────────────────────────────────
            # T-5: decode_df handles AR1:, PK1:, and legacy unprefixed pickle.
            _t_des = _time.perf_counter()
            tables_dict = {}
            for table_info in data.get("tables", []):
                table_name = table_info.get("table_name")
                base64_data = table_info.get("data")

                if table_name and base64_data:
                    try:
                        df = decode_df(base64_data)
                        if isinstance(df, pd.DataFrame):
                            tables_dict[table_name] = df
                        else:
                            logger.warning(f"Deserialized data for table '{table_name}' is not a DataFrame")
                    except Exception as e:
                        logger.error(f"Failed to deserialize table '{table_name}': {e}")
                        raise
            _t_des_e = _time.perf_counter() - _t_des
            logger.info(
                "[PERF] http.load_tables.deserialize  session=%s  duration=%.3fs  table_count=%d",
                session_id, _t_des_e, len(tables_dict),
            )
            _perf_warn("http.load_tables.deserialize", _t_des_e, session_id)

            _t_total = _time.perf_counter() - _t0
            logger.info(
                "[PERF] http.load_tables END  session=%s  http=%.3fs  deserialize=%.3fs  total=%.3fs",
                session_id, _t_http_e, _t_des_e, _t_total,
            )
            _perf_warn("http.load_tables", _t_total, session_id)
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
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Save tables to a session via HTTP API.
        Benchmark: < 1.2 s total (serialize < 0.20 s, HTTP PUT < 0.80 s).

        Args:
            session_id: Unique session identifier
            tables_dict: Dictionary mapping table names to DataFrames
            metadata: Optional session metadata

        Returns:
            True if successful, False otherwise
        """
        _t0 = _time.perf_counter()
        logger.info(
            "[PERF] http.save_tables START  session=%s  table_count=%d",
            session_id, len(tables_dict),
        )
        try:
            url = f"{self.base_url}/api/session/{session_id}/tables"

            # ── serialize ─────────────────────────────────────────────────────
            # T-5: encode_df produces an AR1:-prefixed Arrow IPC blob, falling
            # back to PK1: pickle for frames Arrow can't represent.
            _t_ser = _time.perf_counter()
            tables_data = {}
            for table_name, df in tables_dict.items():
                tables_data[table_name] = {
                    "data": encode_df(df),
                    "row_count": len(df),
                    "column_count": len(df.columns),
                    "columns": list(df.columns),
                    "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
                }
            payload = {"tables": tables_data, "metadata": metadata or {}}
            payload_kb = sum(len(v["data"]) for v in tables_data.values()) / 1024
            _t_ser_e = _time.perf_counter() - _t_ser
            logger.info(
                "[PERF] http.save_tables.serialize  session=%s  duration=%.3fs  payload_kb=%.1f",
                session_id, _t_ser_e, payload_kb,
            )
            _perf_warn("http.save_tables.serialize", _t_ser_e, session_id)

            # ── HTTP PUT ──────────────────────────────────────────────────────
            logger.info(f"Saving {len(tables_dict)} tables to session {session_id} via HTTP")
            _t_http = _time.perf_counter()
            response = self.session.put(url, json=payload, timeout=self.timeout)
            _t_http_e = _time.perf_counter() - _t_http
            logger.info(
                "[PERF] http.save_tables.http  session=%s  status=%d  duration=%.3fs",
                session_id, response.status_code, _t_http_e,
            )
            _perf_warn("http.save_tables.http", _t_http_e, session_id)

            response.raise_for_status()
            result = response.json()
            success = result.get("success", False)
            
            _t_total = _time.perf_counter() - _t0
            logger.info(
                "[PERF] http.save_tables END  session=%s  serialize=%.3fs  http=%.3fs  total=%.3fs  success=%s",
                session_id, _t_ser_e, _t_http_e, _t_total, success,
            )
            _perf_warn("http.save_tables", _t_total, session_id)
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