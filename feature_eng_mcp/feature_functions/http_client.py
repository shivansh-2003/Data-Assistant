"""
HTTP client for session table load/save (same contract as data_mcp).
"""

import os
import base64
import pickle
import requests
import pandas as pd
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

INGESTION_API_URL = os.getenv(
    "INGESTION_API_URL",
    os.getenv("FASTAPI_URL", "https://data-assistant-hj5f.onrender.com"),
)
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))


class IngestionAPIClient:
    def __init__(self, base_url: str = None, timeout: int = None):
        self.base_url = (base_url or INGESTION_API_URL).rstrip("/")
        self.timeout = timeout or REQUEST_TIMEOUT
        self.session = requests.Session()

    def _serialize_dataframes(self, tables_dict: Dict[str, pd.DataFrame]) -> str:
        pickle_bytes = pickle.dumps(tables_dict)
        return base64.b64encode(pickle_bytes).decode("utf-8")

    def _deserialize_dataframes(self, base64_string: str) -> Dict[str, pd.DataFrame]:
        pickle_bytes = base64.b64decode(base64_string.encode("utf-8"))
        return pickle.loads(pickle_bytes)

    def load_tables_from_api(self, session_id: str) -> Optional[Dict[str, pd.DataFrame]]:
        try:
            url = f"{self.base_url}/api/session/{session_id}/tables"
            response = self.session.get(url, params={"format": "full"}, timeout=self.timeout)
            if response.status_code == 404:
                return None
            response.raise_for_status()
            data = response.json()
            tables_dict: Dict[str, pd.DataFrame] = {}
            for table_info in data.get("tables", []):
                table_name = table_info.get("table_name")
                base64_data = table_info.get("data")
                if table_name and base64_data:
                    pickle_bytes = base64.b64decode(base64_data.encode("utf-8"))
                    df = pickle.loads(pickle_bytes)
                    if isinstance(df, pd.DataFrame):
                        tables_dict[table_name] = df
            return tables_dict if tables_dict else None
        except Exception as e:
            logger.error(f"load_tables_from_api failed: {e}")
            raise

    def save_tables_to_api(
        self,
        session_id: str,
        tables_dict: Dict[str, pd.DataFrame],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        import time

        try:
            url = f"{self.base_url}/api/session/{session_id}/tables"
            tables_data = {}
            for table_name, df in tables_dict.items():
                pickle_bytes = pickle.dumps(df)
                base64_data = base64.b64encode(pickle_bytes).decode("utf-8")
                tables_data[table_name] = {
                    "data": base64_data,
                    "row_count": len(df),
                    "column_count": len(df.columns),
                    "columns": list(df.columns),
                    "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
                }
            payload = {"tables": tables_data, "metadata": metadata or {}}
            response = self.session.put(url, json=payload, timeout=self.timeout)
            response.raise_for_status()
            result = response.json()
            return bool(result.get("success", False))
        except Exception as e:
            logger.error(f"save_tables_to_api failed: {e}")
            raise


ingestion_client = IngestionAPIClient()


def get_ingestion_client() -> IngestionAPIClient:
    return ingestion_client
