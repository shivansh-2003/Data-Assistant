"""Message history and session display for InsightBot."""

import streamlit as st
from datetime import datetime
from langchain_core.messages import HumanMessage, AIMessage


def display_session_pill(session_id: str):
    """Compact session indicator (pill) with optional expandable details."""
    try:
        from ..utils.session_loader import SessionLoader
        loader = SessionLoader()
        summary = loader.get_session_summary(session_id)
        tables = summary.get("table_count", 0)
        file_name = summary.get("file_name") or "Uploaded file"
        if len(file_name) > 18:
            file_name = file_name[:15] + "…"
        st.caption(f"📁 {file_name} · {tables} table{'s' if tables != 1 else ''}")
    except Exception:
        st.caption(f"Session: {session_id[:12]}…")


def display_session_info(session_id: str):
    """Display session information in an expander (legacy / optional)."""
    try:
        from ..utils.session_loader import SessionLoader
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

            with st.chat_message("assistant"):
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
