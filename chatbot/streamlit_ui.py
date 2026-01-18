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


def render_chatbot_tab():
    """Main function to render the InsightBot chatbot tab."""
    st.header("💬 InsightBot - Ask Anything About Your Data")
    st.caption("Ask questions, get insights, and generate charts from your data in plain language.")
    
    session_id = st.session_state.get("current_session_id")
    
    # Check if session exists
    if not session_id:
        show_upload_warning()
        return
    
    # Initialize graph config
    config = {"configurable": {"thread_id": session_id}}
    
    try:
        # Load current graph state
        current_state = graph.get_state(config)
        
        # Display session info
        display_session_info(session_id)
        
        st.divider()
        
        # Display message history
        if current_state and current_state.values:
            messages = current_state.values.get("messages", [])
            viz_config = current_state.values.get("viz_config")
            insight_data = current_state.values.get("insight_data")
            
            show_data = st.toggle(
                "Show data tables in responses",
                value=True,
                help="Hide data tables when you only want narrative answers or charts."
            )
            
            # Generate chart from config if present
            viz_figure = None
            if viz_config:
                viz_figure = generate_chart_from_config_ui(viz_config, session_id)
            
            display_message_history(messages, viz_figure, insight_data, show_data=show_data)

            # Quick action chips
            st.markdown("**Quick actions**")
            qa1, qa2, qa3, qa4 = st.columns(4)
            with qa1:
                if st.button("📊 Summary stats", key="qa_summary"):
                    st.session_state["chat_prefill"] = "Show summary statistics for the main table"
            with qa2:
                if st.button("📈 Trend", key="qa_trend"):
                    st.session_state["chat_prefill"] = "Plot the trend over time for the main metric"
            with qa3:
                if st.button("🔍 Top 10", key="qa_top10"):
                    st.session_state["chat_prefill"] = "Show the top 10 rows by the primary numeric column"
            with qa4:
                if st.button("🎯 Correlation", key="qa_corr"):
                    st.session_state["chat_prefill"] = "Show correlation between the two most important numeric columns"
        
        # Chat input
        handle_chat_input(session_id, config)
        
        # Clear chat button
        if current_state and current_state.values.get("messages"):
            display_clear_button(config)
        
    except Exception as e:
        logger.error(f"Error in chatbot tab: {e}", exc_info=True)
        st.error(f"An error occurred: {str(e)}")
        st.info("Try refreshing the page or uploading new data.")


def show_upload_warning():
    """Display warning when no session is active."""
    st.warning("⚠️ No active session found. Please upload a file in the Upload tab first.")
    st.info("💡 After uploading a file, you can ask questions about your data here.")
    
    # Show example queries
    with st.expander("💡 Example Queries (after uploading data)"):
        st.markdown("""
        **Statistical Queries:**
        - "What's the average salary by department?"
        - "Show me the median age"
        - "Calculate the correlation between price and sales"
        
        **Comparative Queries:**
        - "Which department has the highest average salary?"
        - "Compare sales between Q1 and Q2"
        - "Show me the top 10 customers by revenue"
        
        **Trend Queries:**
        - "Show me sales over time"
        - "How has revenue changed in the last quarter?"
        - "Display monthly trends for user signups"
        
        **Distribution Queries:**
        - "What is the distribution of ages?"
        - "Show me how salaries are distributed"
        
        **Visualization Requests:**
        - "Create a bar chart of sales by region"
        - "Plot revenue over time as a line chart"
        - "Show me a scatter plot of price vs quantity"
        """)


def display_session_info(session_id: str):
    """Display session information."""
    try:
        from .utils.session_loader import SessionLoader
        loader = SessionLoader()
        summary = loader.get_session_summary(session_id)
        
        with st.expander("📋 Session Information", expanded=False):
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**Session ID:** {session_id[:20]}...")
                st.write(f"**Tables:** {summary.get('table_count', 0)}")
            with col2:
                if summary.get('file_name'):
                    st.write(f"**File:** {summary.get('file_name')}")
                if summary.get('file_type'):
                    st.write(f"**Type:** {summary.get('file_type')}")
    except Exception as e:
        logger.warning(f"Could not load session summary: {e}")


def display_message_history(messages: list, viz_figure=None, insight_data=None, show_data: bool = True):
    """Display chat message history with optional DataFrame and visualization."""
    import pandas as pd
    
    # Track which message has the viz/data
    last_ai_message_idx = None
    
    for idx, msg in enumerate(messages):
        # Determine if this is a user or assistant message
        if isinstance(msg, HumanMessage):
            with st.chat_message("user"):
                st.write(msg.content)
        elif isinstance(msg, AIMessage):
            last_ai_message_idx = idx
            with st.chat_message("assistant"):
                st.write(msg.content)
                # Message actions
                action_col1, action_col2, action_col3 = st.columns([1, 1, 6])
                with action_col1:
                    st.button("👍", key=f"like_{idx}")
                with action_col2:
                    st.button("👎", key=f"dislike_{idx}")
                with action_col3:
                    st.caption(datetime.now().strftime("Responded %H:%M:%S"))
    
    # Display DataFrame ONLY if there's NO visualization
    # (For filtering/listing queries without charts)
    if show_data and insight_data is not None and last_ai_message_idx is not None and viz_figure is None:
        if insight_data.get("type") == "dataframe":
            with st.chat_message("assistant"):
                # Convert back to DataFrame for display
                df = pd.DataFrame(insight_data["data"])
                
                # Show shape info
                rows, cols = insight_data["shape"]
                st.caption(f"📊 Showing {rows} rows × {cols} columns")
                
                # Display with fixed height and scrolling
                st.dataframe(
                    df,
                    width='stretch',
                    height=min(400, (rows + 1) * 35 + 3),  # Max 400px, auto-adjust for small results
                    hide_index=True
                )
    
    # Display visualization (takes precedence over DataFrame)
    if viz_figure is not None and last_ai_message_idx is not None:
        with st.chat_message("assistant"):
            st.plotly_chart(viz_figure, width='stretch', key=f"viz_{last_ai_message_idx}")


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
    """Handle user chat input and invoke graph."""
    st.caption("Tip: Ask for a chart directly, e.g., 'Plot revenue by month as a line chart.'")
    prefill = st.session_state.pop("chat_prefill", "")
    if prefill:
        st.info(f"Suggestion: {prefill}")
    user_input = st.chat_input("Ask anything about your data...")
    
    if user_input:
        # Display user message immediately
        with st.chat_message("user"):
            st.write(user_input)
        
        # Process query
        with st.spinner("🤔 Thinking..."):
            typing_placeholder = st.empty()
            with typing_placeholder.container():
                with st.chat_message("assistant"):
                    st.markdown("⌛ **InsightBot is thinking...**")
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
    """Display clear chat button."""
    st.divider()
    col1, col2 = st.columns([4, 1])
    with col2:
        if st.button("🗑️ Clear Chat", key="clear_chat"):
            try:
                # Clear the checkpointer state for this thread
                # Note: MemorySaver doesn't have a direct clear method
                # We need to manually clear by creating a new thread or resetting
                logger.info("Clearing chat history")
                st.rerun()
            except Exception as e:
                logger.error(f"Error clearing chat: {e}")
                st.error("Could not clear chat history")
