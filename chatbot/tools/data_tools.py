"""Data analysis tools."""

from langchain_core.tools import tool


@tool
def insight_tool(query: str) -> dict:
    """
    Generate pandas code to analyze data and answer questions.
    
    Use this tool for:
    - Statistical analysis (mean, median, sum, count, describe)
    - Data filtering and selection
    - Grouping and aggregation
    - Correlation analysis
    - Data quality checks
    
    Args:
        query: The analysis question to answer
        
    Returns:
        Dict with analysis results
    """
    # This is a placeholder - actual execution happens in insight_node
    return {"tool": "insight_tool", "query": query}

