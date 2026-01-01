"""DataFrame serialization for Redis storage."""

import pickle
import logging
from typing import Dict
import pandas as pd

logger = logging.getLogger(__name__)


def serialize_dataframes(tables: Dict[str, pd.DataFrame]) -> bytes:
    """Serialize dictionary of DataFrames to bytes."""
    try:
        return pickle.dumps(tables)
    except Exception as e:
        logger.error(f"Serialization failed: {e}")
        raise


def deserialize_dataframes(blob: bytes) -> Dict[str, pd.DataFrame]:
    """Deserialize bytes back to dictionary of DataFrames."""
    try:
        if blob is None:
            return {}
        return pickle.loads(blob)
    except Exception as e:
        logger.error(f"Deserialization failed: {e}")
        raise
