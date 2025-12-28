"""DataFrame serialization utilities for Redis storage."""

import io
import pickle
import pandas as pd
import logging
from typing import Dict

logger = logging.getLogger(__name__)

# Try to import parquet for future use (optional)
try:
    import pyarrow.parquet as pq
    import pyarrow as pa
    PARQUET_AVAILABLE = True
except ImportError:
    PARQUET_AVAILABLE = False
    logger.warning("PyArrow not available. Using pickle-only serialization.")


def serialize_dfs(tables: Dict[str, pd.DataFrame]) -> bytes:
    """
    Serialize dictionary of DataFrames to bytes using pickle.
    
    Args:
        tables: Dictionary mapping table names to DataFrames
        
    Returns:
        Pickled bytes containing the tables dictionary
        
    Note:
        Future enhancement: Use Parquet for large DataFrames (>100MB)
    """
    try:
        return pickle.dumps({name: df for name, df in tables.items()})
    except Exception as e:
        logger.error(f"Failed to serialize DataFrames: {e}")
        raise


def deserialize_dfs(blob: bytes) -> Dict[str, pd.DataFrame]:
    """
    Deserialize bytes back to dictionary of DataFrames.
    
    Args:
        blob: Pickled bytes containing tables dictionary
        
    Returns:
        Dictionary mapping table names to DataFrames
    """
    try:
        if blob is None:
            return {}
        return pickle.loads(blob)
    except Exception as e:
        logger.error(f"Failed to deserialize DataFrames: {e}")
        raise

