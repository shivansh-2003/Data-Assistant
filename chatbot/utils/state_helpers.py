"""Shared helpers for reading from graph state. Keeps node code DRY and intent clear."""

from typing import Any, Dict, List


def get_tool_calls(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return ``state[\"tool_calls\"]`` as a list.

    LangGraph merges thread inputs where ``tool_calls`` is explicitly ``None``;
    ``dict.get(\"tool_calls\", [])`` then returns ``None`` (key present), which
    breaks ``for tc in tool_calls``. Always normalize here.
    """
    raw = state.get("tool_calls")
    if raw is None:
        return []
    if not isinstance(raw, list):
        return []
    return raw


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
