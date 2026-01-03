"""DataFrame serialization for Redis storage."""

import pickle
import logging
from typing import Dict, Optional
import pandas as pd

logger = logging.getLogger(__name__)


class DataFrameSerializer:
    """Serializer for pandas DataFrames to/from bytes for Redis storage."""
    
    def __init__(self, protocol: int = pickle.HIGHEST_PROTOCOL):
        """
        Initialize the serializer.
        
        Args:
            protocol: Pickle protocol version to use (default: highest available)
        """
        self.protocol = protocol
        self.logger = logging.getLogger(__name__)
    
    def serialize(self, tables: Dict[str, pd.DataFrame]) -> bytes:
        """
        Serialize dictionary of DataFrames to bytes.
        
        Args:
            tables: Dictionary mapping table names to DataFrames
            
        Returns:
            Serialized bytes
            
        Raises:
            Exception: If serialization fails
        """
        try:
            return pickle.dumps(tables, protocol=self.protocol)
        except Exception as e:
            self.logger.error(f"Serialization failed: {e}")
            raise
    
    def deserialize(self, blob: Optional[bytes]) -> Dict[str, pd.DataFrame]:
        """
        Deserialize bytes back to dictionary of DataFrames.
        
        Args:
            blob: Serialized bytes (can be None)
            
        Returns:
            Dictionary mapping table names to DataFrames (empty dict if blob is None)
            
        Raises:
            Exception: If deserialization fails
        """
        try:
            if blob is None:
                return {}
            return pickle.loads(blob)
        except Exception as e:
            self.logger.error(f"Deserialization failed: {e}")
            raise
