"""Router node for intent classification."""

import logging
from langchain_core.messages import SystemMessage, HumanMessage
from typing import Dict, List, Optional
from langfuse import observe

from observability.langfuse_client import update_trace_context

try:
    from pydantic import BaseModel, Field
except ImportError:
    # Fallback for older LangChain versions
    from langchain_core.pydantic_v1 import BaseModel, Field  # type: ignore

from ..constants import INTENT_DATA_QUERY, INTENT_SMALL_TALK, INTENT_SUMMARIZE_LAST, TOOL_INSIGHT
from ..llm_registry import get_router_llm, get_resolver_llm
from ..prompts import get_router_prompt, get_context_resolver_prompt

logger = logging.getLogger(__name__)


def _get_all_schema_columns(schema: Dict) -> List[str]:
    """Collect all column names from schema (tables -> columns)."""
    cols = []
    for t in (schema.get("tables") or {}).values():
        if isinstance(t, dict) and "columns" in t:
            cols.extend(t["columns"])
    return list(dict.fromkeys(cols))


def _check_column_ambiguity(mentioned_columns: List[str], schema: Dict) -> Optional[Dict]:
    """
    If any mention matches multiple schema columns, return clarification info.
    Returns dict with mention, options; else None.
    """
    all_cols = _get_all_schema_columns(schema)
    if not all_cols:
        return None
    for mention in (mentioned_columns or []):
        mention_lower = mention.lower().strip()
        if not mention_lower:
            continue
        matches = [c for c in all_cols if mention_lower in c.lower() or c.lower() in mention_lower]
        if len(matches) > 1:
            return {"mention": mention.strip(), "options": matches[:10]}
    return None


def _resolve_follow_up(user_message: str, conversation_context: Dict) -> Optional[str]:
    """Resolve a short follow-up message into a full question using context."""
    try:
        last_query = conversation_context.get("last_query", "")
        last_insight_summary = conversation_context.get("last_insight_summary", "")
        if not last_query and not last_insight_summary:
            return None
        llm = get_resolver_llm()
        prompt = get_context_resolver_prompt()
        context_str = f"Previous question: {last_query}\nPrevious answer summary: {last_insight_summary[:300]}"
        response = llm.invoke([
            SystemMessage(content=prompt),
            HumanMessage(content=f"Context:\n{context_str}\n\nUser follow-up: {user_message}\n\nOutput the single full question:")
        ])
        resolved = (response.content or "").strip()
        return resolved if resolved else None
    except Exception as e:
        logger.warning(f"Context resolution failed: {e}")
        return None


class IntentClassification(BaseModel):
    """Intent classification result."""
    intent: str = Field(description="Query intent: data_query, visualization_request, small_talk, report, or summarize_last")
    sub_intent: str = Field(
        default="general",
        description="Analytical sub-intent: compare, trend, correlate, segment, distribution, filter, report, or general"
    )
    implicit_viz_hint: bool = Field(
        default=False,
        description="True for vague exploratory queries (e.g. How are we doing?, Give me an overview, What stands out?) where a chart is appropriate even if not explicitly requested"
    )
    mentioned_columns: List[str] = Field(default_factory=list, description="Column names mentioned")
    operations: List[str] = Field(default_factory=list, description="Operations mentioned (mean, sum, etc.)")
    confidence: float = Field(default=1.0, description="Classification confidence")
    is_follow_up: bool = Field(default=False, description="True if this is a short follow-up to the previous turn (e.g. What about the maximum?, Just Q1, By region)")


@observe(name="chatbot_router", as_type="chain")
def router_node(state: Dict) -> Dict:
    """
    Classify user query intent and extract entities.
    
    Routes to:
    - Analyzer for data queries and viz requests
    - Responder for small talk
    """
    try:
        update_trace_context(session_id=state.get("session_id"), metadata={"node": "router"})

        # Get last user message
        messages = state.get("messages", [])
        if not messages:
            return state
        
        last_message = messages[-1]
        query = last_message.content if hasattr(last_message, 'content') else str(last_message)
        
        # Prepare context
        schema = state.get("schema", {})
        operation_history = state.get("operation_history", [])
        conversation_context = state.get("conversation_context") or {}
        conv_str = str(conversation_context) if conversation_context else "None"
        
        # Format prompt using modular prompt function
        system_prompt = get_router_prompt(
            schema=schema,
            operation_history=operation_history,
            conversation_context=conv_str
        )
        
        # Initialize LLM with structured output
        llm = get_router_llm()
        structured_llm = llm.with_structured_output(IntentClassification)
        
        # Classify intent
        result = structured_llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=query)
        ])
        
        # Update state
        state["intent"] = result.intent
        state["sub_intent"] = getattr(result, "sub_intent", "general")
        state["implicit_viz_hint"] = getattr(result, "implicit_viz_hint", False)
        state["entities"] = {
            "mentioned_columns": result.mentioned_columns,
            "operations": result.operations
        }
        state["effective_query"] = None

        # Resolve pending clarification if user is answering (e.g. "sales_amount" or "1")
        if state.get("needs_clarification") and state.get("clarification_options") and state.get("clarification_original_query"):
            choice = query.strip()
            opts = state["clarification_options"]
            chosen = None
            if choice in opts:
                chosen = choice
            elif choice.isdigit() and 1 <= int(choice) <= len(opts):
                chosen = opts[int(choice) - 1]
            if chosen:
                mention = state.get("clarification_mention", "")
                state["effective_query"] = state["clarification_original_query"].replace(mention, chosen, 1)
                state["needs_clarification"] = False
                state["clarification_options"] = None
                state["clarification_mention"] = None
                state["clarification_original_query"] = None
                state["clarification_resolved"] = {mention: chosen}
                logger.info(f"Clarification resolved: {mention} -> {chosen}")

        # Resolve follow-up into effective_query when applicable
        if not state.get("needs_clarification") and result.is_follow_up and conversation_context and result.intent != INTENT_SMALL_TALK:
            effective = _resolve_follow_up(query, conversation_context)
            if effective:
                state["effective_query"] = effective
                logger.info(f"Resolved follow-up to: {effective[:60]}...")

        # When user asks to summarize previous result, send a synthetic tool call so insight node runs
        if result.intent == INTENT_SUMMARIZE_LAST:
            state["tool_calls"] = [{"name": TOOL_INSIGHT, "args": {"query": "Summarize the previous result"}}]

        # Check for column ambiguity (multiple columns match one mention)
        if not state.get("needs_clarification") and result.intent not in (INTENT_SMALL_TALK, INTENT_SUMMARIZE_LAST):
            amb = _check_column_ambiguity(result.mentioned_columns or [], schema)
            if amb:
                state["needs_clarification"] = True
                state["clarification_options"] = amb["options"]
                state["clarification_type"] = "column"
                state["clarification_mention"] = amb["mention"]
                state["clarification_original_query"] = query
                logger.info(f"Column ambiguity: '{amb['mention']}' matches {amb['options']}")
        
        logger.info(f"Classified intent: {result.intent} (confidence: {result.confidence})")
        
        return state
        
    except Exception as e:
        logger.error(f"Error in router node: {e}", exc_info=True)
        state["error"] = f"Intent classification failed: {str(e)}"
        state["intent"] = INTENT_DATA_QUERY
        state["sub_intent"] = "general"
        state["implicit_viz_hint"] = False
        return state

