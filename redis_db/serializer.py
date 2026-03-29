"""Pickle serialization for DataFrame dicts stored in Redis."""

import logging
import pickle
from typing import Dict, Optional

import pandas as pd

logger = logging.getLogger(__name__)


class DataFrameSerializer:
    """Pickle encode/decode for `dict[str, pd.DataFrame]`."""

    def __init__(self, protocol: int = pickle.HIGHEST_PROTOCOL):
        self.protocol = protocol

    def serialize(self, tables: Dict[str, pd.DataFrame]) -> bytes:
        try:
            return pickle.dumps(tables, protocol=self.protocol)
        except Exception as e:
            logger.error("Serialization failed: %s", e)
            raise

    def deserialize(self, blob: Optional[bytes]) -> Dict[str, pd.DataFrame]:
        try:
            if blob is None:
                return {}
            return pickle.loads(blob)
        except Exception as e:
            logger.error("Deserialization failed: %s", e)
            raise
