"""Chat input and graph invocation for InsightBot.

Uses graph.stream(stream_mode='values') so the AI response is shown as soon
as the responder node completes, while the suggestion node continues running
in the background. Perceived latency drops from 15s (all-or-nothing) to
~1–2s first token visible.

Progressive status labels shown while nodes execute:
  router done         → "Understanding your question…"
  analyzer done       → "Selecting analysis tools…"
  planner done        → "Planning multi-step analysis…"
  insight done        → "Composing response…"
  responder done      → response rendered immediately
  suggestion done     → rerun to load chips
"""

import streamlit as st
import logging
import traceback
from langchain_core.messages import HumanMessage, AIMessage

from ..utils.session_loader import prepare_state_dataframes
from observability.langfuse_client import get_langfuse_client, update_trace_context

logger = logging.getLogger(__name__)


def _status_label(snapshot: dict) -> str:
    """Derive a human-readable status from the current state snapshot."""
    if snapshot.get("last_insight"):
        return "Composing response…"
    if snapshot.get("plan"):
        return "Planning multi-step analysis…"
    if snapshot.get("tool_calls") is not None:
        return "Running analysis…"
    if snapshot.get("intent"):
        return "Selecting analysis tools…"
    return "Understanding your question…"


def handle_chat_input(session_id: str, config: dict, graph):
    """Handle user chat input and stream the graph response.

    Supports auto-submit when user clicked a suggestion or quick-action
    (pending_chat_query in session_state from a previous rerun).
    """
    user_input = st.session_state.pop("pending_chat_query", None)
    if user_input is None:
        user_input = st.chat_input("Ask anything about your data…")
    if not user_input:
        st.caption("e.g. *What's the average price by brand?* · *Plot sales over time* · *Top 10 by revenue*")
        return

    # Display user message immediately
    with st.chat_message("user"):
        st.write(user_input)

    # Placeholders we will update as nodes stream in
    status_placeholder = st.empty()
    response_placeholder = st.empty()

    try:
        state_data = prepare_state_dataframes(session_id, st.session_state)

        inputs = {
            "session_id": session_id,
            "messages": [HumanMessage(content=user_input)],
            "schema": state_data["schema"],
            "operation_history": state_data["operation_history"],
            "table_names": list(state_data["df_dict"].keys()),
            "data_profile": state_data.get("data_profile") or {"tables": {}},
            "user_tone": st.session_state.get("chatbot_user_tone", "explorer"),
            "intent": None,
            "entities": None,
            "tool_calls": None,
            "last_insight": None,
            "viz_config": None,
            "viz_type": None,
            "error": None,
            "sources": [],
        }

        logger.info(f"Streaming graph for query: {user_input[:50]}…")
        langfuse_client = get_langfuse_client()

        response_shown = False

        with langfuse_client.start_as_current_observation(
            name="chatbot_query",
            as_type="agent",
            input=user_input,
            metadata={"source": "streamlit_chat"},
        ):
            update_trace_context(session_id=session_id, metadata={"source": "streamlit_chat"})

            for snapshot in graph.stream(inputs, config, stream_mode="values"):
                messages = snapshot.get("messages") or []
                last_msg = messages[-1] if messages else None

                # As soon as the responder has appended its AIMessage — show it now.
                # The suggestion node may still be running in the background.
                if not response_shown and isinstance(last_msg, AIMessage):
                    status_placeholder.empty()
                    with response_placeholder.container():
                        with st.chat_message("assistant"):
                            st.markdown(last_msg.content)
                    response_shown = True
                    # Keep iterating so the suggestion node can finish
                    continue

                # Show progressive status while we're still waiting for the response
                if not response_shown:
                    label = _status_label(snapshot)
                    with status_placeholder.container():
                        with st.chat_message("assistant"):
                            st.caption(f"_{label}_")

        logger.info("Graph stream completed")
        status_placeholder.empty()

        # Rerun to re-render the full message history (with charts, tables, code,
        # suggestion chips) through the normal message_history renderer.
        st.rerun()

    except Exception as e:
        logger.error(f"Error processing query: {e}", exc_info=True)
        status_placeholder.empty()
        response_placeholder.empty()
        with st.chat_message("assistant"):
            st.error(f"Sorry, I encountered an error: {str(e)}")
            st.info("Please try rephrasing your question or check if your data is still loaded.")
            with st.expander("🐛 Debug Information"):
                st.code(traceback.format_exc())
