"""Analyzer node for tool selection.

This node follows LangChain's tool-calling pattern:
1. Bind tools to LLM using `llm.bind_tools(tools)` 
2. LLM selects which tools to call based on query
3. Extract `tool_calls` from LLM response

However, unlike LangChain's `ToolNode` pattern (which automatically executes tools),
we use specialized execution nodes (`insight_node`, `viz_node`) that:
- Extract tool_calls from state
- Execute tools with domain-specific logic
- Store results in state

This custom pattern allows:
- Specialized execution (data analysis vs visualization)
- Better error handling per tool type
- Separation of concerns (config generation vs execution)

See: https://docs.langchain.com/oss/python/langchain/tools for LangChain's standard pattern.
"""

import logging
from typing import Dict, Any, List, Dict as DictType
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
import os
from langfuse import observe

from observability.langfuse_client import update_trace_context

from ..constants import (
    INTENT_SMALL_TALK,
    TOOL_INSIGHT,
    VIZ_TOOL_NAMES,
    TOOL_BAR_CHART,
    TOOL_SCATTER_CHART,
    TOOL_HEATMAP_CHART,
)
from ..prompts import get_analyzer_prompt
from ..tools import get_all_tools
from ..utils.profile_formatter import format_profile_for_prompt
from ..utils.state_helpers import get_current_query

logger = logging.getLogger(__name__)


def _format_data_profile_summary(data_profile: Dict[str, Any]) -> str:
    """Format data_profile for analyzer prompt using enhanced profiling."""
    return format_profile_for_prompt(data_profile, max_columns=20)


def _is_correlation_query(query: str) -> bool:
    """Heuristic: detect correlation-style queries for viz defaults."""
    q = (query or "").lower()
    return any(
        kw in q
        for kw in [
            "correlation between",
            "correlate",
            "relationship between",
            "how correlated",
            "show correlation",
        ]
    )


def _coerce_correlation_viz_to_heatmap(
    query: str, tool_calls: List[DictType[str, Any]]
) -> List[DictType[str, Any]]:
    """
    Fix cases where LLM picks wrong chart type for correlation-style questions.

    For queries like "Show correlation between Price and Weight", we strongly
    prefer a heatmap (correlation matrix). Sometimes the LLM selects bar_chart
    or scatter_chart despite the prompt guidelines. This function post-processes tool_calls:

    - If query looks like a correlation-style question
    - And a viz tool call is bar_chart or scatter_chart
    - Then rewrite that call to heatmap_chart with the two columns.
    """
    if not tool_calls or not _is_correlation_query(query):
        return tool_calls

    fixed_calls: List[DictType[str, Any]] = []
    for tc in tool_calls:
        name = tc.get("name")
        # Convert bar_chart or scatter_chart to heatmap for correlation queries
        if name in (TOOL_BAR_CHART, TOOL_SCATTER_CHART):
            args = tc.get("args", {}) or {}
            x_col = args.get("x_col")
            y_col = args.get("y_col")
            
            # Build list of columns for heatmap
            columns = []
            if x_col:
                columns.append(x_col)
            if y_col and y_col != x_col:  # Avoid duplicates
                columns.append(y_col)
            
            # Only create heatmap if we have at least 2 columns
            if len(columns) >= 2:
                # Note: viz_node expects "heatmap_columns" (not "columns")
                # This matches the heatmap_chart tool signature and viz_node validation
                heatmap_args = {
                    "heatmap_columns": columns,
                    "table_name": args.get("table_name", "current"),
                }
                fixed_calls.append(
                    {
                        "name": TOOL_HEATMAP_CHART,
                        "args": heatmap_args,
                    }
                )
            else:
                # If we can't extract columns, keep original tool call
                fixed_calls.append(tc)
        else:
            fixed_calls.append(tc)

    return fixed_calls


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
        
        query = get_current_query(state)
        
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
        
        # Get all available tools and bind to LLM (LangChain pattern)
        # Tools are defined with @tool decorator in chatbot/tools/
        tools = get_all_tools()
        llm_with_tools = llm.bind_tools(tools)
        
        # Invoke LLM with tools - LLM decides which tools to call
        # This follows LangChain's tool-calling pattern:
        # https://docs.langchain.com/oss/python/langchain/tools
        response = llm_with_tools.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Query: {query}")
        ])
        
        # Extract tool calls from LLM response
        # Note: Unlike LangChain's ToolNode (which auto-executes tools),
        # we store tool_calls in state and execute them in specialized nodes
        # (insight_node for data analysis, viz_node for charts)
        tool_calls = []
        if hasattr(response, 'tool_calls') and response.tool_calls:
            tool_calls = response.tool_calls

        # Post-process tool selection for correlation-style questions:
        # if the model picked bar_chart or scatter_chart for a clear "correlation between X and Y"
        # request, coerce that viz tool to heatmap_chart (correlation matrix).
        tool_calls = _coerce_correlation_viz_to_heatmap(query, tool_calls)

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

