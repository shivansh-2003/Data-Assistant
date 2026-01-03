"""Response formatter for chatbot with visualization support."""

import logging
from typing import Dict, Optional, Any, List

from data_visualization.visualization import generate_chart

logger = logging.getLogger(__name__)


def format_response(
    agent_response: str,
    viz_config: Optional[Dict[str, Any]],
    session_id: str
) -> Dict[str, Any]:
    """
    Format complete response with visualization if needed.
    
    Args:
        agent_response: Text response from agent
        viz_config: Visualization configuration dictionary (from extract_chart_parameters)
        session_id: Session ID
        
    Returns:
        Formatted response dictionary:
        {
            "text_response": str,
            "visualization": {
                "needed": bool,
                "chart_figure": Optional[Any],  # Plotly figure object
                "chart_type": Optional[str]
            },
            "data_snippets": List[Dict],
            "tools_used": List[str]
        }
    """
    response = {
        "text_response": agent_response,
        "visualization": {
            "needed": viz_config is not None,
            "chart_figure": None,
            "chart_type": None
        },
        "data_snippets": [],
        "tools_used": []
    }
    
    # Generate chart if visualization is needed
    if viz_config:
        try:
            chart_figure = generate_chart_if_needed(viz_config, session_id)
            response["visualization"]["chart_figure"] = chart_figure
            response["visualization"]["chart_type"] = viz_config.get("chart_type")
        except Exception as e:
            logger.error(f"Error generating chart: {e}")
            response["visualization"]["needed"] = False
            response["text_response"] += f"\n\n(Note: Could not generate visualization: {str(e)})"
    
    # Extract data snippets from response (simple implementation)
    # Could be enhanced to parse tables/statistics from agent response
    data_snippets = extract_data_snippets(agent_response)
    response["data_snippets"] = data_snippets
    
    return response


def generate_chart_if_needed(
    viz_config: Dict[str, Any],
    session_id: str,
    table_name: Optional[str] = None
) -> Optional[Any]:
    """
    Generate Plotly chart based on visualization configuration.
    
    Args:
        viz_config: Chart configuration dictionary with:
            - chart_type: str
            - x_col: Optional[str]
            - y_col: Optional[str]
            - agg_func: str
            - color_col: Optional[str]
            - table_name: str
        session_id: Session ID
        table_name: Optional table name override
        
    Returns:
        Plotly figure or None if generation fails
    """
    try:
        # Get table name from config or parameter
        table_name = table_name or viz_config.get("table_name")
        if not table_name:
            logger.warning("No table name provided for chart generation")
            return None
        
        # Load DataFrame from session
        from .session_loader import load_session_dataframes
        dfs = load_session_dataframes(session_id)
        
        if table_name not in dfs:
            logger.warning(f"Table '{table_name}' not found in session")
            return None
        
        df = dfs[table_name]
        
        # Extract chart parameters
        chart_type = viz_config.get("chart_type", "bar")
        x_col = viz_config.get("x_col")
        y_col = viz_config.get("y_col")
        agg_func = viz_config.get("agg_func", "none")
        color_col = viz_config.get("color_col")
        
        # Generate chart using visualization module
        chart_figure = generate_chart(
            df=df,
            chart_type=chart_type,
            x_col=x_col,
            y_col=y_col,
            agg_func=agg_func,
            color_col=color_col
        )
        
        logger.info(f"Generated {chart_type} chart for session {session_id}")
        return chart_figure
        
    except Exception as e:
        logger.error(f"Error generating chart: {e}", exc_info=True)
        return None


def extract_data_snippets(agent_response: str) -> List[Dict[str, Any]]:
    """
    Extract data snippets (tables, statistics) from agent response.
    
    Args:
        agent_response: Text response from agent
        
    Returns:
        List of data snippet dictionaries:
        [
            {
                "type": "table" | "statistic",
                "data": Any,
                "label": str
            }
        ]
    """
    snippets = []
    
    # Simple implementation - could be enhanced to parse structured data
    # from agent response (e.g., tables, statistics)
    
    # Check for numeric values that might be statistics
    import re
    stat_pattern = r'(\d+\.?\d*)\s*(?:is|was|are|were|equals?|=\s*)(\d+\.?\d*)'
    matches = re.findall(stat_pattern, agent_response)
    
    # For now, return empty list
    # In a full implementation, you might parse tables or statistics
    # from the agent's response format
    
    return snippets

