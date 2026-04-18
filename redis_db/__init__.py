"""Redis session store: tables, metadata, versions, and TTL.

`get_session_store()` picks a backend from env:
- Standard Redis (`redis-py`): when `REDIS_URL` or `REDIS_HOST`+`REDIS_PASSWORD` is set → `RedisCloudStore`
- Otherwise Upstash REST → `RedisStore`
"""

from .redis_store import RedisStore
from .session_store import BaseSessionStore, get_session_store
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
    'RedisCloudStore',
    'BaseSessionStore',
    'get_session_store',
    'DataFrameSerializer',
    'UPSTASH_REDIS_REST_URL',
    'UPSTASH_REDIS_REST_TOKEN',
    'SESSION_TTL',
    'KEY_SESSION_TABLES',
    'KEY_SESSION_META',
    'KEY_VERSION_TABLES',
    'KEY_SESSION_GRAPH'
]

# Optional import: only needed when Redis Cloud is selected.
try:
    from .redis_cloud_store import RedisCloudStore  # noqa: F401
except Exception:
    # Avoid import-time failures when redis-py isn't installed yet.
    RedisCloudStore = None  # type: ignore
