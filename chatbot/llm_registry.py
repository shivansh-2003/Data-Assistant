"""LLM Registry — singleton pattern for ChatOpenAI instances.

One instance per (model_key, temperature, max_tokens) combination is created and
reused for the lifetime of the process. All nodes import getters from here
instead of constructing ChatOpenAI() inline, eliminating the per-call overhead
of API-key validation, HTTP-client initialisation, and metadata fetch (~200ms/node).

Model assignment:
  main  → gpt-4o      (Analyzer, Planner, Code Gen — need schema reasoning)
  mini  → gpt-4o-mini (Router, Resolver, Summarizer, Suggestions, Small Talk)

Override via environment variables without code changes:
  MAIN_MODEL, MINI_MODEL, ROUTER_MODEL, SUGGESTION_MODEL, CONTEXT_RESOLVER_MODEL
"""

import os
from typing import Dict, Optional, Tuple

from langchain_openai import ChatOpenAI

_registry: Dict[Tuple, ChatOpenAI] = {}

# Resolve model names once at import time (env vars must be set before first import)
_MODELS: Dict[str, str] = {
    "main": os.getenv("MAIN_MODEL", os.getenv("OPENAI_MODEL", "gpt-4o")),
    "mini": os.getenv("MINI_MODEL", "gpt-4o-mini"),
    "router": os.getenv("ROUTER_MODEL", os.getenv("MINI_MODEL", "gpt-4o-mini")),
    "suggestion": os.getenv("SUGGESTION_MODEL", os.getenv("MINI_MODEL", "gpt-4o-mini")),
    "resolver": os.getenv("CONTEXT_RESOLVER_MODEL", os.getenv("MINI_MODEL", "gpt-4o-mini")),
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
    """gpt-4o-mini, temp=0.0, max_tokens=256 — binary intent classification."""
    return get_llm("router", temperature=0.0, max_tokens=256)


def get_analyzer_llm() -> ChatOpenAI:
    """gpt-4o, temp=0.1 — tool selection with schema reasoning."""
    return get_llm("main", temperature=0.1)


def get_planner_llm() -> ChatOpenAI:
    """gpt-4o, temp=0.1 — multi-step plan generation."""
    return get_llm("main", temperature=0.1)


def get_code_gen_llm() -> ChatOpenAI:
    """gpt-4o, temp=0.1 — pandas code generation (accuracy matters)."""
    return get_llm("main", temperature=0.1)


def get_summarizer_llm() -> ChatOpenAI:
    """gpt-4o-mini, temp=0.2, max_tokens=256 — one/two sentence summaries."""
    return get_llm("mini", temperature=0.2, max_tokens=256)


def get_suggestion_llm() -> ChatOpenAI:
    """gpt-4o-mini, temp=0.4, max_tokens=128 — three short follow-up questions."""
    return get_llm("suggestion", temperature=0.4, max_tokens=128)


def get_resolver_llm() -> ChatOpenAI:
    """gpt-4o-mini, temp=0.0, max_tokens=128 — one-sentence follow-up resolution."""
    return get_llm("resolver", temperature=0.0, max_tokens=128)


def get_small_talk_llm() -> ChatOpenAI:
    """gpt-4o-mini, temp=0.7, max_tokens=150 — brief conversational replies."""
    return get_llm("mini", temperature=0.7, max_tokens=150)


def get_responder_llm() -> ChatOpenAI:
    """gpt-4o-mini, temp=0.3, max_tokens=512 — fallback response formatting."""
    return get_llm("mini", temperature=0.3, max_tokens=512)
