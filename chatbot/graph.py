"""LangGraph state graph definition for InsightBot."""

import logging
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from .state import State
from .nodes import (
    router_node,
    analyzer_node,
    insight_node,
    viz_node,
    responder_node,
    suggestion_node,
    clarification_node
)
from .nodes.analyzer import route_after_analyzer

logger = logging.getLogger(__name__)

# Create the graph
workflow = StateGraph(State)

# Add nodes
workflow.add_node("router", router_node)
workflow.add_node("analyzer", analyzer_node)
workflow.add_node("insight", insight_node)
workflow.add_node("viz", viz_node)
workflow.add_node("responder", responder_node)
workflow.add_node("suggestion", suggestion_node)
workflow.add_node("clarification", clarification_node)

# Set entry point
workflow.set_entry_point("router")

# Add edges from router
def route_from_router(state: dict) -> str:
    """Route from router based on intent and clarification."""
    if state.get("needs_clarification"):
        return "clarification"
    intent = state.get("intent", "data_query")
    if intent == "small_talk":
        return "responder"
    if intent == "summarize_last":
        return "insight"  # insight node handles summarize_last (re-summarize previous result)
    return "analyzer"

workflow.add_conditional_edges(
    "router",
    route_from_router,
    {
        "analyzer": "analyzer",
        "responder": "responder",
        "clarification": "clarification",
        "insight": "insight"
    }
)

# Clarification node goes to END (no tools this turn)
workflow.add_edge("clarification", END)

# Add conditional edges from analyzer
workflow.add_conditional_edges(
    "analyzer",
    route_after_analyzer,
    {
        "insight": "insight",
        "viz": "viz",
        "responder": "responder"
    }
)

# Add edges from insight
def route_from_insight(state: dict) -> str:
    """Route from insight to viz if viz tools present, else responder."""
    tool_calls = state.get("tool_calls", [])
    viz_tools = ["bar_chart", "line_chart", "scatter_chart", "histogram", "combo_chart", "dashboard"]
    has_viz = any(tc.get("name") in viz_tools for tc in tool_calls)
    return "viz" if has_viz else "responder"

workflow.add_conditional_edges(
    "insight",
    route_from_insight,
    {
        "viz": "viz",
        "responder": "responder"
    }
)

# Add edge from viz to responder
workflow.add_edge("viz", "responder")

# Add edge from responder to suggestion (generate follow-up chips), then END
workflow.add_edge("responder", "suggestion")
workflow.add_edge("suggestion", END)

# Compile graph with checkpointer
checkpointer = MemorySaver()
graph = workflow.compile(checkpointer=checkpointer)

logger.info("InsightBot graph compiled successfully")

