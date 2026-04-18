"""Shared Langfuse helpers for tracing and LangChain callbacks."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

# Applied before OTLP exporter reads env (seconds; avoids noisy 5s timeouts on slow links).
os.environ.setdefault("OTEL_EXPORTER_OTLP_TRACES_TIMEOUT", "30")
os.environ.setdefault("OTEL_EXPORTER_OTLP_TIMEOUT", "30")

from langfuse import get_client
from langfuse.langchain import CallbackHandler

_client = None


def _otel_span_is_recording() -> bool:
    try:
        from opentelemetry import trace as otel_trace_api

        span = otel_trace_api.get_current_span()
        return span is not otel_trace_api.INVALID_SPAN and span.is_recording()
    except Exception:
        return False


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
    """Update the current trace with optional metadata (no-op if no active OTEL span)."""
    if not _otel_span_is_recording():
        return
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
        if _otel_span_is_recording():
            trace_id = client.get_current_trace_id() or client.create_trace_id()
            update_trace_context(
                session_id=session_id,
                user_id=user_id,
                tags=tags,
                metadata=metadata,
            )
        else:
            trace_id = client.create_trace_id()
        trace_context = {"trace_id": trace_id}
        return CallbackHandler(trace_context=trace_context, update_trace=update_trace)
    except Exception:
        return None
