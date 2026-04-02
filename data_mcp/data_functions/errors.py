"""
Structured error payloads for MCP tools (context + suggestions).
"""

from __future__ import annotations

import re
from difflib import get_close_matches
from typing import Any, Dict, List, Optional

from .core import get_table_data, list_available_tables


def format_error_with_context(
    error: str,
    session_id: str,
    table_name: str = "current",
    suggestions: Optional[List[str]] = None,
    mention: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Build a consistent failure dict with session/table context and optional column fuzzy-match.
    """
    available_tables = list_available_tables(session_id)
    response: Dict[str, Any] = {
        "success": False,
        "error": error,
        "context": {
            "session_id": session_id,
            "table_name": table_name,
            "available_tables": available_tables,
        },
    }

    df = get_table_data(session_id, table_name)
    if df is not None:
        cols = list(df.columns)
        response["context"]["columns"] = cols
        response["context"]["shape"] = {"rows": len(df), "columns": len(df.columns)}

        needle = mention
        if needle is None and "column" in error.lower():
            m = re.search(r"'([^']+)'", error)
            if m:
                needle = m.group(1)
        if needle:
            matches = get_close_matches(needle, cols, n=3, cutoff=0.55)
            if matches:
                response["suggestions"] = {
                    "did_you_mean": matches,
                    "message": f"Unknown or ambiguous column '{needle}'. Did you mean one of these?",
                }

    if suggestions:
        if "suggestions" in response:
            response["suggestions"]["hints"] = suggestions
        else:
            response["suggestions"] = {"hints": suggestions}

    return response
