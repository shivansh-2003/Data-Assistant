"""LLM Registry — singleton pattern for ChatOpenAI instances.

One instance per (model_key, temperature, max_tokens) combination is created and
reused for the lifetime of the process. All nodes import getters from here
instead of constructing ChatOpenAI() inline, eliminating the per-call overhead
of API-key validation, HTTP-client initialisation, and metadata fetch (~200ms/node).

Model assignment:
  main  → gpt-5                  (Analyzer default, Planner, Code Gen — schema reasoning + code gen)
  mini  → gpt-5-mini-2025-08-07  (Router, Resolver, Summarizer, Suggestions, Small Talk;
                                  Analyzer for short simple-op queries when CHATBOT_ANALYZER_TIER=1)

Override via environment variables without code changes:
  MAIN_MODEL, MINI_MODEL, ROUTER_MODEL, SUGGESTION_MODEL, CONTEXT_RESOLVER_MODEL
"""

import os
from typing import Dict, Optional, Tuple

from langchain_openai import ChatOpenAI

from model_routing import select_main_or_mini_tier

_registry: Dict[Tuple, ChatOpenAI] = {}

# Resolve model names once at import time (env vars must be set before first import)
_MODELS: Dict[str, str] = {
    "main": os.getenv("MAIN_MODEL", os.getenv("OPENAI_MODEL", "gpt-5")),
    "mini": os.getenv("MINI_MODEL", "gpt-5-mini-2025-08-07"),
    "router": os.getenv("ROUTER_MODEL", os.getenv("MINI_MODEL", "gpt-5-mini-2025-08-07")),
    "suggestion": os.getenv("SUGGESTION_MODEL", os.getenv("MINI_MODEL", "gpt-5-mini-2025-08-07")),
    "resolver": os.getenv("CONTEXT_RESOLVER_MODEL", os.getenv("MINI_MODEL", "gpt-5-mini-2025-08-07")),
}


def get_llm(
    model_key: str = "main",
    temperature: float = 0.1,
    max_tokens: Optional[int] = None,
) -> ChatOpenAI:
    """Return a cached ChatOpenAI instance for the given configuration."""
    cache_key = (model_key, temperature, max_tokens)
    if cache_key not in _registry:
        model_name = _MODELS.get(model_key, _MODELS["main"])
        kwargs: dict = dict(
            model=model_name,
            temperature=temperature,
            api_key=os.getenv("OPENAI_API_KEY"),
        )
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        _registry[cache_key] = ChatOpenAI(**kwargs)
    return _registry[cache_key]


# ---------------------------------------------------------------------------
# Pre-built shortcuts — import these in node files
# ---------------------------------------------------------------------------

def get_router_llm() -> ChatOpenAI:
    """gpt-5-mini, temp=0.0 — structured intent + entities; needs headroom so
    ``with_structured_output`` does not hit ``length`` before JSON completes."""
    return get_llm("router", temperature=0.0, max_tokens=1024)


def get_analyzer_llm(query: Optional[str] = None) -> ChatOpenAI:
    """Tool-selection LLM: ``main`` (gpt-5) by default; ``mini`` for simple queries.

    Tiering uses the same heuristics as NL Transform (``model_routing``).
    Disable with ``CHATBOT_ANALYZER_TIER=0`` to always use ``main``.
    """
    tiering = os.getenv("CHATBOT_ANALYZER_TIER", "1").lower() not in (
        "0", "false", "no", "off",
    )
    if tiering and query and select_main_or_mini_tier(query) == "mini":
        return get_llm("mini", temperature=0.1)
    return get_llm("main", temperature=0.1)


def get_planner_llm() -> ChatOpenAI:
    """gpt-5, temp=0.1 — multi-step plan generation."""
    return get_llm("main", temperature=0.1)


def get_code_gen_llm() -> ChatOpenAI:
    """gpt-5, temp=0.1 — pandas code generation (accuracy matters)."""
    return get_llm("main", temperature=0.1)


def get_summarizer_llm() -> ChatOpenAI:
    """gpt-5-mini, temp=0.2, max_tokens=256 — one/two sentence summaries."""
    return get_llm("mini", temperature=0.2, max_tokens=256)


def get_suggestion_llm() -> ChatOpenAI:
    """gpt-5-mini, temp=0.4, max_tokens=128 — three short follow-up questions."""
    return get_llm("suggestion", temperature=0.4, max_tokens=128)


def get_resolver_llm() -> ChatOpenAI:
    """gpt-5-mini, temp=0.0, max_tokens=128 — one-sentence follow-up resolution."""
    return get_llm("resolver", temperature=0.0, max_tokens=128)


def get_small_talk_llm() -> ChatOpenAI:
    """gpt-5-mini, temp=0.7, max_tokens=150 — brief conversational replies."""
    return get_llm("mini", temperature=0.7, max_tokens=150)


def get_responder_llm() -> ChatOpenAI:
    """gpt-5-mini, temp=0.3, max_tokens=512 — fallback response formatting."""
    return get_llm("mini", temperature=0.3, max_tokens=512)
