"""Shared helpers for reading from graph state. Keeps node code DRY and intent clear."""

from typing import Dict, Any


def get_current_query(state: Dict[str, Any]) -> str:
    """
    Return the query string to use for this turn.
    Prefers effective_query (resolved follow-up or clarification); otherwise last message content.
    Use in nodes (analyzer, insight, planner, responder) for consistent "what did the user ask?".
    """
    effective = state.get("effective_query")
    if effective and isinstance(effective, str) and str(effective).strip():
        return str(effective).strip()
    messages = state.get("messages") or []
    if not messages:
        return ""
    last = messages[-1]
    content = getattr(last, "content", None)
    if content is not None:
        return str(content).strip()
    return str(last).strip()
