"""State schema for InsightBot LangGraph implementation."""

from typing import TypedDict, Annotated, List, Dict, Optional, Any
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage
import pandas as pd
import plotly.graph_objects as go


class State(TypedDict):
    """State schema for InsightBot conversation graph."""
    
    # Session identification
    session_id: str
    
    # Conversation history with automatic message reduction
    messages: Annotated[List[BaseMessage], add_messages]
    
    # Data context
    df_dict: Dict[str, pd.DataFrame]
    schema: Dict[str, Any]
    operation_history: List[Dict[str, Any]]
    
    # Query processing
    intent: Optional[str]  # "data_query", "visualization_request", "small_talk"
    entities: Optional[Dict[str, Any]]  # Extracted entities (columns, operations)
    tool_calls: Optional[List[Dict[str, Any]]]  # Tools to execute
    
    # Results
    last_insight: Optional[str]  # Text insight from pandas analysis
    insight_data: Optional[Any]  # Raw data from analysis
    viz_figure: Optional[go.Figure]  # Plotly figure
    viz_type: Optional[str]  # Chart type
    
    # Error handling
    error: Optional[str]
    
    # Response metadata
    sources: Optional[List[str]]  # Tools used
    data_snippets: Optional[List[Dict[str, Any]]]  # Extracted data

