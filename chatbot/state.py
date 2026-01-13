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
    
    # Results (serializable only)
    last_insight: Optional[str]  # Text insight from pandas analysis
    insight_data: Optional[Dict[str, Any]]  # DataFrame as dict (for filtering queries) or value
    viz_config: Optional[Dict[str, Any]]  # Chart configuration (not the figure itself)
    viz_type: Optional[str]  # Chart type
    
    # Error handling
    error: Optional[str]
    
    # Response metadata
    sources: Optional[List[str]]  # Tools used

