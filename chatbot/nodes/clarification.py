"""Clarification node: ask user to disambiguate when multiple columns match."""

import logging
from typing import Dict
from langchain_core.messages import AIMessage
from langfuse import observe

from observability.langfuse_client import update_trace_context

logger = logging.getLogger(__name__)


@observe(name="chatbot_clarification", as_type="chain")
def clarification_node(state: Dict) -> Dict:
    """
    When needs_clarification is True, append an AIMessage asking the user to pick one option.
    No tools run this turn; next user message will be treated as the choice.
    """
    try:
        update_trace_context(session_id=state.get("session_id"), metadata={"node": "clarification"})
        options = state.get("clarification_options", [])
        mention = state.get("clarification_mention", "that column")
        if not options:
            state["needs_clarification"] = False
            return state
        lines = [f"I found {len(options)} columns matching '{mention}'. Which do you mean?"]
        for i, opt in enumerate(options[:10], 1):
            lines.append(f"  {i}. {opt}")
        lines.append("\nReply with the column name or number (e.g. 1 or 2).")
        msg = "\n".join(lines)
        state["messages"].append(AIMessage(content=msg))
        logger.info(f"Asked clarification for '{mention}' with {len(options)} options")
        return state
    except Exception as e:
        logger.error(f"Clarification node error: {e}", exc_info=True)
        state["needs_clarification"] = False
        return state
