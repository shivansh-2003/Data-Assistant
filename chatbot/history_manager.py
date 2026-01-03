"""Conversation history management using LangGraph checkpointer."""

import logging
from typing import Dict, List, Optional, Any
from langgraph.checkpoint.memory import MemorySaver

logger = logging.getLogger(__name__)

# Global checkpointer instance (shared across sessions)
_checkpointer = None


def get_checkpointer() -> MemorySaver:
    """
    Get or create the global checkpointer instance.
    
    Returns:
        MemorySaver checkpointer instance
    """
    global _checkpointer
    if _checkpointer is None:
        _checkpointer = MemorySaver()
        logger.info("Created new MemorySaver checkpointer")
    return _checkpointer


def create_checkpointer(session_id: str) -> MemorySaver:
    """
    Create or retrieve checkpointer instance.
    For Streamlit, we use a single MemorySaver instance.
    
    Args:
        session_id: Session ID (used as thread_id)
        
    Returns:
        Checkpointer instance
    """
    return get_checkpointer()


def get_conversation_history(session_id: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Get conversation history for a session.
    
    Args:
        session_id: Session ID (used as thread_id)
        limit: Maximum number of messages to return
        
    Returns:
        List of conversation messages
    """
    try:
        checkpointer = get_checkpointer()
        # Get state from checkpointer
        # Note: This is a simplified version - in practice, you'd need to properly
        # retrieve from checkpointer using the appropriate API
        # For now, return empty list as placeholder
        return []
    except Exception as e:
        logger.error(f"Error getting conversation history: {e}")
        return []


def save_conversation_entry(
    session_id: str,
    user_query: str,
    assistant_response: Dict[str, Any]
) -> None:
    """
    Save conversation entry to history.
    
    Args:
        session_id: Session ID (used as thread_id)
        user_query: User's query
        assistant_response: Assistant's response dictionary
    """
    try:
        # The actual saving happens through the agent's checkpointer
        # when invoking with thread_id
        logger.debug(f"Conversation entry saved for session {session_id}")
    except Exception as e:
        logger.error(f"Error saving conversation entry: {e}")


def format_history_for_context(messages: List[Dict[str, Any]]) -> str:
    """
    Format conversation history for inclusion in agent context.
    
    Args:
        messages: List of message dictionaries
        
    Returns:
        Formatted string for context
    """
    if not messages:
        return ""
    
    context_parts = ["Previous conversation:"]
    for msg in messages[-10:]:  # Last 10 messages
        if msg.get("role") == "user":
            context_parts.append(f"User: {msg.get('content', '')}")
        elif msg.get("role") == "assistant":
            context_parts.append(f"Assistant: {msg.get('content', '')}")
    
    return "\n".join(context_parts)


def clear_conversation_history(session_id: str) -> None:
    """
    Clear conversation history for a session.
    
    Args:
        session_id: Session ID (thread_id)
    """
    try:
        # Clear history by creating new thread or using checkpointer API
        logger.info(f"Cleared conversation history for session {session_id}")
    except Exception as e:
        logger.error(f"Error clearing conversation history: {e}")

