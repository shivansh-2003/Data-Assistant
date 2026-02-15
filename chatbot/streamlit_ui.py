"""Streamlit UI for InsightBot."""

import streamlit as st
import logging
from datetime import datetime
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
import traceback

from .graph import graph
from .utils.session_loader import prepare_state_dataframes
from observability.langfuse_client import get_langfuse_client, update_trace_context

logger = logging.getLogger(__name__)

# Inject custom CSS for chatbot tab (scoped to avoid affecting other tabs)
CHATBOT_CSS = """
<style>
  [data-testid="stChatBot"] .stChatMessage { margin-bottom: 0.5rem; }
  div[data-testid="stVerticalBlock"] > div:has(> div[data-testid="stChatMessage"]) { margin-bottom: 0.25rem; }
  .insightbot-hero { padding: 0.5rem 0 1rem 0; border-bottom: 1px solid var(--border-color, #e5e7eb); margin-bottom: 1rem; }
  .insightbot-session-pill { display: inline-flex; align-items: center; gap: 0.5rem; padding: 0.35rem 0.75rem; 
    background: var(--secondary-background-color, #f3f4f6); border-radius: 9999px; font-size: 0.8rem; color: var(--text-color, #374151); margin-top: 0.25rem; }
  .insightbot-suggestions { padding: 0.75rem; background: var(--secondary-background-color, #f8fafc); border-radius: 12px; margin: 0.75rem 0; }
  .insightbot-quick-actions { display: flex; flex-wrap: wrap; gap: 0.5rem; margin: 0.5rem 0; }
  .insightbot-code-expander { border-radius: 8px; overflow: hidden; border: 1px solid var(--border-color, #e5e7eb); }
  .insightbot-timestamp { font-size: 0.7rem; opacity: 0.7; }
</style>
"""


def render_chatbot_tab():
    """Main function to render the InsightBot chatbot tab."""
    st.markdown(CHATBOT_CSS, unsafe_allow_html=True)

    # Hero + session pill
    col_title, col_pill = st.columns([1, 0.35])
    with col_title:
        st.markdown("### 💬 InsightBot")
        st.caption("Ask questions in plain language. Get insights, tables, and charts from your data.")
    session_id = st.session_state.get("current_session_id")

    if not session_id:
        show_upload_warning()
        return

    with col_pill:
        display_session_pill(session_id)

    st.divider()

    config = {"configurable": {"thread_id": session_id}}

    try:
        current_state = graph.get_state(config)

        # Sidebar: options and quick actions
        with st.sidebar:
            st.markdown("**Chat options**")
            show_data = st.toggle(
                "Show data tables",
                value=True,
                help="Include table previews in responses when no chart is shown.",
            )
            st.caption("Turn off for narrative-only answers.")
            st.markdown("---")
            st.markdown("**Quick questions**")
            if st.button("📊 Summary stats", key="qa_summary", use_container_width=True):
                st.session_state["pending_chat_query"] = "Show summary statistics for the main table"
                st.rerun()
            if st.button("📈 Trend", key="qa_trend", use_container_width=True):
                st.session_state["pending_chat_query"] = "Plot the trend over time for the main metric"
                st.rerun()
            if st.button("🔍 Top 10", key="qa_top10", use_container_width=True):
                st.session_state["pending_chat_query"] = "Show the top 10 rows by the primary numeric column"
                st.rerun()
            if st.button("🎯 Correlation", key="qa_corr", use_container_width=True):
                st.session_state["pending_chat_query"] = "Show correlation between the two most important numeric columns"
                st.rerun()
            if current_state and current_state.values.get("messages"):
                st.markdown("---")
                if st.button("🗑️ Clear chat", key="clear_chat", use_container_width=True):
                    logger.info("Clearing chat history")
                    st.rerun()

        if current_state and current_state.values:
            messages = current_state.values.get("messages", [])
            response_snapshots = current_state.values.get("response_snapshots") or []
            suggestions = current_state.values.get("suggestions") or []

            # Backward compatibility: single viz/insight/code when no snapshots
            viz_config = current_state.values.get("viz_config")
            insight_data = current_state.values.get("insight_data")
            generated_code = current_state.values.get("generated_code")
            viz_figure = None
            viz_error = current_state.values.get("viz_error")
            if not response_snapshots and viz_config and not viz_error:
                viz_figure = generate_chart_from_config_ui(viz_config, session_id)

            display_message_history(
                messages,
                viz_figure=viz_figure,
                insight_data=insight_data,
                show_data=show_data,
                generated_code=generated_code,
                response_snapshots=response_snapshots,
                session_id=session_id,
            )

            if suggestions:
                with st.container():
                    st.markdown("**💡 Suggested follow-ups**")
                    sug_cols = st.columns(min(3, len(suggestions)))
                    for i, sug in enumerate(suggestions[:3]):
                        with sug_cols[i]:
                            label = (sug[:48] + "…") if len(sug) > 48 else sug
                            if st.button(label, key=f"sug_{i}", use_container_width=True):
                                st.session_state["pending_chat_query"] = sug
                                st.rerun()

        handle_chat_input(session_id, config)

    except Exception as e:
        logger.error(f"Error in chatbot tab: {e}", exc_info=True)
        st.error(f"An error occurred: {str(e)}")
        st.info("Try refreshing the page or uploading new data.")


