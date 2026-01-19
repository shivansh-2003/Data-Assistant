"""Finance performance analysis tools."""

from langchain_core.tools import tool


@tool
def trading_performance_analyzer(query: str) -> dict:
    """
    Analyze trading performance queries (P&L, win rate, Sharpe, strategy metrics).

    Returns:
        Dict with tool identifier and query payload
    """
    return {"tool": "trading_performance_analyzer", "query": query}
