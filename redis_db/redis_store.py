"""Core Redis operations using Upstash Redis SDK (REST API)."""

import time
import json
import base64
import logging
from typing import Any, Dict, List, Optional
import pandas as pd
from langfuse import observe

from .constants import (
    UPSTASH_REDIS_REST_URL, UPSTASH_REDIS_REST_TOKEN,
    SESSION_TTL, KEY_SESSION_TABLES, KEY_SESSION_META,
    KEY_VERSION_TABLES, KEY_SESSION_GRAPH
)
from .serializer import DataFrameSerializer

logger = logging.getLogger(__name__)


class RedisStore:
    """Session tables, metadata, versions, and lineage graph in Upstash Redis."""

    def __init__(
        self,
        redis_url: Optional[str] = None,
        redis_token: Optional[str] = None,
        session_ttl: Optional[int] = None,
        serializer: Optional[DataFrameSerializer] = None,
    ):
        self.redis_url = redis_url or UPSTASH_REDIS_REST_URL
        self.redis_token = redis_token or UPSTASH_REDIS_REST_TOKEN
        self.session_ttl = session_ttl or SESSION_TTL
        self.serializer = serializer or DataFrameSerializer()
        self.redis = None
        
        self._initialize_redis()
    
    def _initialize_redis(self) -> None:
        """Create Upstash REST client from URL/token or env."""
        try:
            from upstash_redis import Redis

            url = (self.redis_url or "").strip().strip('"').strip("'")
            token = (self.redis_token or "").strip().strip('"').strip("'")

            if url and token:
                self.redis = Redis(
                    url=url,
                    token=token,
                    allow_telemetry=False,
                    rest_retries=3,
                    rest_retry_interval=2.0,
                )
            else:
                self.redis = Redis.from_env(
                    allow_telemetry=False,
                    rest_retries=3,
                    rest_retry_interval=2.0,
                )

            self.redis.ping()
            logger.info("Connected to Upstash Redis")

        except ImportError:
            logger.error("upstash-redis not installed. Run: pip install upstash-redis")
            self.redis = None
        except Exception as e:
            logger.error("Upstash Redis init error: %s", e, exc_info=True)
            self.redis = None

    def probe_read_write(self) -> Dict[str, Any]:
        """Minimal SET/GET/DEL check for the REST client (debug endpoint)."""
        out: Dict[str, Any] = {"ping": False, "set_get_delete": False, "error": None}
        if not self.is_connected():
            out["error"] = "client not initialized or ping failed"
            return out
        key = "__data_assistant_probe__"
        try:
            self.redis.ping()
            out["ping"] = True
            self.redis.set(key, "ok", ex=15)
            val = self.redis.get(key)
            self.redis.delete(key)
            out["set_get_delete"] = val in ("ok", b"ok")
            if not out["set_get_delete"]:
                out["sample_value_repr"] = repr(val)[:200]
        except Exception as e:
            msg = str(e)
            out["error"] = msg
            if "NOPERM" in msg or "no permissions" in msg.lower():
                out["hint"] = (
                    "REST token is read-only or ACL-restricted (cannot SET). In Upstash: "
                    "Redis → your database → REST API → use the default read-write token, "
                    "not a read-only token. Update UPSTASH_REDIS_REST_TOKEN in .env and restart."
                )
            logger.error("Redis probe failed: %s", e, exc_info=True)
        return out

    def is_connected(self) -> bool:
        """True if client exists and PING succeeds."""
        if self.redis is None:
            return False
        try:
            self.redis.ping()
            return True
        except Exception:
            return False

    def scan_keys(self, pattern: str) -> List[str]:
        """Return all keys matching `pattern` (SCAN until cursor 0)."""
        if self.redis is None:
            return []
        out: List[str] = []
        cursor = 0
        while True:
            cursor, batch = self.redis.scan(cursor, match=pattern, count=100)
            out.extend(batch)
            if cursor == 0:
                break
        return out

    def count_keys(self, pattern: str) -> int:
        """Count keys matching `pattern` without materializing the full list."""
        if self.redis is None:
            return 0
        n = 0
        cursor = 0
        while True:
            cursor, batch = self.redis.scan(cursor, match=pattern, count=100)
            n += len(batch)
            if cursor == 0:
                break
        return n

    def _sync_version_ttls(self, session_id: str) -> None:
        """Refresh TTL on all version table keys for this session."""
        try:
            versions = self.list_versions(session_id)
            for version_id in versions:
                key_version = KEY_VERSION_TABLES.format(sid=session_id, vid=version_id)
                self.redis.expire(key_version, self.session_ttl)
        except Exception as e:
            logger.warning(f"Failed to sync version TTLs for {session_id}: {e}")
    
    @observe(name="redis_save_session", as_type="span")
    def save_session(
        self,
        session_id: str,
        tables: Dict[str, pd.DataFrame],
        metadata: Dict,
    ) -> bool:
        """Persist tables, metadata, and graph stub under one TTL."""
        if not self.is_connected():
            logger.error("Upstash Redis not connected")
            return False
        
        try:
            key_tables = KEY_SESSION_TABLES.format(sid=session_id)
            key_meta = KEY_SESSION_META.format(sid=session_id)
            key_graph = KEY_SESSION_GRAPH.format(sid=session_id)

            tables_bytes = self.serializer.serialize(tables)
            tables_b64 = base64.b64encode(tables_bytes).decode("utf-8")

            self.redis.setex(key_tables, self.session_ttl, tables_b64)
            self.redis.setex(
                key_meta, self.session_ttl, json.dumps(metadata, default=str)
            )
            if not self.redis.exists(key_graph):
                empty_graph = {"nodes": [], "edges": []}
                self.redis.setex(key_graph, self.session_ttl, json.dumps(empty_graph))
            else:
                self.redis.expire(key_graph, self.session_ttl)

            try:
                self._sync_version_ttls(session_id)
            except Exception as sync_e:
                logger.warning(
                    "TTL sync for version keys skipped (session saved): %s", sync_e
                )

            logger.info(
                f"Saved session {session_id} with {len(tables)} tables (TTL: {self.session_ttl}s)"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to save session {session_id}: {e}", exc_info=True)
            return False
    
    @observe(name="redis_load_session", as_type="span")
    def load_session(self, session_id: str) -> Optional[Dict[str, pd.DataFrame]]:
        """Load current session tables, or None if missing."""
        if not self.is_connected():
            return None
        
        try:
            key = KEY_SESSION_TABLES.format(sid=session_id)
            data = self.redis.get(key)
            
            if data is None:
                return None

            tables_bytes = base64.b64decode(data)
            return self.serializer.deserialize(tables_bytes)
            
        except Exception as e:
            logger.error(f"Failed to load session {session_id}: {e}")
            return None
    
    def get_metadata(self, session_id: str) -> Optional[Dict]:
        """Return JSON metadata for the session, or None."""
        if not self.is_connected():
            return None
        
        try:
            key = KEY_SESSION_META.format(sid=session_id)
            data = self.redis.get(key)
            
            if data is None:
                return None
            
            return json.loads(data)
            
        except Exception as e:
            logger.error(f"Failed to get metadata for {session_id}: {e}")
            return None
    
    def delete_session(self, session_id: str) -> bool:
        """Delete every key under `session:{id}:*`."""
        if not self.is_connected():
            return False

        try:
            all_keys = self.scan_keys(f"session:{session_id}:*")
            if not all_keys:
                logger.warning(f"No keys found for session {session_id}")
                return False
            
            deleted = self.redis.delete(*all_keys)
            
            logger.info(f"Deleted session {session_id} - removed {deleted} keys: {len(all_keys)} found")
            return deleted > 0
            
        except Exception as e:
            logger.error(f"Failed to delete session {session_id}: {e}")
            return False
    
    def session_exists(self, session_id: str) -> bool:
        if not self.is_connected():
            return False

        try:
            key = KEY_SESSION_TABLES.format(sid=session_id)
            return bool(self.redis.exists(key))
        except Exception as e:
            logger.error(f"Failed to check session {session_id}: {e}")
            return False
    
    def extend_ttl(self, session_id: str) -> bool:
        """Reset TTL on tables, meta, graph, and all version keys."""
        if not self.is_connected():
            return False
        
        try:
            key_tables = KEY_SESSION_TABLES.format(sid=session_id)
            key_meta = KEY_SESSION_META.format(sid=session_id)
            key_graph = KEY_SESSION_GRAPH.format(sid=session_id)
            
            self.redis.expire(key_tables, self.session_ttl)
            self.redis.expire(key_meta, self.session_ttl)
            self.redis.expire(key_graph, self.session_ttl)

            versions = self.list_versions(session_id)
            for version_id in versions:
                key_version = KEY_VERSION_TABLES.format(sid=session_id, vid=version_id)
                self.redis.expire(key_version, self.session_ttl)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to extend TTL for {session_id}: {e}")
            return False
    
    def list_sessions(self) -> List[Dict]:
        """Sessions that still have a `*:tables` key and loadable metadata."""
        if not self.is_connected():
            return []

        try:
            sessions = []
            pattern = KEY_SESSION_TABLES.replace("{sid}", "*")
            for key in self.scan_keys(pattern):
                try:
                    session_id = key.split(":")[1]
                    metadata = self.get_metadata(session_id)
                    if metadata:
                        sessions.append(
                            {"session_id": session_id, "metadata": metadata}
                        )
                except Exception:
                    continue
            return sessions

        except Exception as e:
            logger.error(f"Failed to list sessions: {e}")
            return []

    @observe(name="redis_save_version", as_type="span")
    def save_version(
        self,
        session_id: str,
        version_id: str,
        tables: Dict[str, pd.DataFrame]
    ) -> bool:
        """Snapshot tables under `session:{sid}:version:{vid}:tables`."""
        if not self.is_connected():
            logger.error("Upstash Redis not connected")
            return False

        try:
            key = KEY_VERSION_TABLES.format(sid=session_id, vid=version_id)

            tables_bytes = self.serializer.serialize(tables)
            tables_b64 = base64.b64encode(tables_bytes).decode("utf-8")

            self.redis.setex(key, self.session_ttl, tables_b64)
            self.extend_ttl(session_id)
            
            logger.info(f"Saved version {version_id} for session {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save version {version_id} for {session_id}: {e}")
            return False
    
    @observe(name="redis_load_version", as_type="span")
    def load_version(
        self,
        session_id: str,
        version_id: str
    ) -> Optional[Dict[str, pd.DataFrame]]:
        """Load a version snapshot; refreshes TTL on success."""
        if not self.is_connected():
            return None
        
        try:
            key = KEY_VERSION_TABLES.format(sid=session_id, vid=version_id)
            data = self.redis.get(key)
            
            if data is None:
                return None

            tables_bytes = base64.b64decode(data)
            tables = self.serializer.deserialize(tables_bytes)
            self.extend_ttl(session_id)
            
            return tables
            
        except Exception as e:
            logger.error(f"Failed to load version {version_id} for {session_id}: {e}")
            return None
    
    def delete_version(self, session_id: str, version_id: str) -> bool:
        if not self.is_connected():
            return False
        
        try:
            key = KEY_VERSION_TABLES.format(sid=session_id, vid=version_id)
            deleted = self.redis.delete(key)
            logger.info(f"Deleted version {version_id} for session {session_id}")
            return deleted > 0
            
        except Exception as e:
            logger.error(f"Failed to delete version {version_id} for {session_id}: {e}")
            return False
    
    def list_versions(self, session_id: str) -> List[str]:
        """Version ids from keys `session:{sid}:version:{vid}:tables`."""
        if not self.is_connected():
            return []

        try:
            versions = []
            pattern = KEY_VERSION_TABLES.format(sid=session_id, vid="*")
            for key in self.scan_keys(pattern):
                try:
                    parts = key.split(":")
                    if len(parts) >= 5 and parts[2] == "version":
                        versions.append(parts[3])
                except Exception:
                    continue
            return versions

        except Exception as e:
            logger.error(f"Failed to list versions for {session_id}: {e}")
            return []

    def get_graph(self, session_id: str) -> Dict[str, Any]:
        """Lineage graph `nodes` / `edges`; empty dicts if missing."""
        if not self.is_connected():
            return {"nodes": [], "edges": []}
        
        try:
            key = KEY_SESSION_GRAPH.format(sid=session_id)
            data = self.redis.get(key)
            
            if data is None:
                return {"nodes": [], "edges": []}
            
            graph = json.loads(data)
            return graph
            
        except Exception as e:
            logger.error(f"Failed to get graph for {session_id}: {e}")
            return {"nodes": [], "edges": []}
    
    def update_graph(
        self,
        session_id: str,
        parent_vid: Optional[str],
        new_vid: str,
        operation: str,
        query: Optional[str] = None
    ) -> bool:
        """Append a version node and optional parent→child edge."""
        if not self.is_connected():
            return False

        try:
            graph = self.get_graph(session_id)

            new_node = {
                "id": new_vid,
                "label": f"{new_vid}: {operation}" if operation else new_vid,
                "operation": operation,
                "query": query,
                "timestamp": time.time()
            }
            graph["nodes"].append(new_node)

            if parent_vid:
                new_edge = {
                    "from": parent_vid,
                    "to": new_vid,
                    "label": operation or "Operation"
                }
                graph["edges"].append(new_edge)

            key = KEY_SESSION_GRAPH.format(sid=session_id)
            self.redis.setex(key, self.session_ttl, json.dumps(graph, default=str))
            self.extend_ttl(session_id)
            
            logger.info(f"Updated graph for {session_id}: added {new_vid}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update graph for {session_id}: {e}")
            return False
    
    def set_current_version(self, session_id: str, version_id: str) -> bool:
        """Set `current_version` in session metadata."""
        if not self.is_connected():
            return False

        try:
            metadata = self.get_metadata(session_id) or {}
            metadata["current_version"] = version_id

            key_meta = KEY_SESSION_META.format(sid=session_id)
            self.redis.setex(
                key_meta, self.session_ttl, json.dumps(metadata, default=str)
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to set current version for {session_id}: {e}")
            return False
    
    def get_current_version(self, session_id: str) -> Optional[str]:
        metadata = self.get_metadata(session_id)
        if metadata:
            return metadata.get("current_version")
        return None
