"""Shared session-store logic (no Redis client)."""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def json_loads_flexible(raw: Any) -> Any:
    """Parse JSON from Upstash (str) or redis-py (bytes)."""
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode("utf-8")
    return json.loads(raw)


def version_ids_from_key_names(keys: List[str]) -> List[str]:
    """Extract version ids from keys like ``session:{sid}:version:{vid}:tables``."""
    out: List[str] = []
    for key in keys:
        parts = key.split(":")
        if len(parts) >= 5 and parts[2] == "version":
            out.append(parts[3])
    return out


def append_lineage(
    graph: Dict[str, Any],
    parent_vid: Optional[str],
    new_vid: str,
    operation: str,
    query: Optional[str],
) -> None:
    """Append a node and optional edge to a lineage graph (mutates ``graph``)."""
    graph.setdefault("nodes", []).append(
        {
            "id": new_vid,
            "label": f"{new_vid}: {operation}" if operation else new_vid,
            "operation": operation,
            "query": query,
            "timestamp": time.time(),
        }
    )
    if parent_vid:
        graph.setdefault("edges", []).append(
            {"from": parent_vid, "to": new_vid, "label": operation or "Operation"}
        )


class CurrentVersionMixin:
    """``current_version`` field in session metadata; subclasses implement ``_write_metadata``."""

    def get_current_version(self, session_id: str) -> Optional[str]:
        meta = self.get_metadata(session_id)
        return meta.get("current_version") if meta else None

    def set_current_version(self, session_id: str, version_id: str) -> bool:
        if not self.is_connected():
            return False
        try:
            meta = self.get_metadata(session_id) or {}
            meta["current_version"] = version_id
            return bool(self._write_metadata(session_id, meta))
        except Exception as e:
            logger.error("Failed to set current version for %s: %s", session_id, e)
            return False
