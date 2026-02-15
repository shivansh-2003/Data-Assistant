"""Suggestion node: generate 3 contextual follow-up questions after each response."""

import logging
from typing import Dict, List
import os
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langfuse import observe

from observability.langfuse_client import update_trace_context

from ..prompts import PROMPTS

logger = logging.getLogger(__name__)


@observe(name="chatbot_suggestions", as_type="chain")
def suggestion_node(state: Dict) -> Dict:
    """
    Generate 3 short follow-up question suggestions from last query and insight.
    Writes to state["suggestions"] for the UI to render as chips.
    """
    try:
        update_trace_context(session_id=state.get("session_id"), metadata={"node": "suggestion"})
        messages = state.get("messages", [])
        if len(messages) < 2:
            state["suggestions"] = []
            return state

        # Last message is the AI response we just added; one before is the user query
        last_msg = messages[-1]
        prev_msg = messages[-2]
        if isinstance(last_msg, AIMessage) and isinstance(prev_msg, HumanMessage):
            last_user = prev_msg.content if hasattr(prev_msg, "content") else str(prev_msg)
            last_ai = last_msg.content if hasattr(last_msg, "content") else str(last_msg)
        else:
            state["suggestions"] = []
            return state

        last_insight = state.get("last_insight") or last_ai[:400]
        schema = state.get("schema", {})
        table_names = state.get("table_names", [])

        prompt = PROMPTS["suggestions"]
        context = f"""User's last question: {last_user}

Answer summary: {last_insight}

Schema (tables and columns): {schema}
Table names: {table_names}

Output exactly 3 follow-up questions, one per line:"""

        llm = ChatOpenAI(
            model=os.getenv("OPENAI_MODEL", "gpt-4o"),
            temperature=0.4,
            api_key=os.getenv("OPENAI_API_KEY")
        )
        response = llm.invoke([
            SystemMessage(content=prompt),
            HumanMessage(content=context)
        ])
        text = (response.content or "").strip()
        lines = [ln.strip() for ln in text.split("\n") if ln.strip()][:3]
        # Remove leading numbers/bullets if present
        suggestions = []
        for ln in lines:
            s = ln.lstrip("0123456789.-)> ")
            if s:
                suggestions.append(s)
        state["suggestions"] = suggestions[:3]
        logger.info(f"Generated {len(state['suggestions'])} suggestions")
        return state
    except Exception as e:
        logger.warning(f"Suggestion generation failed: {e}")
        state["suggestions"] = []
        return state
