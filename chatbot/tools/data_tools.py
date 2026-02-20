"""Data analysis tools following LangChain's @tool pattern.

These tools are callable by the LLM via function calling:
https://docs.langchain.com/oss/python/langchain/tools

The analyzer node binds these tools to the LLM, which selects which tools to call.
Tool execution happens in specialized nodes (insight_node, viz_node) rather than
LangChain's ToolNode, allowing domain-specific execution logic.
"""

from langchain_core.tools import tool


@tool
def insight_tool(query: str) -> dict:
    """
    Generate pandas code to analyze data and answer questions.
    
    This tool is selected by the LLM when the user asks data analysis questions.
    The tool itself returns a config dict; actual execution (code generation + run)
    happens in chatbot/nodes/insight.py.
    
    Use this tool for:
    - Statistical analysis (mean, median, sum, count, describe)
    - Data filtering and selection
    - Grouping and aggregation
    - Correlation analysis
    - Data quality checks
    
    Args:
        query: The analysis question to answer
        
    Returns:
        Dict with tool identifier and query (execution happens in insight_node)
    """
    # Tool returns config; actual execution happens in insight_node
    # This follows LangChain's tool pattern but with custom execution
    return {"tool": "insight_tool", "query": query}

