"""State schema for InsightBot LangGraph implementation."""

from typing import TypedDict, Annotated, List, Dict, Optional, Any, Callable
import pandas as pd
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage

# Formal contract for graph nodes: accept state dict, return updated state dict
Node = Callable[[Dict[str, Any]], Dict[str, Any]]


class State(TypedDict):
    """State schema for InsightBot conversation graph.

    Live DataFrames for a run are supplied via ``chatbot.run_df_context``
    (ContextVar) from the UI — they must **not** appear in graph inputs or
    checkpointed state (LangGraph/msgpack cannot serialize ``DataFrame``).
    The optional ``df_dict`` key exists only for tests or callers that inject
    frames without a checkpointer; production Streamlit passes ``table_names``
    + ``schema`` and uses the context var.
    """

    # Session identification
    session_id: str

    # Conversation history with automatic message reduction
    messages: Annotated[List[BaseMessage], add_messages]

    # Data context (metadata + the actual DataFrames for this run)
    schema: Dict[str, Any]
    operation_history: List[Dict[str, Any]]
    table_names: List[str]  # List of available table names
    data_profile: Optional[Dict[str, Any]]  # Per-table/column: dtype, n_unique, n_null for analyzer/viz
    df_dict: Optional[Dict[str, pd.DataFrame]]  # Loaded once at graph entry; nodes read from here
    
    # Query processing
    intent: Optional[str]  # "data_query", "visualization_request", "small_talk"
    sub_intent: Optional[str]  # compare, trend, correlate, segment, distribution, filter, report, general
    implicit_viz_hint: Optional[bool]  # True for exploratory queries where a chart is appropriate
    entities: Optional[Dict[str, Any]]  # Extracted entities (columns, operations)
    tool_calls: Optional[List[Dict[str, Any]]]  # Tools to execute
    # Follow-up reuse (C-5): on a follow-up turn, the UI passes the prior turn's
    # tool selection so the analyzer LLM call can be skipped if the schema hasn't
    # changed. `prior_schema_hash` lets the router invalidate the reuse when the
    # underlying tables drift between turns.
    prior_tool_calls: Optional[List[Dict[str, Any]]]
    prior_schema_hash: Optional[str]
    is_follow_up: Optional[bool]  # Set by router when the message is a short follow-up
    plan: Optional[List[Dict[str, Any]]]  # Multi-step plan: [{"step": 1, "description": "...", "code": "..."}, ...]
    needs_planning: Optional[bool]  # True if query requires multi-step reasoning
    effective_query: Optional[str]  # Resolved query when follow-up (e.g. "What about max?" -> "Show max revenue by region")
    conversation_context: Optional[Dict[str, Any]]  # last_columns, last_aggregation, last_group_by, active_filters, current_topic, last_query
    needs_clarification: Optional[bool]  # True when multiple columns match one mention
    clarification_options: Optional[List[str]]  # Candidate column names to ask user
    clarification_type: Optional[str]  # e.g. "column"
    clarification_resolved: Optional[Dict[str, Any]]  # User's choice next turn, e.g. {"sales": "sales_amount"}
    clarification_mention: Optional[str]  # The ambiguous term that matched multiple columns, e.g. "sales"
    clarification_original_query: Optional[str]  # User query when we asked for clarification (for resolution next turn)
    
    # Results (serializable only)
    last_insight: Optional[str]  # Text insight from pandas analysis
    insight_data: Optional[Dict[str, Any]]  # DataFrame as dict (for filtering queries) or value
    viz_config: Optional[Dict[str, Any]]  # Chart configuration (not the figure itself)
    viz_type: Optional[str]  # Chart type
    chart_reason: Optional[str]  # One-line reason for chart type choice ("Bar chart to compare categories.")
    one_line_insight: Optional[str]  # Mandatory single-sentence takeaway from analysis
    generated_code: Optional[str]  # Pandas code used for last insight (for "Show code")
    
    # Error handling
    error: Optional[str]
    error_suggestion: Optional[Dict[str, Any]]  # e.g. {"type": "did_you_mean", "suggested_columns": [...], "bad_column": "..."}
    viz_error: Optional[str]  # When chart generation fails (e.g. "Too many categories")
    
    # Response metadata
    user_tone: Optional[str]  # "technical", "executive", "explorer" for response style
    sources: Optional[List[str]]  # Tools used
    suggestions: Optional[List[str]]  # 3 contextual follow-up questions (for UI chips)
    # Per-turn snapshots so the UI can show chart/table/code for each AI message (not just the latest)
    response_snapshots: Optional[List[Dict[str, Any]]]  # Per-turn: viz_config, insight_data, generated_code, viz_error

