"""Chat input and graph invocation for InsightBot.

Streaming strategy — two modes combined:
  stream_mode=["values", "messages"]

  "values"   → full state snapshot after each node completes.
               Used for progressive status labels and triggering final re-render.

  "messages" → (AIMessageChunk, metadata) tuples emitted as the LLM generates tokens.
               metadata["langgraph_node"] tells us which node is speaking.
               We stream ONLY the responder node's tokens directly into the UI.

Result: users see text appearing word-by-word (like ChatGPT) instead of
waiting for the full response and then seeing it all at once.

Node status progression shown while waiting for the first token:
  router done     → "Understanding your question…"
  analyzer done   → "Selecting analysis tools…"
  planner done    → "Planning multi-step analysis…"
  insight done    → "Running analysis…"
  responder start → status clears, token stream begins
  suggestion done → st.rerun() loads full history (charts, tables, chips)
"""

import hashlib
import json
import streamlit as st
import logging
import traceback
from langchain_core.messages import HumanMessage, AIMessage, AIMessageChunk

from ..utils.session_loader import prepare_state_dataframes
from ..run_df_context import set_run_df_dict, reset_run_df_dict
from observability.langfuse_client import get_langfuse_client, update_trace_context


def _hash_schema(schema: dict) -> str:
    """Stable fingerprint for table_name+columns set; used to invalidate
    follow-up tool reuse when schema shifts between turns."""
    try:
        tables = (schema or {}).get("tables") or {}
        compact = {
            t: sorted((info or {}).get("columns") or [])
            for t, info in tables.items()
        }
        return hashlib.md5(
            json.dumps(compact, sort_keys=True).encode()
        ).hexdigest()
    except Exception:
        return ""

logger = logging.getLogger(__name__)

# Node name that emits the visible response text.
# Only tokens from this node are streamed to the UI.
_STREAMING_NODE = "responder"


def _status_label(snapshot: dict) -> str:
    """Derive a human-readable status caption from the latest state snapshot."""
    if snapshot.get("last_insight"):
        return "Running analysis…"
    if snapshot.get("plan"):
        return "Planning multi-step analysis…"
    if snapshot.get("tool_calls") is not None:
        return "Selecting analysis tools…"
    if snapshot.get("intent"):
        return "Selecting analysis tools…"
    return "Understanding your question…"


def _is_responder_chunk(metadata: dict) -> bool:
    """Return True when a message chunk comes from the responder node."""
    return metadata.get("langgraph_node") == _STREAMING_NODE


