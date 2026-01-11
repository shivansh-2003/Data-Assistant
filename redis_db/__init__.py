"""
Redis database module for session management with automatic TTL-based cleanup.

All session data (tables, metadata, versions, graphs) automatically expires
after the configured TTL period (default: 30 minutes).
"""

from .redis_store import RedisStore
from .constants import (
    UPSTASH_REDIS_REST_URL,
    UPSTASH_REDIS_REST_TOKEN,
    SESSION_TTL,
    KEY_SESSION_TABLES,
    KEY_SESSION_META,
    KEY_VERSION_TABLES,
    KEY_SESSION_GRAPH
)
from .serializer import DataFrameSerializer

__all__ = [
    'RedisStore',
    'DataFrameSerializer',
    'UPSTASH_REDIS_REST_URL',
    'UPSTASH_REDIS_REST_TOKEN',
    'SESSION_TTL',
    'KEY_SESSION_TABLES',
    'KEY_SESSION_META',
    'KEY_VERSION_TABLES',
    'KEY_SESSION_GRAPH'
]