def display_session_pill(session_id: str):
    """Compact session indicator (pill) with optional expandable details."""
    try:
        from .utils.session_loader import SessionLoader
        loader = SessionLoader()
        summary = loader.get_session_summary(session_id)
        tables = summary.get("table_count", 0)
        file_name = summary.get("file_name") or "Uploaded file"
        if len(file_name) > 18:
            file_name = file_name[:15] + "…"
        st.caption(f"📁 {file_name} · {tables} table{'s' if tables != 1 else ''}")
    except Exception:
        st.caption(f"Session: {session_id[:12]}…")


def show_upload_warning():
    """Display when no session is active."""
    st.info("👆 **No data loaded.** Upload a file in the **Upload** tab to start asking questions.")
    with st.expander("Example questions (after you upload data)"):
        st.markdown("""
        - *What's the average X by Y?*
        - *Show me the top 10 by Z*
        - *Plot X over time as a line chart*
        - *Compare X across categories*
        - *Summarize the main table*
        """)


def display_session_info(session_id: str):
    """Display session information in an expander (legacy / optional)."""
    try:
        from .utils.session_loader import SessionLoader
        loader = SessionLoader()
        summary = loader.get_session_summary(session_id)
        with st.expander("📋 Session details", expanded=False):
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**Session ID:** `{session_id[:24]}…`")
                st.write(f"**Tables:** {summary.get('table_count', 0)}")
            with col2:
                if summary.get("file_name"):
                    st.write(f"**File:** {summary.get('file_name')}")
                if summary.get("file_type"):
                    st.write(f"**Type:** {summary.get('file_type')}")
    except Exception as e:
        logger.warning(f"Could not load session summary: {e}")


