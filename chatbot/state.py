"""State schema for InsightBot LangGraph implementation."""

from typing import TypedDict, Annotated, List, Dict, Optional, Any
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage


class State(TypedDict):
    """State schema for InsightBot conversation graph.
    
    Note: DataFrames are NOT stored in state (not serializable).
    They are loaded fresh from Redis using session_id.
    """
    
    # Session identification
    session_id: str
    
    # Conversation history with automatic message reduction
    messages: Annotated[List[BaseMessage], add_messages]
    
    # Data context (metadata only, not actual DataFrames)
    schema: Dict[str, Any]
    operation_history: List[Dict[str, Any]]
    table_names: List[str]  # List of available table names
    
    # Query processing
    intent: Optional[str]  # "data_query", "visualization_request", "small_talk"
    entities: Optional[Dict[str, Any]]  # Extracted entities (columns, operations)
    tool_calls: Optional[List[Dict[str, Any]]]  # Tools to execute
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
    sources: Optional[List[str]]  # Tools used
    suggestions: Optional[List[str]]  # 3 contextual follow-up questions (for UI chips)
    # Per-turn snapshots so the UI can show chart/table/code for each AI message (not just the latest)
    response_snapshots: Optional[List[Dict[str, Any]]]  # Per-turn: viz_config, insight_data, generated_code, viz_error

