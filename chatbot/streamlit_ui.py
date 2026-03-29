"""Streamlit UI for InsightBot. Orchestrates tab layout and delegates to ui components."""

import streamlit as st
import logging

from .graph import graph
from .utils.session_loader import prepare_state_dataframes
from .constants import USER_TONES, USER_TONE_EXPLORER
from .ui import (
    display_message_history,
    display_session_pill,
    handle_chat_input,
    generate_chart_from_config_ui,
)
from components.empty_state import render_empty_state

logger = logging.getLogger(__name__)

CHATBOT_CSS = """
<style>
  [data-testid="stChatBot"] .stChatMessage { margin-bottom: 0.5rem; }
  div[data-testid="stVerticalBlock"] > div:has(> div[data-testid="stChatMessage"]) { margin-bottom: 0.25rem; }
  .insightbot-hero { padding: 0.5rem 0 1rem 0; border-bottom: 1px solid var(--border-color, #e5e7eb); margin-bottom: 1rem; }
  .insightbot-session-pill { display: inline-flex; align-items: center; gap: 0.5rem; padding: 0.35rem 0.75rem; 
    background: var(--secondary-background-color, #f3f4f6); border-radius: 9999px; font-size: 0.8rem; color: var(--text-color, #374151); margin-top: 0.25rem; }
  .insightbot-suggestions { padding: 0.75rem; background: var(--secondary-background-color, #f8fafc); border-radius: 12px; margin: 0.75rem 0; }
  .insightbot-suggestions button, .insightbot-quick-actions button { border-radius: 999px; padding: 6px 14px; 
    font-weight: 500; background: var(--primary-50, #eef2ff); border: 1px solid var(--border, #e5e7eb); transition: background 0.2s; }
  .insightbot-suggestions button:hover, .insightbot-quick-actions button:hover { background: rgba(102, 126, 234, 0.18); }
  .insightbot-quick-actions { display: flex; flex-wrap: wrap; gap: 0.5rem; margin: 0.5rem 0; }
  .insightbot-code-expander { border-radius: 8px; overflow: hidden; border: 1px solid var(--border-color, #e5e7eb); }
  .insightbot-timestamp { font-size: 0.7rem; opacity: 0.7; }
  .insightbot-key-finding { background: var(--primary-50, #eef2ff); border-left: 4px solid var(--primary-600, #667eea); padding: 0.75rem 1rem; border-radius: 0 8px 8px 0; margin: 0.5rem 0; font-weight: 500; }
  .insightbot-analyzing { animation: pulse 2s ease-in-out infinite; }
  .action-bar { display: flex; gap: 0.5rem; align-items: center; margin-top: 0.5rem; padding-top: 0.5rem; border-top: 1px solid var(--border-color, #e5e7eb); }
  @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.6; } }
</style>
"""




def render_chatbot_tab():
    """Main function to render the InsightBot chatbot tab."""
    st.markdown(CHATBOT_CSS, unsafe_allow_html=True)

    session_id = st.session_state.get("current_session_id")

    if not session_id:
        render_empty_state(
            title="No data loaded yet",
            message="Upload a file in the Upload tab to start asking questions.",
            primary_action_label="Go to Upload",
            primary_action_key="empty_chatbot_upload",
            secondary_action_label="Example questions",
            secondary_action_key="empty_chatbot_examples",
            icon="💬",
        )
        return

    st.markdown('<div class="card-elevated hero-section" role="region" aria-label="Chatbot header">', unsafe_allow_html=True)
    col_title, col_pill = st.columns([1, 0.35])
    with col_title:
        st.markdown('<h2 class="section-title">💬 InsightBot</h2>', unsafe_allow_html=True)
        st.markdown('<p class="section-subtitle">Ask questions in plain language. Get insights, tables, and charts from your data.</p>', unsafe_allow_html=True)
    with col_pill:
        display_session_pill(session_id)
    st.markdown("</div>", unsafe_allow_html=True)
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
            _current_tone = st.session_state.get("chatbot_user_tone", USER_TONE_EXPLORER)
            _tone_index = list(USER_TONES).index(_current_tone) if _current_tone in USER_TONES else 0
            st.selectbox(
                "Response style",
                options=list(USER_TONES),
                index=_tone_index,
                format_func=lambda x: {"explorer": "Explorer (suggestive)", "technical": "Technical (show code)", "executive": "Executive (brief KPIs)"}[x],
                key="chatbot_user_tone",
                help="Explorer: curious, suggestive. Technical: emphasize code. Executive: short, KPI-focused.",
            )
            st.markdown("---")
            st.markdown('<div class="card" role="region" aria-label="Quick questions">', unsafe_allow_html=True)
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
            st.markdown("</div>", unsafe_allow_html=True)

        if current_state and current_state.values:
            messages = current_state.values.get("messages", [])
            response_snapshots = current_state.values.get("response_snapshots") or []
            suggestions = current_state.values.get("suggestions") or []

            viz_config = current_state.values.get("viz_config")
            insight_data = current_state.values.get("insight_data")
            generated_code = current_state.values.get("generated_code")
            viz_figure = None
            viz_error = current_state.values.get("viz_error")
            if not response_snapshots and viz_config and not viz_error:
                viz_figure = generate_chart_from_config_ui(viz_config, session_id)

            st.markdown('<div class="card-elevated" role="region" aria-label="Chat messages">', unsafe_allow_html=True)
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
                st.markdown('<div class="insightbot-suggestions">', unsafe_allow_html=True)
                st.markdown("**💡 Suggested follow-ups**")
                sug_cols = st.columns(min(3, len(suggestions)))
                for i, sug in enumerate(suggestions[:3]):
                    with sug_cols[i]:
                        label = (sug[:48] + "…") if len(sug) > 48 else sug
                        if st.button(label, key=f"sug_{i}", use_container_width=True):
                            st.session_state["pending_chat_query"] = sug
                            st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

        st.markdown('<div class="card-elevated" role="region" aria-label="Chat input">', unsafe_allow_html=True)
        handle_chat_input(session_id, config, graph)
        st.markdown("</div>", unsafe_allow_html=True)

    except Exception as e:
        logger.error(f"Error in chatbot tab: {e}", exc_info=True)
        st.error(f"An error occurred: {str(e)}")
        st.info("Try refreshing the page or uploading new data.")
