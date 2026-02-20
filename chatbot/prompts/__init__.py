"""Prompts module for InsightBot - Modular, versioned prompt system."""

# New modular prompt functions
from .router_prompt import get_router_prompt
from .context_resolver_prompt import get_context_resolver_prompt
from .analyzer_prompt import get_analyzer_prompt
from .planner_prompt import get_planner_prompt
from .code_generator_prompt import get_code_generator_prompt
from .summarizer_prompt import get_summarizer_prompt
from .suggestion_prompt import get_suggestion_prompt
from .small_talk_prompt import get_small_talk_prompt
from .responder_prompt import get_responder_prompt

# Base utilities
from .base import PromptTemplate, truncate_schema

__all__ = [
    # New modular functions
    "get_router_prompt",
    "get_context_resolver_prompt",
    "get_analyzer_prompt",
    "get_planner_prompt",
    "get_code_generator_prompt",
    "get_summarizer_prompt",
    "get_suggestion_prompt",
    "get_small_talk_prompt",
    "get_responder_prompt",
    # Base utilities
    "PromptTemplate",
    "truncate_schema",
]
