"""Router node for intent classification."""

import logging
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from typing import Dict, List, Optional
import os

try:
    from pydantic import BaseModel, Field
except ImportError:
    # Fallback for older LangChain versions
    from langchain_core.pydantic_v1 import BaseModel, Field  # type: ignore

from ..prompts import PROMPTS

logger = logging.getLogger(__name__)


class IntentClassification(BaseModel):
    """Intent classification result."""
    intent: str = Field(description="Query intent: data_query, visualization_request, or small_talk")
    mentioned_columns: List[str] = Field(default_factory=list, description="Column names mentioned")
    operations: List[str] = Field(default_factory=list, description="Operations mentioned (mean, sum, etc.)")
    confidence: float = Field(default=1.0, description="Classification confidence")


def router_node(state: Dict) -> Dict:
    """
    Classify user query intent and extract entities.
    
    Routes to:
    - Analyzer for data queries and viz requests
    - Responder for small talk
    """
    try:
        # Get last user message
        messages = state.get("messages", [])
        if not messages:
            return state
        
        last_message = messages[-1]
        query = last_message.content if hasattr(last_message, 'content') else str(last_message)
        
        # Prepare context
        schema = state.get("schema", {})
        operation_history = state.get("operation_history", [])
        
        # Format prompt
        system_prompt = PROMPTS["router"].format(
            schema=schema,
            operation_history=operation_history[-5:] if operation_history else []
        )
        
        # Initialize LLM with structured output
        llm = ChatOpenAI(
            model=os.getenv("OPENAI_MODEL", "gpt-4o"),
            temperature=0.1,
            api_key=os.getenv("OPENAI_API_KEY")
        )
        
        structured_llm = llm.with_structured_output(IntentClassification)
        
        # Classify intent
        result = structured_llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=query)
        ])
        
        # Update state
        state["intent"] = result.intent
        state["entities"] = {
            "mentioned_columns": result.mentioned_columns,
            "operations": result.operations
        }
        
        logger.info(f"Classified intent: {result.intent} (confidence: {result.confidence})")
        
        return state
        
    except Exception as e:
        logger.error(f"Error in router node: {e}", exc_info=True)
        state["error"] = f"Intent classification failed: {str(e)}"
        state["intent"] = "data_query"  # Default fallback
        return state

