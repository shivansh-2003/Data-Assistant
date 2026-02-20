"""Planner node for multi-step query breakdown."""

import logging
import json
from typing import Dict, List, Any, Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
import os
from langfuse import observe

from observability.langfuse_client import update_trace_context

from ..constants import INTENT_SMALL_TALK, INTENT_DATA_QUERY, TOOL_INSIGHT
from ..prompts import get_planner_prompt
from ..utils.state_helpers import get_current_query

logger = logging.getLogger(__name__)


def _detect_complexity(query: str, sub_intent: str, entities: Dict[str, Any]) -> bool:
    """
    Detect if a query requires multi-step planning.
    
    Heuristics:
    - Multiple operations mentioned (aggregate + filter + sort + top N)
    - YoY, MoM, growth calculations
    - Multiple aggregations
    - "then", "and", "after" keywords suggesting sequence
    
    Args:
        query: User query
        sub_intent: Analytical sub-intent
        entities: Extracted entities
        
    Returns:
        True if query likely needs planning
    """
    query_lower = query.lower()
    
    # Keywords suggesting multi-step
    multi_step_keywords = [
        "then", "after", "and show", "and filter", "and sort",
        "yoy", "year over year", "mom", "month over month",
        "growth", "declining", "increasing", "trend",
        "top", "bottom", "first", "last", "n largest", "n smallest"
    ]
    
    if any(kw in query_lower for kw in multi_step_keywords):
        return True
    
    # Multiple operations in entities
    operations = entities.get("operations", [])
    if len(operations) >= 2:
        return True
    
    # Complex sub-intents
    if sub_intent in ("compare", "trend", "correlate"):
        # Check if query has multiple parts
        if " and " in query_lower or " then " in query_lower:
            return True
    
    return False


def _parse_plan_response(response_text: str) -> Optional[List[Dict[str, Any]]]:
    """
    Parse LLM response into plan structure.
    
    Expected format: JSON array of step objects.
    Falls back to single-step plan if parsing fails.
    
    Args:
        response_text: LLM response text
        
    Returns:
        List of plan steps or None if parsing fails
    """
    try:
        # Try to extract JSON from response
        text = response_text.strip()
        
        # Look for JSON array
        start_idx = text.find("[")
        end_idx = text.rfind("]") + 1
        if start_idx >= 0 and end_idx > start_idx:
            json_str = text[start_idx:end_idx]
            plan = json.loads(json_str)
            if isinstance(plan, list) and len(plan) > 0:
                # Validate plan structure
                validated = []
                for step in plan:
                    if isinstance(step, dict) and "step" in step and "code" in step:
                        validated.append({
                            "step": step.get("step"),
                            "description": step.get("description", ""),
                            "code": step.get("code", ""),
                            "output_var": step.get("output_var", f"step{step.get('step')}_result")
                        })
                return validated if validated else None
        
        # Fallback: treat as single step
        return [{
            "step": 1,
            "description": "Execute query",
            "code": response_text.strip(),
            "output_var": "result"
        }]
    except Exception as e:
        logger.warning(f"Failed to parse plan response: {e}")
        return None


@observe(name="chatbot_planner", as_type="chain")
def planner_node(state: Dict) -> Dict:
    """
    Break down complex queries into multi-step plans.
    
    For simple queries, creates a single-step plan.
    For complex queries, creates sequential steps.
    """
    try:
        update_trace_context(session_id=state.get("session_id"), metadata={"node": "planner"})
        
        # Skip planning for small talk or if no insight tool
        intent = state.get("intent", INTENT_DATA_QUERY)
        if intent == INTENT_SMALL_TALK:
            state["plan"] = None
            state["needs_planning"] = False
            return state
        
        tool_calls = state.get("tool_calls", [])
        insight_calls = [tc for tc in tool_calls if tc.get("name") == TOOL_INSIGHT]
        if not insight_calls:
            state["plan"] = None
            state["needs_planning"] = False
            return state
        
        query = get_current_query(state)
        insight_call = insight_calls[0]
        insight_query = insight_call.get("args", {}).get("query", query)
        
        schema = state.get("schema", {})
        sub_intent = state.get("sub_intent", "general")
        entities = state.get("entities", {})
        
        # Detect if planning is needed
        needs_planning = _detect_complexity(insight_query, sub_intent, entities)
        state["needs_planning"] = needs_planning
        
        # Always create a plan (even if single-step) for consistency
        logger.info(f"Creating plan for query (complexity: {needs_planning}): {insight_query[:60]}...")
        
        # Format prompt
        system_prompt = get_planner_prompt(
            schema=schema,
            intent=intent,
            sub_intent=sub_intent,
            query=insight_query
        )
        
        # Initialize LLM
        llm = ChatOpenAI(
            model=os.getenv("OPENAI_MODEL", "gpt-4o"),
            temperature=0.1,
            api_key=os.getenv("OPENAI_API_KEY")
        )
        
        # Get plan
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Create a step-by-step plan for: {insight_query}")
        ])
        
        plan_text = response.content or ""
        plan = _parse_plan_response(plan_text)
        
        if plan:
            state["plan"] = plan
            logger.info(f"Created plan with {len(plan)} step(s)")
        else:
            # Fallback: single-step plan
            state["plan"] = [{
                "step": 1,
                "description": "Execute query",
                "code": "",
                "output_var": "result"
            }]
            logger.warning("Plan parsing failed, using fallback single-step plan")
        
        return state
        
    except Exception as e:
        logger.error(f"Error in planner node: {e}", exc_info=True)
        # Fallback: single-step plan
        state["plan"] = [{
            "step": 1,
            "description": "Execute query",
            "code": "",
            "output_var": "result"
        }]
        state["needs_planning"] = False
        return state