def display_message_history(
    messages: list,
    viz_figure=None,
    insight_data=None,
    show_data: bool = True,
    generated_code: str = None,
    response_snapshots: list = None,
    session_id: str = None,
):
    """Display chat message history. When response_snapshots is set, each AI message shows its own table/chart/code."""
    import pandas as pd

    snapshots = response_snapshots or []
    use_snapshots = len(snapshots) > 0 and session_id is not None
    last_ai_message_idx = None
    ai_index = -1

    for idx, msg in enumerate(messages):
        if isinstance(msg, HumanMessage):
            with st.chat_message("user"):
                st.markdown(msg.content)
        elif isinstance(msg, AIMessage):
            ai_index += 1
            last_ai_message_idx = idx
            snapshot = snapshots[ai_index] if ai_index < len(snapshots) else None

            with st.chat_message("assistant"):
                st.markdown(msg.content)
                with st.container():
                    ac1, ac2, ac3 = st.columns([1, 1, 8])
                    with ac1:
                        st.button("👍", key=f"like_{idx}", help="Good response")
                    with ac2:
                        st.button("👎", key=f"dislike_{idx}", help="Poor response")
                    with ac3:
                        st.caption(f"· {datetime.now().strftime("%H:%M")}")

            if use_snapshots and snapshot:
                # Table for this turn (when no chart or chart failed but we have data)
                snap_insight = snapshot.get("insight_data")
                snap_viz_config = snapshot.get("viz_config")
                snap_viz_error = snapshot.get("viz_error")
                if show_data and snap_insight and snap_insight.get("type") == "dataframe":
                    if not snap_viz_config or snap_viz_error:
                        with st.chat_message("assistant"):
                            df = pd.DataFrame(snap_insight["data"])
                            rows, cols = snap_insight["shape"]
                            st.caption(f"📊 {rows} rows × {cols} columns")
                            st.dataframe(
                                df,
                                width="stretch",
                                height=min(380, (rows + 1) * 35 + 3),
                                hide_index=True,
                            )
                if snap_viz_config and not snap_viz_error:
                    fig = generate_chart_from_config_ui(snap_viz_config, session_id)
                    if fig is not None:
                        with st.chat_message("assistant"):
                            st.plotly_chart(fig, width="stretch", key=f"viz_{idx}")
                if snapshot.get("generated_code"):
                    with st.chat_message("assistant"):
                        with st.expander("🔍 See how this was computed", expanded=False):
                            st.code(snapshot["generated_code"], language="python")

    # Backward compatibility: no snapshots — show single viz/table/code after last AI message
    if not use_snapshots and last_ai_message_idx is not None:
        if show_data and insight_data is not None and viz_figure is None:
            if insight_data.get("type") == "dataframe":
                with st.chat_message("assistant"):
                    df = pd.DataFrame(insight_data["data"])
                    rows, cols = insight_data["shape"]
                    st.caption(f"📊 {rows} rows × {cols} columns")
                    st.dataframe(
                        df,
                        width="stretch",
                        height=min(380, (rows + 1) * 35 + 3),
                        hide_index=True,
                    )
        if viz_figure is not None:
            with st.chat_message("assistant"):
                st.plotly_chart(viz_figure, width="stretch", key=f"viz_{last_ai_message_idx}")
        if generated_code:
            with st.chat_message("assistant"):
                with st.expander("🔍 See how this was computed", expanded=False):
                    st.code(generated_code, language="python")


def generate_chart_from_config_ui(viz_config: dict, session_id: str):
    """Generate chart from configuration for UI display."""
    try:
        from data_visualization.visualization import generate_chart
        from .utils.session_loader import SessionLoader
        
        loader = SessionLoader()
        dfs = loader.load_session_dataframes(session_id)
        
        table_name = viz_config.get("table_name", "current")
        if table_name not in dfs:
            table_name = list(dfs.keys())[0]
        
        df = dfs[table_name]
        
        fig = generate_chart(
            df=df,
            chart_type=viz_config.get("chart_type", "bar"),
            x_col=viz_config.get("x_col"),
            y_col=viz_config.get("y_col"),
            agg_func=viz_config.get("agg_func", "none"),
            color_col=viz_config.get("color_col")
        )
        
        return fig
    except Exception as e:
        logger.error(f"Error generating chart: {e}")
        return None


def handle_chat_input(session_id: str, config: dict):
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
                    # Initialize other fields
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
                    result = graph.invoke(inputs, config)
                
                logger.info("Graph invoked successfully")
                typing_placeholder.empty()
                
                # Rerun to display updated state
                st.rerun()
                
            except Exception as e:
                logger.error(f"Error processing query: {e}", exc_info=True)
                with st.chat_message("assistant"):
                    st.error(f"Sorry, I encountered an error: {str(e)}")
                    st.info("Please try rephrasing your question or check if your data is still loaded.")
                    
                    # Show debug info in expander
                    with st.expander("🐛 Debug Information"):
                        st.code(traceback.format_exc())


def display_clear_button(config: dict):
    """Clear chat is now in sidebar."""
    pass
