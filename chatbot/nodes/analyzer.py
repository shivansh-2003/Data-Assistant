"""Analyzer node for tool selection."""

import logging
from typing import Dict
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
import os
from langfuse import observe

from observability.langfuse_client import update_trace_context

from ..prompts import PROMPTS
from ..tools import get_all_tools

logger = logging.getLogger(__name__)


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
        if intent == "small_talk":
            state["tool_calls"] = []
            return state
        
        # Get query and context
        messages = state.get("messages", [])
        last_message = messages[-1]
        query = last_message.content if hasattr(last_message, 'content') else str(last_message)
        
        schema = state.get("schema", {})
        entities = state.get("entities", {})
        
        # Format prompt
        system_prompt = PROMPTS["analyzer"].format(
            schema=schema,
            intent=intent,
            entities=entities
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
        state["tool_calls"] = [{"name": "insight_tool", "args": {"query": query}}]
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
    
    if intent == "small_talk" or not tool_calls:
        return "responder"
    
    tool_names = [tc.get("name", "") for tc in tool_calls]
    
    has_insight = any("insight" in name for name in tool_names)
    has_viz = any(name in ["bar_chart", "line_chart", "scatter_chart", "histogram", "combo_chart", "dashboard"] for name in tool_names)
    
    if has_insight:
        return "insight"
    elif has_viz:
        return "viz"
    else:
        return "responder"

