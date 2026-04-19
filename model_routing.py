"""Shared query-complexity tiering for MAIN vs MINI models.

Used by:
  - ``mcp_client._select_model`` (NL Transform tab)
  - ``chatbot.llm_registry.get_analyzer_llm`` (chatbot analyzer tiering)

See ``context/MODEL_STRATEGY.md`` §4. Keep keyword sets in sync when tuning.
"""

from __future__ import annotations

from typing import Literal

TIER1_KEYWORDS = frozenset(
    {
        "remove",
        "drop",
        "filter",
        "sort",
        "rename",
        "fill",
        "replace",
        "select columns",
        "keep only",
        "delete column",
        "reset index",
        "lowercase",
        "uppercase",
        "strip",
        "cast",
        "convert to",
        "remove duplicates",
        "drop duplicates",
        "null",
        "missing",
    }
)

TIER3_KEYWORDS = frozenset(
    {
        "year-over-year",
        "yoy",
        "cohort",
        "retention",
        "funnel",
        "rolling",
        "cumulative",
        "rank within",
        "outlier",
        "anomaly",
        "correlation",
        "pivot",
        "merge",
        "join",
        "multi-table",
        "percentile",
        "growth rate",
        "month-over-month",
        "mom",
    }
)


def select_main_or_mini_tier(query: str) -> Literal["main", "mini"]:
    """Return ``mini`` for simple single-op queries, else ``main``.

    Mirrors the historical ``mcp_client._select_model`` policy without
    importing env-specific model names.
    """
    q = (query or "").lower().strip()
    if any(kw in q for kw in TIER3_KEYWORDS):
        return "main"
    words = q.split()
    if len(words) <= 12 and any(kw in q for kw in TIER1_KEYWORDS):
        return "mini"
    return "main"
