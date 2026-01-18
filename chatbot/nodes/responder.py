"""Responder node for final response formatting."""

import logging
from typing import Dict
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
import os
from langfuse import observe

from observability.langfuse_client import update_trace_context

from ..prompts import PROMPTS

logger = logging.getLogger(__name__)


@observe(name="chatbot_responder", as_type="chain")
def responder_node(state: Dict) -> Dict:
    """
    Format final response combining insights and visualizations.
    
    Process:
    1. Combine insights and viz info
    2. Format as natural language
    3. Add to message history
    4. Return updated state
    """
    try:
        update_trace_context(session_id=state.get("session_id"), metadata={"node": "responder"})
        intent = state.get("intent", "data_query")
        messages = state.get("messages", [])
        last_message = messages[-1]
        query = last_message.content if hasattr(last_message, 'content') else str(last_message)
        
        # Handle small talk
        if intent == "small_talk":
            response_text = generate_small_talk_response(query)
        # Handle critical errors (but not viz failures)
        elif state.get("error") and not state.get("last_insight"):
            # Only show error if we have no insights to show
            response_text = f"I encountered an issue: {state['error']}. Could you try rephrasing your question?"
        # Handle data queries
        else:
            insight = state.get("last_insight", "")
            viz_config = state.get("viz_config")
            
            # Check if visualization was successfully created
            has_viz = viz_config is not None
            
            if insight and has_viz:
                response_text = f"{insight}\n\nI've created a visualization to help illustrate this."
            elif insight:
                # Have insight, no viz - that's fine!
                response_text = insight
            elif has_viz:
                response_text = "Here's a visualization of your data based on your request."
            else:
                # No insight or viz - generate generic response
                response_text = format_fallback_response(query, state)
        
        # Add response to messages
        state["messages"].append(AIMessage(content=response_text))
        
        logger.info(f"Generated response ({len(response_text)} chars)")
        
        return state
        
    except Exception as e:
        logger.error(f"Error in responder node: {e}", exc_info=True)
        # Emergency fallback
        state["messages"].append(
            AIMessage(content="I'm having trouble processing your request. Please try again.")
        )
        return state


def generate_small_talk_response(query: str) -> str:
    """Generate response for small talk."""
    try:
        llm = ChatOpenAI(
            model=os.getenv("OPENAI_MODEL", "gpt-4o"),
            temperature=0.7,
            api_key=os.getenv("OPENAI_API_KEY")
        )
        
        response = llm.invoke([
            SystemMessage(content=PROMPTS["small_talk"]),
            HumanMessage(content=query)
        ])
        
        return response.content
        
    except Exception as e:
        logger.error(f"Error generating small talk: {e}")
        return "Hello! I'm here to help you analyze your data. What would you like to know?"


def format_fallback_response(query: str, state: Dict) -> str:
    """Format fallback response when no insight or viz available."""
    try:
        llm = ChatOpenAI(
            model=os.getenv("OPENAI_MODEL", "gpt-4o"),
            temperature=0.3,
            api_key=os.getenv("OPENAI_API_KEY")
        )
        
        schema = state.get("schema", {})
        
        prompt = f"""The user asked: {query}

Session data schema: {schema}

Generate a helpful response acknowledging their question and suggesting how you could help analyze their data."""
        
        response = llm.invoke([
            SystemMessage(content=PROMPTS["responder"]),
            HumanMessage(content=prompt)
        ])
        
        return response.content
        
    except Exception as e:
        logger.error(f"Error formatting fallback: {e}")
        return "I'd be happy to help you analyze your data! Could you please rephrase your question or be more specific about what you'd like to know?"

