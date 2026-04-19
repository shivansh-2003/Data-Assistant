"""Message history and session display for InsightBot."""

import streamlit as st
from datetime import datetime
from langchain_core.messages import HumanMessage, AIMessage


@st.cache_data(show_spinner=False, ttl=300)
def _load_session_pill_data(session_id: str) -> dict:
    """Fetch only the metadata fields needed for the session pill.

    Uses the Redis store's ``get_metadata`` directly — avoids loading full
    DataFrames the way ``get_session_summary`` does.  Cached per session_id
    for 5 minutes so the pill text doesn't hit Redis on every Streamlit rerun.
    """
    from redis_db import get_session_store
    try:
        store = get_session_store()
        meta = store.get_metadata(session_id) or {}
        # Count tables via a lightweight key listing rather than deserialising
        # the full DataFrames.  Fall back to loading if count is unavailable.
        table_count = meta.get("table_count")
        if table_count is None:
            tables = store.load_session(session_id) or {}
            table_count = len(tables)
        return {
            "file_name": meta.get("file_name") or "Uploaded file",
            "table_count": int(table_count),
        }
    except Exception:
        return {"file_name": "Uploaded file", "table_count": 0}


def display_session_pill(session_id: str):
    """Compact session indicator (pill) — metadata only, no DataFrame load."""
    try:
        info = _load_session_pill_data(session_id)
        file_name = info["file_name"]
        tables = info["table_count"]
        if len(file_name) > 18:
            file_name = file_name[:15] + "…"
        st.caption(f"📁 {file_name} · {tables} table{'s' if tables != 1 else ''}")
    except Exception:
        st.caption(f"Session: {session_id[:12]}…")


def display_session_info(session_id: str):
    """Display session information in an expander (legacy / optional)."""
    try:
        info = _load_session_pill_data(session_id)  # reuse the cached metadata fetch
        with st.expander("📋 Session details", expanded=False):
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**Session ID:** `{session_id[:24]}…`")
                st.write(f"**Tables:** {info.get('table_count', 0)}")
            with col2:
                if info.get("file_name"):
                    st.write(f"**File:** {info.get('file_name')}")
    except Exception as e:
        import logging
        logging.warning(f"Could not load session summary: {e}")


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
    from .chart_ui import generate_chart_from_config_ui

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
            key_finding = None
            if hasattr(msg, "additional_kwargs") and msg.additional_kwargs:
                key_finding = msg.additional_kwargs.get("key_finding") or msg.additional_kwargs.get("one_line_insight")
            if snapshot and key_finding is None:
                key_finding = snapshot.get("key_finding") or snapshot.get("one_line_insight")

            with st.chat_message("assistant"):
                if key_finding:
                    st.markdown(f'<div class="insightbot-key-finding" role="status">💡 {key_finding}</div>', unsafe_allow_html=True)
                st.markdown(msg.content)
                with st.container():
                    ac1, ac2, ac3 = st.columns([1, 1, 8])
                    with ac1:
                        st.button("👍", key=f"like_{idx}", help="Good response")
                    with ac2:
                        st.button("👎", key=f"dislike_{idx}", help="Poor response")
                    with ac3:
                        st.caption(f"· {datetime.now().strftime('%H:%M')}")

            if use_snapshots and snapshot:
                snap_insight = snapshot.get("insight_data")
                snap_viz_config = snapshot.get("viz_config")
                snap_viz_error = snapshot.get("viz_error")
                has_table = show_data and snap_insight and snap_insight.get("type") == "dataframe" and (not snap_viz_config or snap_viz_error)
                has_chart = snap_viz_config and not snap_viz_error
                if has_table or has_chart:
                    with st.chat_message("assistant"):
                        with st.expander("Show detailed breakdown", expanded=True):
                            if has_table:
                                df = pd.DataFrame(snap_insight["data"])
                                rows, cols = snap_insight["shape"]
                                st.caption(f"📊 {rows} rows × {cols} columns")
                                st.dataframe(
                                    df,
                                    width="stretch",
                                    height=min(380, (rows + 1) * 35 + 3),
                                    hide_index=True,
                                )
                                csv_data = df.to_csv(index=False)
                                st.download_button("Export CSV", data=csv_data, file_name="insight_data.csv", mime="text/csv", key=f"export_{idx}")
                            if has_chart:
                                fig = generate_chart_from_config_ui(snap_viz_config, session_id)
                                if fig is not None:
                                    st.plotly_chart(fig, width="stretch", key=f"viz_{idx}")
                        st.markdown('<div class="action-bar" role="group" aria-label="Message actions">', unsafe_allow_html=True)
                        act1, act2, act3 = st.columns(3)
                        with act1:
                            if st.button("Refine", key=f"refine_{idx}", help="Ask a follow-up"):
                                if "pending_chat_query" not in st.session_state:
                                    st.session_state["pending_chat_query"] = "Can you break this down further or add more detail?"
                                st.rerun()
                        with act2:
                            st.button("Save insight", key=f"save_insight_{idx}", help="Save to session (placeholder)")
                        with act3:
                            st.button("Share", key=f"share_{idx}", help="Copy or share (placeholder)")
                        st.markdown("</div>", unsafe_allow_html=True)
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
