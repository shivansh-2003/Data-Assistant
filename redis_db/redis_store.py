"""Session storage via Upstash Redis REST SDK."""

import base64
import json
import logging
import time as _time
from typing import Any, Dict, List, Optional

import pandas as pd

from .constants import (
    KEY_SESSION_GRAPH,
    KEY_SESSION_META,
    KEY_SESSION_TABLES,
    KEY_VERSION_TABLES,
    SESSION_TTL,
    UPSTASH_REDIS_REST_TOKEN,
    UPSTASH_REDIS_REST_URL,
)
from .serializer import DataFrameSerializer
from .session_store import BaseSessionStore
from .store_common import append_lineage, json_loads_flexible, version_ids_from_key_names

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Per-operation latency ceilings (seconds).  Exceeded → WARNING in logs.
# ---------------------------------------------------------------------------
_BENCHMARKS: dict[str, float] = {
    "redis.save_session":             0.50,
    "redis.save_session.serialize":   0.15,
    "redis.save_session.redis_set":   0.30,
    "redis.load_session":             0.50,
    "redis.load_session.redis_get":   0.30,
    "redis.load_session.deserialize": 0.15,
    "redis.save_version":             0.50,
    "redis.load_version":             0.50,
    "redis.snapshot_copy":            0.10,
    "redis.restore_copy":             0.10,
    "redis.update_graph":             0.40,
    "redis.extend_ttl":               0.20,
}


def _perf_warn(name: str, elapsed: float, session_id: str = "") -> None:
    threshold = _BENCHMARKS.get(name)
    if threshold and elapsed > threshold:
        logger.warning(
            "[PERF][SLOW] %-40s  session=%s  %.3fs elapsed  (benchmark: %.3fs  |  %.1fx over)",
            name, session_id, elapsed, threshold, elapsed / threshold,
        )


