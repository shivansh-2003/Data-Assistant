"""
InsightBot - LangGraph-based chatbot for Data Assistant Platform.
Provides intelligent conversational interface with stateful memory and visualization support.
"""

from .streamlit_ui import render_chatbot_tab
from .graph import graph
from .state import State, Node
from .utils.session_loader import SessionLoader, prepare_state_dataframes

__all__ = [
    "render_chatbot_tab",
    "graph",
    "State",
    "Node",
    "SessionLoader",
    "prepare_state_dataframes"
]

__version__ = "2.0.0"  # InsightBot version