def handle_chat_input(session_id: str, config: dict, graph):
    """Handle user chat input and stream graph output token-by-token.

    Supports auto-submit when user clicked a suggestion or quick-action
    (pending_chat_query in session_state from a previous rerun).
    """
    # ── Input resolution ──────────────────────────────────────────────────────
    user_input = st.session_state.pop("pending_chat_query", None)
    if user_input is None:
        user_input = st.chat_input("Ask anything about your data…")
    if not user_input:
        st.caption(
            "e.g. *What's the average price by brand?* · "
            "*Plot sales over time* · *Top 10 by revenue*"
        )
        return

    # ── Show user message immediately ─────────────────────────────────────────
    with st.chat_message("user"):
        st.write(user_input)

    # ── Placeholders updated throughout the stream ────────────────────────────
    status_placeholder = st.empty()
    response_placeholder = st.empty()

    try:
        state_data = prepare_state_dataframes(session_id, st.session_state)

        # C-5: pull the prior turn's tool_calls + schema fingerprint from the
        # checkpointer so route_from_router can fast-path follow-ups without
        # firing the analyzer LLM again. Falls back gracefully on the very
        # first turn (no checkpoint yet). `prior_schema_hash` carries the
        # previous turn's schema hash so the router can compare against the
        # current turn's schema (computed from state["schema"]).
        prior_tool_calls = None
        prior_schema_hash = None
        try:
            snapshot = graph.get_state(config)
            prev_state = getattr(snapshot, "values", None) or {}
            prior_tool_calls = prev_state.get("tool_calls")
            prior_schema_hash = _hash_schema(prev_state.get("schema") or {})
        except Exception as e:
            logger.debug("No prior checkpoint state to reuse: %s", e)

        inputs = {
            "session_id": session_id,
            "messages": [HumanMessage(content=user_input)],
            "schema": state_data["schema"],
            "operation_history": state_data["operation_history"],
            "table_names": list(state_data["df_dict"].keys()),
            "data_profile": state_data.get("data_profile") or {"tables": {}},
            # df_dict lives in run_df_context only — never pass DataFrames into
            # graph state or the checkpointer will raise (msgpack).
            "user_tone": st.session_state.get("chatbot_user_tone", "explorer"),
            # Initialise all optional state fields so LangGraph doesn't error on missing keys
            "intent": None,
            "entities": None,
            "tool_calls": [],  # never None — LangGraph merge keeps null from overwriting to list
            "prior_tool_calls": prior_tool_calls,
            "prior_schema_hash": prior_schema_hash,
            "is_follow_up": None,
            "last_insight": None,
            "viz_config": None,
            "viz_type": None,
            "error": None,
            "sources": [],
        }

        logger.info("Starting token-level stream for query: %s…", user_input[:60])

        langfuse_client = get_langfuse_client()

        # ── Streaming state ───────────────────────────────────────────────────
        streamed_text = ""          # accumulated response text so far
        streaming_started = False   # True once first responder token received
        response_finalized = False  # True once we rendered the complete AIMessage

        _df_ctx_token = set_run_df_dict(state_data["df_dict"])
        try:
            with langfuse_client.start_as_current_observation(
                name="chatbot_query",
                as_type="agent",
                input=user_input,
                metadata={"source": "streamlit_chat"},
            ):
                update_trace_context(
                    session_id=session_id,
                    metadata={"source": "streamlit_chat"},
                )

                # ── Dual-mode stream ──────────────────────────────────────────
                # Each event is a tuple: (mode, data)
                #   mode == "values"   → data is the full state dict after a node
                #   mode == "messages" → data is (AIMessageChunk, metadata_dict)
                for event_type, event_data in graph.stream(
                    inputs,
                    config,
                    stream_mode=["values", "messages"],
                ):

                    # ── Token chunk from an LLM node ──────────────────────────
                    if event_type == "messages":
                        chunk, meta = event_data

                        # Only stream tokens that come from the responder node
                        if not _is_responder_chunk(meta):
                            continue

                        # Ignore non-text chunks (tool calls, function calls, etc.)
                        token = getattr(chunk, "content", "")
                        if not token or not isinstance(token, str):
                            continue

                        # First token: clear status, open assistant message frame
                        if not streaming_started:
                            status_placeholder.empty()
                            streaming_started = True

                        streamed_text += token

                        # Re-render the growing text inside an assistant chat bubble.
                        # st.empty() + container() gives us a stable DOM node to
                        # update in-place on every token without flicker.
                        with response_placeholder.container():
                            with st.chat_message("assistant"):
                                st.markdown(streamed_text + "▌")  # blinking cursor feel

                    # ── Full state snapshot after a node completes ────────────
                    elif event_type == "values":
                        snapshot = event_data
                        messages = snapshot.get("messages") or []
                        last_msg = messages[-1] if messages else None

                        # Responder finalized — replace preview with the clean
                        # final message (adds format_hint prefix/suffix, no cursor).
                        if (
                            not response_finalized
                            and streaming_started
                            and isinstance(last_msg, AIMessage)
                        ):
                            status_placeholder.empty()
                            with response_placeholder.container():
                                with st.chat_message("assistant"):
                                    st.markdown(last_msg.content)
                            response_finalized = True
                            # Keep iterating — suggestion node may still be running
                            continue

                        # Insight text is ready: show it as a live preview while
                        # the viz and responder nodes are still running.
                        # The responder AIMessage hasn't landed yet (last_msg is
                        # HumanMessage or None), so we show the raw insight first.
                        insight_text = snapshot.get("last_insight")
                        if (
                            insight_text
                            and not streaming_started
                            and not isinstance(last_msg, AIMessage)
                        ):
                            streaming_started = True
                            streamed_text = insight_text
                            status_placeholder.empty()
                            with response_placeholder.container():
                                with st.chat_message("assistant"):
                                    st.markdown(streamed_text)
                            logger.debug(
                                "Showing insight preview (%d chars) while viz/responder run",
                                len(insight_text),
                            )
                            continue

                        # No content yet — show progressive status caption
                        if not streaming_started:
                            label = _status_label(snapshot)
                            with status_placeholder.container():
                                with st.chat_message("assistant"):
                                    st.caption(f"_{label}_")

            # ── Fallback: if no tokens streamed but a response is in state ─────
            # (e.g. small-talk or clarification nodes that don't emit chunks)
            if not response_finalized and not streaming_started:
                try:
                    final_state = graph.get_state(config)
                    msgs = (final_state.values or {}).get("messages") or []
                    last = msgs[-1] if msgs else None
                    if isinstance(last, AIMessage):
                        status_placeholder.empty()
                        with response_placeholder.container():
                            with st.chat_message("assistant"):
                                st.markdown(last.content)
                except Exception:
                    pass

            logger.info("Graph stream completed — response_finalized=%s", response_finalized)
            status_placeholder.empty()

            # Trigger full re-render: loads charts, data tables, and suggestion chips
            # from response_snapshots via the normal message_history renderer.
            st.rerun()
        finally:
            reset_run_df_dict(_df_ctx_token)

    except Exception as e:
        logger.error("Error processing query: %s", e, exc_info=True)
        status_placeholder.empty()
        response_placeholder.empty()
        with st.chat_message("assistant"):
            st.error(f"Sorry, I encountered an error: {str(e)}")
            st.info(
                "Please try rephrasing your question or check if your data is still loaded."
            )
            with st.expander("🐛 Debug information"):
                st.code(traceback.format_exc())