class RedisStore(BaseSessionStore):
    """Upstash REST: session tables, metadata, versions, lineage graph."""

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
        if self.redis is None:
            return False
        try:
            self.redis.ping()
            return True
        except Exception:
            return False

    def scan_keys(self, pattern: str) -> List[str]:
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
        try:
            for version_id in self.list_versions(session_id):
                key_version = KEY_VERSION_TABLES.format(sid=session_id, vid=version_id)
                self.redis.expire(key_version, self.session_ttl)
        except Exception as e:
            logger.warning("Failed to sync version TTLs for %s: %s", session_id, e)

    def _write_metadata(self, session_id: str, metadata: Dict) -> bool:
        key = KEY_SESSION_META.format(sid=session_id)
        self.redis.setex(key, self.session_ttl, json.dumps(metadata, default=str))
        return True

    def save_session(
        self,
        session_id: str,
        tables: Dict[str, pd.DataFrame],
        metadata: Dict,
    ) -> bool:
        """
        Benchmark: < 0.5 s total.
        serialize < 0.15 s, redis SET < 0.30 s.
        """
        if not self.is_connected():
            logger.error("Upstash Redis not connected")
            return False

        _t0 = _time.perf_counter()
        logger.info(
            "[PERF] redis.save_session START  session=%s  table_count=%d",
            session_id, len(tables),
        )

        try:
            key_tables = KEY_SESSION_TABLES.format(sid=session_id)
            key_meta = KEY_SESSION_META.format(sid=session_id)
            key_graph = KEY_SESSION_GRAPH.format(sid=session_id)

            # ── serialize ─────────────────────────────────────────────────────
            _t_ser = _time.perf_counter()
            tables_bytes = self.serializer.serialize(tables)
            tables_b64 = base64.b64encode(tables_bytes).decode("utf-8")
            _t_ser_elapsed = _time.perf_counter() - _t_ser
            payload_kb = len(tables_b64) / 1024
            logger.info(
                "[PERF] redis.save_session.serialize  session=%s  duration=%.3fs  payload_kb=%.1f",
                session_id, _t_ser_elapsed, payload_kb,
            )
            _perf_warn("redis.save_session.serialize", _t_ser_elapsed, session_id)

            # ── Redis SET ─────────────────────────────────────────────────────
            _t_set = _time.perf_counter()
            self.redis.setex(key_tables, self.session_ttl, tables_b64)
            self.redis.setex(key_meta, self.session_ttl, json.dumps(metadata, default=str))
            if not self.redis.exists(key_graph):
                self.redis.setex(key_graph, self.session_ttl, json.dumps({"nodes": [], "edges": []}))
            else:
                self.redis.expire(key_graph, self.session_ttl)
            _t_set_elapsed = _time.perf_counter() - _t_set
            logger.info(
                "[PERF] redis.save_session.redis_set  session=%s  duration=%.3fs",
                session_id, _t_set_elapsed,
            )
            _perf_warn("redis.save_session.redis_set", _t_set_elapsed, session_id)

            try:
                self._sync_version_ttls(session_id)
            except Exception as sync_e:
                logger.warning("TTL sync for version keys skipped (session saved): %s", sync_e)

            _t_total = _time.perf_counter() - _t0
            logger.info(
                "[PERF] redis.save_session END  session=%s  serialize=%.3fs  redis_set=%.3fs  total=%.3fs",
                session_id, _t_ser_elapsed, _t_set_elapsed, _t_total,
            )
            _perf_warn("redis.save_session", _t_total, session_id)
            logger.info(
                "Saved session %s with %d tables (TTL: %ss)",
                session_id, len(tables), self.session_ttl,
            )
            return True

        except Exception as e:
            logger.error("Failed to save session %s: %s", session_id, e, exc_info=True)
            return False

    def load_session(self, session_id: str) -> Optional[Dict[str, pd.DataFrame]]:
        """
        Benchmark: < 0.5 s total.
        redis GET < 0.30 s, deserialize < 0.15 s.
        """
        if not self.is_connected():
            return None

        _t0 = _time.perf_counter()
        logger.info("[PERF] redis.load_session START  session=%s", session_id)

        try:
            key = KEY_SESSION_TABLES.format(sid=session_id)

            # ── Redis GET ─────────────────────────────────────────────────────
            _t_get = _time.perf_counter()
            data = self.redis.get(key)
            _t_get_elapsed = _time.perf_counter() - _t_get
            logger.info(
                "[PERF] redis.load_session.redis_get  session=%s  duration=%.3fs  found=%s",
                session_id, _t_get_elapsed, data is not None,
            )
            _perf_warn("redis.load_session.redis_get", _t_get_elapsed, session_id)

            if data is None:
                return None

            # ── deserialize ───────────────────────────────────────────────────
            _t_des = _time.perf_counter()
            tables_bytes = base64.b64decode(data)
            result = self.serializer.deserialize(tables_bytes)
            _t_des_elapsed = _time.perf_counter() - _t_des
            logger.info(
                "[PERF] redis.load_session.deserialize  session=%s  duration=%.3fs  table_count=%d",
                session_id, _t_des_elapsed, len(result) if result else 0,
            )
            _perf_warn("redis.load_session.deserialize", _t_des_elapsed, session_id)

            _t_total = _time.perf_counter() - _t0
            logger.info(
                "[PERF] redis.load_session END  session=%s  redis_get=%.3fs  deserialize=%.3fs  total=%.3fs",
                session_id, _t_get_elapsed, _t_des_elapsed, _t_total,
            )
            _perf_warn("redis.load_session", _t_total, session_id)
            return result

        except Exception as e:
            logger.error("Failed to load session %s: %s", session_id, e)
            return None

    def get_metadata(self, session_id: str) -> Optional[Dict]:
        if not self.is_connected():
            return None

        try:
            key = KEY_SESSION_META.format(sid=session_id)
            data = self.redis.get(key)

            if data is None:
                return None

            return json.loads(data)

        except Exception as e:
            logger.error("Failed to get metadata for %s: %s", session_id, e)
            return None

    def delete_session(self, session_id: str) -> bool:
        if not self.is_connected():
            return False

        try:
            all_keys = self.scan_keys(f"session:{session_id}:*")
            if not all_keys:
                logger.warning("No keys found for session %s", session_id)
                return False

            deleted = self.redis.delete(*all_keys)

            logger.info(
                "Deleted session %s - removed %d keys: %d found",
                session_id,
                deleted,
                len(all_keys),
            )
            return deleted > 0

        except Exception as e:
            logger.error("Failed to delete session %s: %s", session_id, e)
            return False

    def session_exists(self, session_id: str) -> bool:
        if not self.is_connected():
            return False

        try:
            key = KEY_SESSION_TABLES.format(sid=session_id)
            return bool(self.redis.exists(key))
        except Exception as e:
            logger.error("Failed to check session %s: %s", session_id, e)
            return False

    def extend_ttl(self, session_id: str) -> bool:
        if not self.is_connected():
            return False

        try:
            key_tables = KEY_SESSION_TABLES.format(sid=session_id)
            key_meta = KEY_SESSION_META.format(sid=session_id)
            key_graph = KEY_SESSION_GRAPH.format(sid=session_id)

            self.redis.expire(key_tables, self.session_ttl)
            self.redis.expire(key_meta, self.session_ttl)
            self.redis.expire(key_graph, self.session_ttl)
            self._sync_version_ttls(session_id)

            return True

        except Exception as e:
            logger.error("Failed to extend TTL for %s: %s", session_id, e)
            return False

    def list_sessions(self) -> List[Dict]:
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
                        sessions.append({"session_id": session_id, "metadata": metadata})
                except Exception:
                    continue
            return sessions

        except Exception as e:
            logger.error("Failed to list sessions: %s", e)
            return []

    def save_version(
        self,
        session_id: str,
        version_id: str,
        tables: Dict[str, pd.DataFrame],
    ) -> bool:
        """
        Fallback path when Redis COPY is unavailable.
        Benchmark: < 0.5 s (same budget as save_session).
        """
        if not self.is_connected():
            logger.error("Upstash Redis not connected")
            return False

        _t0 = _time.perf_counter()
        logger.info(
            "[PERF] redis.save_version START  session=%s  version=%s",
            session_id, version_id,
        )
        try:
            key = KEY_VERSION_TABLES.format(sid=session_id, vid=version_id)

            _t_ser = _time.perf_counter()
            tables_bytes = self.serializer.serialize(tables)
            tables_b64 = base64.b64encode(tables_bytes).decode("utf-8")
            _t_ser_e = _time.perf_counter() - _t_ser

            _t_set = _time.perf_counter()
            self.redis.setex(key, self.session_ttl, tables_b64)
            _t_set_e = _time.perf_counter() - _t_set

            self.extend_ttl(session_id)

            _t_total = _time.perf_counter() - _t0
            logger.info(
                "[PERF] redis.save_version END  session=%s  version=%s  "
                "serialize=%.3fs  redis_set=%.3fs  total=%.3fs",
                session_id, version_id, _t_ser_e, _t_set_e, _t_total,
            )
            _perf_warn("redis.save_version", _t_total, session_id)
            logger.info("Saved version %s for session %s", version_id, session_id)
            return True

        except Exception as e:
            logger.error("Failed to save version %s for %s: %s", version_id, session_id, e)
            return False

    def load_version(
        self,
        session_id: str,
        version_id: str,
    ) -> Optional[Dict[str, pd.DataFrame]]:
        """
        Fallback path when Redis COPY is unavailable.
        Benchmark: < 0.5 s (same budget as load_session).
        """
        if not self.is_connected():
            return None

        _t0 = _time.perf_counter()
        logger.info(
            "[PERF] redis.load_version START  session=%s  version=%s",
            session_id, version_id,
        )
        try:
            key = KEY_VERSION_TABLES.format(sid=session_id, vid=version_id)

            _t_get = _time.perf_counter()
            data = self.redis.get(key)
            _t_get_e = _time.perf_counter() - _t_get

            if data is None:
                logger.info(
                    "[PERF] redis.load_version END  session=%s  version=%s  not_found  total=%.3fs",
                    session_id, version_id, _time.perf_counter() - _t0,
                )
                return None

            _t_des = _time.perf_counter()
            tables_bytes = base64.b64decode(data)
            tables = self.serializer.deserialize(tables_bytes)
            _t_des_e = _time.perf_counter() - _t_des

            self.extend_ttl(session_id)

            _t_total = _time.perf_counter() - _t0
            logger.info(
                "[PERF] redis.load_version END  session=%s  version=%s  "
                "redis_get=%.3fs  deserialize=%.3fs  total=%.3fs",
                session_id, version_id, _t_get_e, _t_des_e, _t_total,
            )
            _perf_warn("redis.load_version", _t_total, session_id)
            return tables

        except Exception as e:
            logger.error("Failed to load version %s for %s: %s", version_id, session_id, e)
            return None

    def delete_version(self, session_id: str, version_id: str) -> bool:
        if not self.is_connected():
            return False

        try:
            key = KEY_VERSION_TABLES.format(sid=session_id, vid=version_id)
            deleted = self.redis.delete(key)
            logger.info("Deleted version %s for session %s", version_id, session_id)
            return deleted > 0

        except Exception as e:
            logger.error("Failed to delete version %s for %s: %s", version_id, session_id, e)
            return False

    def list_versions(self, session_id: str) -> List[str]:
        if not self.is_connected():
            return []

        try:
            pattern = KEY_VERSION_TABLES.format(sid=session_id, vid="*")
            return version_ids_from_key_names(self.scan_keys(pattern))

        except Exception as e:
            logger.error("Failed to list versions for %s: %s", session_id, e)
            return []

    def get_graph(self, session_id: str) -> Dict[str, Any]:
        if not self.is_connected():
            return {"nodes": [], "edges": []}

        try:
            key = KEY_SESSION_GRAPH.format(sid=session_id)
            data = self.redis.get(key)

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
        """
        Read-modify-write the version lineage graph via a pipelined SET+EXPIRE.
        Benchmark: < 0.40 s (GET ~0.15 s + pipelined SET/EXPIRE ~0.20 s).
        """
        if not self.is_connected():
            return False

        _t0 = _time.perf_counter()
        logger.info(
            "[PERF] redis.update_graph START  session=%s  new_vid=%s  parent=%s",
            session_id, new_vid, parent_vid,
        )
        try:
            # ── GET graph ────────────────────────────────────────────────────
            _t_get = _time.perf_counter()
            graph = self.get_graph(session_id)
            _t_get_e = _time.perf_counter() - _t_get

            append_lineage(graph, parent_vid, new_vid, operation, query)

            # ── pipelined SET + EXPIRE ────────────────────────────────────────
            key_graph  = KEY_SESSION_GRAPH.format(sid=session_id)
            key_tables = KEY_SESSION_TABLES.format(sid=session_id)
            key_meta   = KEY_SESSION_META.format(sid=session_id)
            _t_set = _time.perf_counter()
            pipe = self.redis.pipeline()
            pipe.setex(key_graph, self.session_ttl, json.dumps(graph, default=str))
            pipe.expire(key_tables, self.session_ttl)
            pipe.expire(key_meta, self.session_ttl)
            pipe.exec()
            _t_set_e = _time.perf_counter() - _t_set

            _t_total = _time.perf_counter() - _t0
            logger.info(
                "[PERF] redis.update_graph END  session=%s  new_vid=%s  "
                "get=%.3fs  pipeline_set=%.3fs  total=%.3fs  node_count=%d",
                session_id, new_vid, _t_get_e, _t_set_e, _t_total,
                len(graph.get("nodes", [])),
            )
            _perf_warn("redis.update_graph", _t_total, session_id)
            logger.info("Updated graph for %s: added %s", session_id, new_vid)
            return True

        except Exception as e:
            logger.error("Failed to update graph for %s: %s", session_id, e)
            return False

    def snapshot_session_as_version(self, session_id: str, version_id: str) -> bool:
        """
        Server-side Redis COPY — benchmark: < 0.10 s.
        Falls back to serialize/deserialize if COPY unavailable.
        """
        if not self.is_connected():
            return False

        src = KEY_SESSION_TABLES.format(sid=session_id)
        dst = KEY_VERSION_TABLES.format(sid=session_id, vid=version_id)

        _t0 = _time.perf_counter()
        logger.info(
            "[PERF] redis.snapshot_copy START  session=%s  version=%s  method=COPY",
            session_id, version_id,
        )
        try:
            if not self.redis.exists(src):
                return False
            ok = self.redis.copy(src, dst, replace=True)
            if ok:
                self.redis.expire(dst, self.session_ttl)
                _t_elapsed = _time.perf_counter() - _t0
                logger.info(
                    "[PERF] redis.snapshot_copy END  session=%s  version=%s  method=COPY  duration=%.3fs",
                    session_id, version_id, _t_elapsed,
                )
                _perf_warn("redis.snapshot_copy", _t_elapsed, session_id)
                return True
        except Exception as e:
            logger.warning("Redis COPY snapshot failed, using load/save fallback: %s", e)
            logger.warning(
                "[PERF] redis.snapshot_copy FALLBACK  session=%s  version=%s  reason=%s",
                session_id, version_id, e,
            )

        # Fallback: full serialize round-trip
        tables = self.load_session(session_id)
        if tables is None:
            return False
        return self.save_version(session_id, version_id, tables)

    def restore_version_as_session(self, session_id: str, version_id: str) -> bool:
        """
        Server-side Redis COPY in reverse — benchmark: < 0.10 s.
        Falls back to load_version + save_session if COPY unavailable.
        """
        if not self.is_connected():
            return False

        src = KEY_VERSION_TABLES.format(sid=session_id, vid=version_id)
        dst = KEY_SESSION_TABLES.format(sid=session_id)

        _t0 = _time.perf_counter()
        logger.info(
            "[PERF] redis.restore_copy START  session=%s  version=%s  method=COPY",
            session_id, version_id,
        )
        try:
            if not self.redis.exists(src):
                logger.info(
                    "[PERF] redis.restore_copy END  session=%s  version=%s  not_found",
                    session_id, version_id,
                )
                return False
            ok = self.redis.copy(src, dst, replace=True)
            if ok:
                self.redis.expire(dst, self.session_ttl)
                _t_elapsed = _time.perf_counter() - _t0
                logger.info(
                    "[PERF] redis.restore_copy END  session=%s  version=%s  method=COPY  duration=%.3fs",
                    session_id, version_id, _t_elapsed,
                )
                _perf_warn("redis.restore_copy", _t_elapsed, session_id)
                return True
        except Exception as e:
            logger.warning("Redis COPY restore failed, using load/save fallback: %s", e)
            logger.warning(
                "[PERF] redis.restore_copy FALLBACK  session=%s  version=%s  reason=%s",
                session_id, version_id, e,
            )

        # Fallback: full serialize round-trip
        tables = self.load_version(session_id, version_id)
        if tables is None:
            return False
        meta = self.get_metadata(session_id) or {}
        return self.save_session(session_id, tables, meta)

    # ── Raw KV helpers (T-3 transform cache) ────────────────────────────────
    def raw_get(self, key: str) -> Optional[Any]:
        if not self.is_connected():
            return None
        try:
            return self.redis.get(key)
        except Exception as e:
            logger.warning("raw_get(%s) failed: %s", key, e)
            return None

    def raw_setex(self, key: str, ttl_seconds: int, value: Any) -> bool:
        if not self.is_connected():
            return False
        try:
            # Upstash REST accepts str values; coerce bytes to utf-8 if needed
            if isinstance(value, bytes):
                value = value.decode("utf-8", errors="replace")
            self.redis.setex(key, ttl_seconds, value)
            return True
        except Exception as e:
            logger.warning("raw_setex(%s) failed: %s", key, e)
            return False
