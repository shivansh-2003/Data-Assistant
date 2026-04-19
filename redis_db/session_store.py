"""
Backend-agnostic session store interface + factory.

Callers should use ``get_session_store()``; configuration lives in ``constants.py``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

import pandas as pd

from .constants import (
    REDIS_URL,
    REDIS_HOST,
    REDIS_PORT,
    REDIS_USERNAME,
    REDIS_PASSWORD,
    REDIS_TLS,
    SESSION_TTL,
    use_redis_cloud_kv,
)
from .store_common import CurrentVersionMixin


class BaseSessionStore(ABC, CurrentVersionMixin):
    @abstractmethod
    def probe_read_write(self) -> Dict[str, Any]: ...

    @abstractmethod
    def is_connected(self) -> bool: ...

    @abstractmethod
    def save_session(self, session_id: str, tables: Dict[str, pd.DataFrame], metadata: Dict) -> bool: ...

    @abstractmethod
    def load_session(self, session_id: str) -> Optional[Dict[str, pd.DataFrame]]: ...

    @abstractmethod
    def get_metadata(self, session_id: str) -> Optional[Dict]: ...

    @abstractmethod
    def _write_metadata(self, session_id: str, metadata: Dict) -> bool: ...

    @abstractmethod
    def delete_session(self, session_id: str) -> bool: ...

    @abstractmethod
    def extend_ttl(self, session_id: str) -> bool: ...

    @abstractmethod
    def session_exists(self, session_id: str) -> bool: ...

    @abstractmethod
    def save_version(self, session_id: str, version_id: str, tables: Dict[str, pd.DataFrame]) -> bool: ...

    @abstractmethod
    def load_version(self, session_id: str, version_id: str) -> Optional[Dict[str, pd.DataFrame]]: ...

    @abstractmethod
    def list_versions(self, session_id: str) -> List[str]: ...

    @abstractmethod
    def delete_version(self, session_id: str, version_id: str) -> bool: ...

    @abstractmethod
    def get_graph(self, session_id: str) -> Dict[str, Any]: ...

    @abstractmethod
    def update_graph(
        self,
        session_id: str,
        parent_vid: Optional[str],
        new_vid: str,
        operation: str,
        query: Optional[str] = None,
    ) -> bool: ...

    @abstractmethod
    def snapshot_session_as_version(self, session_id: str, version_id: str) -> bool:
        """Point-in-time copy of live session tables to a version key (prefer Redis COPY)."""
        ...

    @abstractmethod
    def restore_version_as_session(self, session_id: str, version_id: str) -> bool:
        """Copy a version snapshot back to live session tables (prefer Redis COPY)."""
        ...

    # ── Raw KV helpers (T-3 transform cache) ────────────────────────────────
    # Used by mcp_client.analyze_data (and any future caller) to piggy-back on
    # the existing Redis connection for general-purpose string caching, without
    # needing a separate Redis client. Implementations should accept str/bytes
    # values and return bytes (or str for the Upstash REST backend).
    @abstractmethod
    def raw_get(self, key: str) -> Optional[Any]:
        """Return the raw value at `key` or None if missing."""
        ...

    @abstractmethod
    def raw_setex(self, key: str, ttl_seconds: int, value: Any) -> bool:
        """Set `key` to `value` with TTL; returns True on success."""
        ...


def get_session_store() -> BaseSessionStore:
    if use_redis_cloud_kv():
        from .redis_cloud_store import RedisCloudStore

        username = (REDIS_USERNAME or "").strip() or (
            "default" if (REDIS_HOST or "").strip() else None
        )

        return RedisCloudStore(
            redis_url=REDIS_URL,
            host=REDIS_HOST,
            port=REDIS_PORT,
            username=username,
            password=REDIS_PASSWORD,
            tls=REDIS_TLS,
            session_ttl=SESSION_TTL,
        )

    from .redis_store import RedisStore

    return RedisStore(session_ttl=SESSION_TTL)
