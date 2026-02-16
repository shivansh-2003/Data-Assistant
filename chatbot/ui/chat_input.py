"""Chat input and graph invocation for InsightBot."""

import streamlit as st
import logging
import traceback
from langchain_core.messages import HumanMessage

from ..utils.session_loader import prepare_state_dataframes
from observability.langfuse_client import get_langfuse_client, update_trace_context

logger = logging.getLogger(__name__)


def handle_chat_input(session_id: str, config: dict, graph):
    """Handle user chat input and invoke graph. Supports auto-submit from suggestion/quick-action clicks."""
    # Auto-submit when user clicked a suggestion or quick-action (pending query from previous rerun)
    user_input = st.session_state.pop("pending_chat_query", None)
    if user_input is None:
        user_input = st.chat_input("Ask anything about your data…")
    if not user_input:
        st.caption("e.g. *What's the average price by brand?* · *Plot sales over time* · *Top 10 by revenue*")
        return
    if user_input:
        # Display user message immediately
        with st.chat_message("user"):
            st.write(user_input)

        with st.spinner("Thinking…"):
            typing_placeholder = st.empty()
            with typing_placeholder.container():
                with st.chat_message("assistant"):
                    st.markdown("*Analyzing your data…*")
            try:
                # Prepare state data
                state_data = prepare_state_dataframes(session_id, st.session_state)

                # Create input for graph (only serializable data)
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
                    "sources": []
                }

                # Invoke graph with Langfuse trace context
                logger.info(f"Invoking graph for query: {user_input[:50]}...")
                langfuse_client = get_langfuse_client()
                with langfuse_client.start_as_current_observation(
                    name="chatbot_query",
                    as_type="agent",
                    input=user_input,
                    metadata={"source": "streamlit_chat"},
                ):
                    update_trace_context(session_id=session_id, metadata={"source": "streamlit_chat"})
                    graph.invoke(inputs, config)

                logger.info("Graph invoked successfully")
                typing_placeholder.empty()

                # Rerun to display updated state
                st.rerun()

            except Exception as e:
                logger.error(f"Error processing query: {e}", exc_info=True)
                with st.chat_message("assistant"):
                    st.error(f"Sorry, I encountered an error: {str(e)}")
                    st.info("Please try rephrasing your question or check if your data is still loaded.")

                    with st.expander("🐛 Debug Information"):
                        st.code(traceback.format_exc())
