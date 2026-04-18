"""Session storage via redis-py (Redis Cloud / standard TCP or TLS)."""

from __future__ import annotations

import base64
import json
import logging
from typing import Any, Dict, List, Optional

import pandas as pd

from .constants import (
    KEY_SESSION_GRAPH,
    KEY_SESSION_META,
    KEY_SESSION_TABLES,
    KEY_VERSION_TABLES,
    SESSION_TTL,
)
from .serializer import DataFrameSerializer
from .session_store import BaseSessionStore
from .store_common import append_lineage, json_loads_flexible, version_ids_from_key_names

logger = logging.getLogger(__name__)


class RedisCloudStore(BaseSessionStore):
    def __init__(
        self,
        redis_url: Optional[str] = None,
        host: Optional[str] = None,
        port: int = 6379,
        username: Optional[str] = None,
        password: Optional[str] = None,
        tls: Optional[bool] = None,
        db: int = 0,
        session_ttl: Optional[int] = None,
        serializer: Optional[DataFrameSerializer] = None,
    ):
        self.session_ttl = session_ttl or SESSION_TTL
        self.serializer = serializer or DataFrameSerializer()

        self._client = None
        self._client_kwargs = {
            "redis_url": redis_url,
            "host": host,
            "port": port,
            "username": username,
            "password": password,
            "tls": tls,
            "db": db,
        }
        self._initialize_client()

    def _initialize_client(self) -> None:
        try:
            import redis

            redis_url = (self._client_kwargs.get("redis_url") or "").strip()
            if redis_url:
                self._client = redis.Redis.from_url(
                    redis_url,
                    decode_responses=False,
                    socket_connect_timeout=5,
                    socket_timeout=10,
                    health_check_interval=30,
                    retry_on_timeout=True,
                )
            else:
                host = (self._client_kwargs.get("host") or "").strip()
                port = int(self._client_kwargs.get("port") or 6379)
                username = self._client_kwargs.get("username")
                password = self._client_kwargs.get("password")
                tls_opt = self._client_kwargs.get("tls")
                ssl_enabled = False if tls_opt is None else bool(tls_opt)
                db = int(self._client_kwargs.get("db") or 0)

                if not host:
                    raise ValueError("Redis Cloud config missing: set REDIS_URL or REDIS_HOST")

                self._client = redis.Redis(
                    host=host,
                    port=port,
                    username=username,
                    password=password,
                    db=db,
                    ssl=ssl_enabled,
                    decode_responses=False,
                    socket_connect_timeout=5,
                    socket_timeout=10,
                    health_check_interval=30,
                    retry_on_timeout=True,
                )

            self._client.ping()
            logger.info("Connected to Redis (standard/Redis Cloud)")
        except ImportError:
            logger.error("redis (redis-py) not installed. Add `redis` to requirements.txt")
            self._client = None
        except Exception as e:
            logger.error("Redis Cloud init error: %s", e, exc_info=True)
            self._client = None

    @property
    def redis(self):
        return self._client

    def is_connected(self) -> bool:
        if self._client is None:
            return False
        try:
            return bool(self._client.ping())
        except Exception:
            return False

    def probe_read_write(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {"ping": False, "set_get_delete": False, "error": None}
        if not self.is_connected():
            out["error"] = "client not initialized or ping failed"
            return out
        key = "__data_assistant_probe__"
        try:
            self._client.ping()
            out["ping"] = True
            self._client.set(key, b"ok", ex=15)
            val = self._client.get(key)
            self._client.delete(key)
            out["set_get_delete"] = val in (b"ok", "ok")
            if not out["set_get_delete"]:
                out["sample_value_repr"] = repr(val)[:200]
        except Exception as e:
            out["error"] = str(e)
            logger.error("Redis Cloud probe failed: %s", e, exc_info=True)
        return out

    def _scan_keys(self, pattern: str, count: int = 200) -> List[str]:
        if self._client is None:
            return []
        out: List[str] = []
        cursor = 0
        while True:
            cursor, batch = self._client.scan(cursor=cursor, match=pattern, count=count)
            for k in batch:
                out.append(k.decode("utf-8") if isinstance(k, (bytes, bytearray)) else str(k))
            if cursor == 0:
                break
        return out

    def _set_with_ttl(self, key: str, value: bytes, ttl_seconds: int) -> None:
        self._client.set(key, value, ex=ttl_seconds)

    def _sync_version_ttls(self, session_id: str) -> None:
        try:
            for version_id in self.list_versions(session_id):
                key_version = KEY_VERSION_TABLES.format(sid=session_id, vid=version_id)
                self._client.expire(key_version, self.session_ttl)
        except Exception as e:
            logger.warning("Failed to sync version TTLs for %s: %s", session_id, e)

    def _write_metadata(self, session_id: str, metadata: Dict) -> bool:
        key = KEY_SESSION_META.format(sid=session_id)
        self._set_with_ttl(key, json.dumps(metadata, default=str).encode("utf-8"), self.session_ttl)
        return True

    def save_session(self, session_id: str, tables: Dict[str, pd.DataFrame], metadata: Dict) -> bool:
        if not self.is_connected():
            logger.error("Redis Cloud not connected")
            return False
        try:
            key_tables = KEY_SESSION_TABLES.format(sid=session_id)
            key_meta = KEY_SESSION_META.format(sid=session_id)
            key_graph = KEY_SESSION_GRAPH.format(sid=session_id)

            tables_bytes = self.serializer.serialize(tables)
            tables_b64 = base64.b64encode(tables_bytes)

            self._set_with_ttl(key_tables, tables_b64, self.session_ttl)
            self._set_with_ttl(key_meta, json.dumps(metadata, default=str).encode("utf-8"), self.session_ttl)

            if not self._client.exists(key_graph):
                empty = json.dumps({"nodes": [], "edges": []}).encode("utf-8")
                self._set_with_ttl(key_graph, empty, self.session_ttl)
            else:
                self._client.expire(key_graph, self.session_ttl)

            self._sync_version_ttls(session_id)
            logger.info("Saved session %s with %d tables (TTL=%ss)", session_id, len(tables), self.session_ttl)
            return True
        except Exception as e:
            logger.error("Failed to save session %s: %s", session_id, e, exc_info=True)
            return False

    def load_session(self, session_id: str) -> Optional[Dict[str, pd.DataFrame]]:
        if not self.is_connected():
            return None
        try:
            key = KEY_SESSION_TABLES.format(sid=session_id)
            data = self._client.get(key)
            if data is None:
                return None
            tables_bytes = base64.b64decode(data)
            return self.serializer.deserialize(tables_bytes)
        except Exception as e:
            logger.error("Failed to load session %s: %s", session_id, e)
            return None

    def get_metadata(self, session_id: str) -> Optional[Dict]:
        if not self.is_connected():
            return None
        try:
            key = KEY_SESSION_META.format(sid=session_id)
            data = self._client.get(key)
            if data is None:
                return None
            return json_loads_flexible(data)
        except Exception as e:
            logger.error("Failed to get metadata for %s: %s", session_id, e)
            return None

    def delete_session(self, session_id: str) -> bool:
        if not self.is_connected():
            return False
        try:
            keys = self._scan_keys(f"session:{session_id}:*")
            if not keys:
                return False
            return bool(self._client.delete(*keys))
        except Exception as e:
            logger.error("Failed to delete session %s: %s", session_id, e)
            return False

    def extend_ttl(self, session_id: str) -> bool:
        if not self.is_connected():
            return False
        try:
            key_tables = KEY_SESSION_TABLES.format(sid=session_id)
            key_meta = KEY_SESSION_META.format(sid=session_id)
            key_graph = KEY_SESSION_GRAPH.format(sid=session_id)
            self._client.expire(key_tables, self.session_ttl)
            self._client.expire(key_meta, self.session_ttl)
            self._client.expire(key_graph, self.session_ttl)
            self._sync_version_ttls(session_id)
            return True
        except Exception as e:
            logger.error("Failed to extend TTL for %s: %s", session_id, e)
            return False

    def session_exists(self, session_id: str) -> bool:
        if not self.is_connected():
            return False
        try:
            key_tables = KEY_SESSION_TABLES.format(sid=session_id)
            return bool(self._client.exists(key_tables))
        except Exception:
            return False

    def list_sessions(self) -> List[Dict]:
        if not self.is_connected():
            return []
        sessions: List[Dict] = []
        try:
            for key in self._scan_keys("session:*:meta"):
                try:
                    parts = key.split(":")
                    sid = parts[1] if len(parts) >= 3 else None
                    if not sid:
                        continue
                    meta = self.get_metadata(sid) or {}
                    sessions.append({"session_id": sid, "metadata": meta})
                except Exception:
                    continue
        except Exception as e:
            logger.error("Failed to list sessions: %s", e)
        return sessions

    def save_version(self, session_id: str, version_id: str, tables: Dict[str, pd.DataFrame]) -> bool:
        if not self.is_connected():
            return False
        try:
            key = KEY_VERSION_TABLES.format(sid=session_id, vid=version_id)
            tables_bytes = self.serializer.serialize(tables)
            tables_b64 = base64.b64encode(tables_bytes)
            self._set_with_ttl(key, tables_b64, self.session_ttl)
            self.extend_ttl(session_id)
            return True
        except Exception as e:
            logger.error("Failed to save version %s for %s: %s", version_id, session_id, e)
            return False

    def load_version(self, session_id: str, version_id: str) -> Optional[Dict[str, pd.DataFrame]]:
        if not self.is_connected():
            return None
        try:
            key = KEY_VERSION_TABLES.format(sid=session_id, vid=version_id)
            data = self._client.get(key)
            if data is None:
                return None
            tables_bytes = base64.b64decode(data)
            tables = self.serializer.deserialize(tables_bytes)
            self.extend_ttl(session_id)
            return tables
        except Exception as e:
            logger.error("Failed to load version %s for %s: %s", version_id, session_id, e)
            return None

    def delete_version(self, session_id: str, version_id: str) -> bool:
        if not self.is_connected():
            return False
        try:
            key = KEY_VERSION_TABLES.format(sid=session_id, vid=version_id)
            return bool(self._client.delete(key))
        except Exception as e:
            logger.error("Failed to delete version %s for %s: %s", version_id, session_id, e)
            return False

    def list_versions(self, session_id: str) -> List[str]:
        if not self.is_connected():
            return []
        try:
            pattern = KEY_VERSION_TABLES.format(sid=session_id, vid="*")
            return version_ids_from_key_names(self._scan_keys(pattern))
        except Exception as e:
            logger.error("Failed to list versions for %s: %s", session_id, e)
            return []

    def get_graph(self, session_id: str) -> Dict[str, Any]:
        if not self.is_connected():
            return {"nodes": [], "edges": []}
        try:
            key = KEY_SESSION_GRAPH.format(sid=session_id)
            data = self._client.get(key)
            if data is None:
                return {"nodes": [], "edges": []}
            return json_loads_flexible(data)
        except Exception as e:
            logger.error("Failed to get graph for %s: %s", session_id, e)
            return {"nodes": [], "edges": []}

    def update_graph(
        self,
        session_id: str,
        parent_vid: Optional[str],
        new_vid: str,
        operation: str,
        query: Optional[str] = None,
    ) -> bool:
        if not self.is_connected():
            return False
        try:
            graph = self.get_graph(session_id)
            append_lineage(graph, parent_vid, new_vid, operation, query)
            key = KEY_SESSION_GRAPH.format(sid=session_id)
            self._set_with_ttl(key, json.dumps(graph, default=str).encode("utf-8"), self.session_ttl)
            self.extend_ttl(session_id)
            return True
        except Exception as e:
            logger.error("Failed to update graph for %s: %s", session_id, e)
            return False

    def scan_keys(self, pattern: str) -> List[str]:
        return self._scan_keys(pattern)

    def count_keys(self, pattern: str) -> int:
        if self._client is None:
            return 0
        n = 0
        cursor = 0
        while True:
            cursor, batch = self._client.scan(cursor=cursor, match=pattern, count=500)
            n += len(batch)
            if cursor == 0:
                break
        return n
