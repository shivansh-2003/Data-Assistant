"""LLM-based pandas code generation."""

import logging
from langchain_core.messages import SystemMessage, HumanMessage
from typing import Dict, Any

from ..llm_registry import get_code_gen_llm
from ..prompts import get_code_generator_prompt

logger = logging.getLogger(__name__)


def generate_pandas_code(query: str, schema: Dict[str, Any], df_names: list) -> str:
    """
    Generate pandas code using LLM to answer the query.
    
    Args:
        query: User query
        schema: DataFrame schema information
        df_names: List of available DataFrame names
        
    Returns:
        Executable pandas code string
    """
    try:
        # Format prompt using modular prompt function
        system_prompt = get_code_generator_prompt(
            df_names=df_names,
            schema=schema,
            query=query
        )
        
        # Initialize LLM
        llm = get_code_gen_llm()

        # Generate code
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Generate pandas code for: {query}")
        ])
        
        code = response.content
        
        # Clean up code (remove markdown formatting if present)
        if "```python" in code:
            code = code.split("```python")[1].split("```")[0].strip()
        elif "```" in code:
            code = code.split("```")[1].split("```")[0].strip()
        
        logger.info(f"Generated pandas code ({len(code)} chars)")
        logger.debug(f"Code: {code}")
        
        return code
        
    except Exception as e:
        logger.error(f"Error generating pandas code: {e}", exc_info=True)
        raise

