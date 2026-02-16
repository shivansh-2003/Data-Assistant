"""Analyzer node for tool selection."""

import logging
from typing import Dict, Any
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
import os
from langfuse import observe

from observability.langfuse_client import update_trace_context

from ..constants import INTENT_SMALL_TALK, TOOL_INSIGHT, VIZ_TOOL_NAMES
from ..prompts import get_analyzer_prompt
from ..tools import get_all_tools
from ..utils.profile_formatter import format_profile_for_prompt

logger = logging.getLogger(__name__)


def _format_data_profile_summary(data_profile: Dict[str, Any]) -> str:
    """Format data_profile for analyzer prompt using enhanced profiling."""
    return format_profile_for_prompt(data_profile, max_columns=20)


@observe(name="chatbot_analyzer", as_type="chain")
def analyzer_node(state: Dict) -> Dict:
    """
    Select appropriate tools based on query intent and entities.
    
    Uses LLM function calling to decide which tools to invoke.
    """
    try:
        update_trace_context(session_id=state.get("session_id"), metadata={"node": "analyzer"})
        intent = state.get("intent", "data_query")
        
        # Small talk goes directly to responder
        if intent == INTENT_SMALL_TALK:
            state["tool_calls"] = []
            return state
        
        # Get query and context (use effective_query when follow-up was resolved)
        messages = state.get("messages", [])
        last_message = messages[-1]
        query = state.get("effective_query") or (last_message.content if hasattr(last_message, 'content') else str(last_message))
        
        schema = state.get("schema", {})
        entities = state.get("entities", {})
        sub_intent = state.get("sub_intent", "general")
        implicit_viz_hint = state.get("implicit_viz_hint", False)
        data_profile = state.get("data_profile") or {}
        data_profile_summary = _format_data_profile_summary(data_profile)
        
        # Format prompt using modular prompt function
        system_prompt = get_analyzer_prompt(
            schema=schema,
            intent=intent,
            sub_intent=sub_intent,
            entities=entities,
            implicit_viz_hint=implicit_viz_hint,
            data_profile_summary=data_profile_summary,
        )
        
        # Initialize LLM with tools
        llm = ChatOpenAI(
            model=os.getenv("OPENAI_MODEL", "gpt-4o"),
            temperature=0.1,
            api_key=os.getenv("OPENAI_API_KEY")
        )
        
        # Get all available tools
        tools = get_all_tools()
        llm_with_tools = llm.bind_tools(tools)
        
        # Get tool recommendations
        response = llm_with_tools.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Query: {query}")
        ])
        
        # Extract tool calls
        tool_calls = []
        if hasattr(response, 'tool_calls') and response.tool_calls:
            tool_calls = response.tool_calls
        
        state["tool_calls"] = tool_calls
        
        logger.info(f"Selected {len(tool_calls)} tools: {[tc.get('name', 'unknown') for tc in tool_calls]}")
        
        return state
        
    except Exception as e:
        logger.error(f"Error in analyzer node: {e}", exc_info=True)
        # Default to insight tool for data queries
        state["tool_calls"] = [{"name": TOOL_INSIGHT, "args": {"query": query}}]
        return state


def route_after_analyzer(state: Dict) -> str:
    """
    Conditional edge function to route after analyzer.
    
    Returns:
    - "insight" if insight tool selected
    - "viz" if only viz tools selected
    - "responder" if no tools or small talk
    """
    intent = state.get("intent")
    tool_calls = state.get("tool_calls", [])
    
    if intent == INTENT_SMALL_TALK or not tool_calls:
        return "responder"
    
    tool_names = [tc.get("name", "") for tc in tool_calls]
    
    has_insight = any(name == TOOL_INSIGHT for name in tool_names)
    has_viz = any(name in VIZ_TOOL_NAMES for name in tool_names)
    
    if has_insight:
        return "insight"
    elif has_viz:
        return "viz"
    else:
        return "responder"

