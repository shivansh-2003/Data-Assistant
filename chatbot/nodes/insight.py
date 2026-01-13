"""Insight node for pandas analysis and code generation."""

import logging
from typing import Dict, Any
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
import os

from ..prompts import PROMPTS
from ..execution import generate_pandas_code, execute_pandas_code

logger = logging.getLogger(__name__)


def insight_node(state: Dict) -> Dict:
    """
    Generate pandas code, execute it, and summarize results.
    
    Process:
    1. Generate pandas code using LLM
    2. Execute code safely
    3. Summarize output into natural language
    4. Store insight in state
    """
    try:
        tool_calls = state.get("tool_calls", [])
        
        # Find insight tool calls
        insight_calls = [tc for tc in tool_calls if tc.get("name") == "insight_tool"]
        
        if not insight_calls:
            return state
        
        # Get query and context
        messages = state.get("messages", [])
        last_message = messages[-1]
        query = last_message.content if hasattr(last_message, 'content') else str(last_message)
        
        session_id = state.get("session_id")
        schema = state.get("schema", {})
        
        # Load DataFrames from Redis
        from ..utils.session_loader import SessionLoader
        loader = SessionLoader()
        try:
            df_dict = loader.load_session_dataframes(session_id)
        except Exception as e:
            state["error"] = f"Could not load data: {str(e)}"
            return state
        
        if not df_dict:
            state["error"] = "No data available for analysis"
            return state
        
        # Process first insight call (can extend to handle multiple)
        insight_call = insight_calls[0]
        insight_query = insight_call.get("args", {}).get("query", query)
        
        # Generate pandas code
        logger.info(f"Generating pandas code for: {insight_query[:50]}...")
        code = generate_pandas_code(
            query=insight_query,
            schema=schema,
            df_names=list(df_dict.keys())
        )
        
        # Execute code
        logger.info("Executing pandas code...")
        execution_result = execute_pandas_code(code, df_dict)
        
        if not execution_result["success"]:
            state["error"] = f"Analysis failed: {execution_result['error']}"
            return state
        
        output = execution_result["output"]
        
        # Summarize output using LLM
        logger.info("Summarizing results...")
        summary = summarize_insight(insight_query, output)
        
        # Store results
        state["last_insight"] = summary
        
        # If output is a DataFrame, store it as dict for serialization
        # This allows UI to display the table
        if hasattr(output, 'to_dict'):
            state["insight_data"] = {
                "type": "dataframe",
                "data": output.to_dict('records'),
                "columns": list(output.columns),
                "shape": output.shape
            }
        else:
            state["insight_data"] = {
                "type": "value",
                "data": output
            }
        
        # Add to sources
        sources = state.get("sources", [])
        sources.append("insight_tool")
        state["sources"] = sources
        
        logger.info("Insight generated successfully")
        
        return state
        
    except Exception as e:
        logger.error(f"Error in insight node: {e}", exc_info=True)
        state["error"] = f"Insight generation failed: {str(e)}"
        return state


def summarize_insight(query: str, output: any) -> str:
    """
    Summarize pandas output into natural language.
    
    Args:
        query: Original user query
        output: Pandas analysis output
        
    Returns:
        Natural language summary
    """
    try:
        # Format output for LLM
        if hasattr(output, 'to_string'):
            output_str = output.to_string()
        else:
            output_str = str(output)
        
        # Limit output length
        if len(output_str) > 1000:
            output_str = output_str[:1000] + "..."
        
        # Format prompt
        system_prompt = PROMPTS["summarizer"].format(
            query=query,
            output=output_str
        )
        
        # Initialize LLM
        llm = ChatOpenAI(
            model=os.getenv("OPENAI_MODEL", "gpt-4o"),
            temperature=0.3,
            api_key=os.getenv("OPENAI_API_KEY")
        )
        
        # Generate summary
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content="Summarize this result clearly and concisely.")
        ])
        
        summary = response.content
        
        logger.info(f"Generated summary ({len(summary)} chars)")
        
        return summary
        
    except Exception as e:
        logger.error(f"Error summarizing insight: {e}")
        # Fallback to raw output
        return f"Analysis result: {output}"

