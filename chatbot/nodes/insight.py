"""Insight node for pandas analysis and code generation."""

import logging
from typing import Dict, Any
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
import os
from langfuse import observe

from observability.langfuse_client import update_trace_context

from ..prompts import PROMPTS
from ..execution import generate_pandas_code, execute_pandas_code

logger = logging.getLogger(__name__)


def _extract_bad_column(error_msg: str) -> str:
    """Try to extract the column name from a KeyError-style message."""
    import re
    m = re.search(r"['\"]([^'\"]+)['\"]", error_msg)
    return m.group(1) if m else "that column"


@observe(name="chatbot_insight", as_type="chain")
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
        update_trace_context(session_id=state.get("session_id"), metadata={"node": "insight"})
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
        
        # Use effective_query when present (follow-up resolution from router)
        effective_query = state.get("effective_query")
        if effective_query:
            query = effective_query
        # Process first insight call (can extend to handle multiple)
        insight_call = insight_calls[0]
        insight_query = effective_query or insight_call.get("args", {}).get("query", query)

        # Summarize previous result (no code run) when user said "summarize that"
        if state.get("intent") == "summarize_last":
            if state.get("last_insight") or state.get("insight_data"):
                prev = state.get("last_insight") or ""
                if state.get("insight_data") and state["insight_data"].get("type") == "dataframe":
                    import pandas as pd
                    df = pd.DataFrame(state["insight_data"]["data"])
                    prev = df.to_string()[:1500] if not prev else prev
                summary = summarize_insight("Summarize this result clearly in one or two sentences.", prev)
                state["last_insight"] = summary
                state["one_line_insight"] = summary.split(".")[0].strip() + "." if summary else summary
                sources = state.get("sources", [])
                sources.append("insight_tool")
                state["sources"] = sources
                return state
            else:
                state["error"] = "No previous result to summarize. Ask a question about your data first."
                return state
        
        # Generate pandas code
        logger.info(f"Generating pandas code for: {insight_query[:50]}...")
        code = generate_pandas_code(
            query=insight_query,
            schema=schema,
            df_names=list(df_dict.keys())
        )
        
        # Store code in state for "Show code" in UI
        state["generated_code"] = code
        
        # Execute code
        logger.info("Executing pandas code...")
        execution_result = execute_pandas_code(code, df_dict)
        
        if not execution_result["success"]:
            state["error"] = execution_result.get("error", "Analysis failed")
            if execution_result.get("error_type") == "column_not_found" and execution_result.get("suggested_columns"):
                state["error_suggestion"] = {
                    "type": "did_you_mean",
                    "suggested_columns": execution_result["suggested_columns"],
                    "bad_column": _extract_bad_column(execution_result.get("error", ""))
                }
            else:
                state["error_suggestion"] = None
            return state
        
        output = execution_result["output"]
        
        # Summarize output using LLM
        logger.info("Summarizing results...")
        summary = summarize_insight(insight_query, output)
        
        # Store results (first sentence as one-line takeaway for UI consistency)
        state["last_insight"] = summary
        first_sentence = summary.split(".")[0].strip() + "." if summary else summary
        state["one_line_insight"] = first_sentence
        
        # Store output based on type for serialization
        import pandas as pd
        
        if isinstance(output, pd.DataFrame):
            # DataFrame: store as list of records for table display
            state["insight_data"] = {
                "type": "dataframe",
                "data": output.to_dict('records'),
                "columns": list(output.columns),
                "shape": output.shape
            }
        elif isinstance(output, pd.Series):
            # Series: convert to DataFrame first (for aggregations like mean by group)
            df = output.reset_index()
            state["insight_data"] = {
                "type": "dataframe",
                "data": df.to_dict('records'),
                "columns": list(df.columns),
                "shape": df.shape
            }
        else:
            # Single value: store as-is
            state["insight_data"] = {
                "type": "value",
                "data": output
            }
        
        # Add to sources
        sources = state.get("sources", [])
        sources.append("insight_tool")
        state["sources"] = sources
        
        # Update conversation context for follow-up resolution next turn
        state["conversation_context"] = {
            "last_query": insight_query,
            "last_insight_summary": (summary or "")[:400],
        }
        
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

