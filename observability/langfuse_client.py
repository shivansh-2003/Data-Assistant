"""Shared Langfuse helpers for tracing and LangChain callbacks."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from langfuse import get_client
from langfuse.langchain import CallbackHandler

_client = None


def get_langfuse_client():
    """Return a cached Langfuse client instance."""
    global _client
    if _client is None:
        _client = get_client()
    return _client


def update_trace_context(
    *,
    session_id: Optional[str] = None,
    user_id: Optional[str] = None,
    tags: Optional[List[str]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    name: Optional[str] = None,
) -> None:
    """Update the current trace with optional metadata."""
    client = get_langfuse_client()
    payload: Dict[str, Any] = {}
    if session_id:
        payload["session_id"] = session_id
    if user_id:
        payload["user_id"] = user_id
    if tags:
        payload["tags"] = tags
    if metadata:
        payload["metadata"] = metadata
    if name:
        payload["name"] = name
    if not payload:
        return
    try:
        client.update_current_trace(**payload)
    except Exception:
        # If Langfuse is not configured, skip silently.
        return


def build_langchain_callback(
    *,
    session_id: Optional[str] = None,
    user_id: Optional[str] = None,
    tags: Optional[List[str]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    update_trace: bool = True,
) -> Optional[CallbackHandler]:
    """Build a Langfuse LangChain CallbackHandler tied to the current trace."""
    client = get_langfuse_client()
    try:
        update_trace_context(
            session_id=session_id,
            user_id=user_id,
            tags=tags,
            metadata=metadata,
        )
        trace_id = client.get_current_trace_id() or client.create_trace_id()
        trace_context = {"trace_id": trace_id}
        return CallbackHandler(trace_context=trace_context, update_trace=update_trace)
    except Exception:
        return None

