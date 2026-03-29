"""Suggestion node: generate 3 contextual follow-up questions after each response."""

import logging
from typing import Dict, List
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langfuse import observe

from observability.langfuse_client import update_trace_context

from ..llm_registry import get_suggestion_llm
from ..prompts import get_suggestion_prompt

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Intent-aware fallback suggestions (0ms, no LLM call on failure)
# ---------------------------------------------------------------------------
_INTENT_SUGGESTIONS: Dict[str, List[str]] = {
    "compare": [
        "Which group has the highest average?",
        "Show the same comparison as a bar chart.",
        "Filter to only the top 3 groups.",
    ],
    "trend": [
        "What is the month-over-month growth rate?",
        "Show the trend for a different metric.",
        "Are there any anomalies in this trend?",
    ],
    "correlate": [
        "Show the full correlation matrix.",
        "Which column has the strongest correlation overall?",
        "Plot this as a scatter chart.",
    ],
    "segment": [
        "Which segment performs best on average?",
        "How does the distribution look within each segment?",
        "Compare the top and bottom segments side by side.",
    ],
    "distribution": [
        "What are the outliers in this distribution?",
        "How does this compare to last period?",
        "Split the distribution by a categorical column.",
    ],
    "filter": [
        "What happens if you include the excluded rows?",
        "Apply the same filter to a different metric.",
        "Show top 10 results after this filter.",
    ],
    "report": [
        "Drill down into the highest-value category.",
        "Add a time breakdown to this report.",
        "Export this as a chart.",
    ],
}
_GENERIC_SUGGESTIONS: List[str] = [
    "Show me a summary of the entire dataset.",
    "Which column has the most missing values?",
    "Plot the top 10 rows by a numeric column.",
]


def _fast_suggestions(state: Dict) -> List[str]:
    """Return intent-keyed fallbacks instantly (no LLM needed)."""
    sub_intent = (state.get("sub_intent") or "general").lower().strip()
    return _INTENT_SUGGESTIONS.get(sub_intent, _GENERIC_SUGGESTIONS)


@observe(name="chatbot_suggestions", as_type="chain")
def suggestion_node(state: Dict) -> Dict:
    """
    Generate 3 short follow-up question suggestions from last query and insight.
    Uses gpt-4o-mini (max_tokens=128) for speed; falls back to intent-aware
    pre-defined suggestions instantly on any LLM failure.
    Writes to state["suggestions"] for the UI to render as chips.
    """
    try:
        update_trace_context(session_id=state.get("session_id"), metadata={"node": "suggestion"})
        messages = state.get("messages", [])
        if len(messages) < 2:
            state["suggestions"] = _fast_suggestions(state)
            return state

        last_msg = messages[-1]
        prev_msg = messages[-2]
        if isinstance(last_msg, AIMessage) and isinstance(prev_msg, HumanMessage):
            last_user = last_msg.content if hasattr(prev_msg, "content") else str(prev_msg)
            last_ai = last_msg.content if hasattr(last_msg, "content") else str(last_msg)
        else:
            state["suggestions"] = _fast_suggestions(state)
            return state

        last_insight = state.get("last_insight") or last_ai[:400]
        schema = state.get("schema", {})

        system_prompt = get_suggestion_prompt(
            last_query=last_user,
            insight_summary=last_insight,
            schema=schema,
        )

        llm = get_suggestion_llm()
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content="Output exactly 3 follow-up questions, one per line:"),
        ])
        text = (response.content or "").strip()
        lines = [ln.strip() for ln in text.split("\n") if ln.strip()][:3]
        suggestions = []
        for ln in lines:
            s = ln.lstrip("0123456789.-)> ")
            if s:
                suggestions.append(s)
        state["suggestions"] = suggestions[:3] if suggestions else _fast_suggestions(state)
        logger.info(f"Generated {len(state['suggestions'])} suggestions")
        return state
    except Exception as e:
        logger.warning(f"Suggestion generation failed: {e}")
        state["suggestions"] = _fast_suggestions(state)
        return state
