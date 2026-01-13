"""Visualization node for chart generation."""

import logging
from typing import Dict, Optional
import plotly.graph_objects as go

logger = logging.getLogger(__name__)


def viz_node(state: Dict) -> Dict:
    """
    Execute visualization tools and generate charts.
    
    Uses existing data_visualization module via tool configurations.
    """
    try:
        tool_calls = state.get("tool_calls", [])
        
        # Find viz tool calls
        viz_tools = ["bar_chart", "line_chart", "scatter_chart", "histogram", "combo_chart", "dashboard"]
        viz_calls = [tc for tc in tool_calls if tc.get("name") in viz_tools]
        
        if not viz_calls:
            return state
        
        df_dict = state.get("df_dict", {})
        
        if not df_dict:
            state["error"] = "No data available for visualization"
            return state
        
        # Process first viz call (can extend to handle multiple)
        viz_call = viz_calls[0]
        viz_config = viz_call.get("args", {})
        
        # Generate chart using existing visualization module
        fig = generate_chart_from_config(viz_config, df_dict, state)
        
        if fig is not None:
            state["viz_figure"] = fig
            state["viz_type"] = viz_config.get("chart_type", "unknown")
            
            # Add to sources
            sources = state.get("sources", [])
            sources.append(viz_call.get("name", "viz_tool"))
            state["sources"] = sources
            
            logger.info(f"Generated {viz_config.get('chart_type')} chart")
        
        return state
        
    except Exception as e:
        logger.error(f"Error in viz node: {e}", exc_info=True)
        # Don't set error - viz is optional, continue without chart
        logger.warning(f"Continuing without visualization due to error: {e}")
        return state


def generate_chart_from_config(config: Dict, df_dict: Dict, state: Dict) -> Optional[go.Figure]:
    """
    Generate Plotly figure from tool configuration.
    
    Args:
        config: Chart configuration from tool
        df_dict: Dictionary of DataFrames
        state: Current state
        
    Returns:
        Plotly Figure or None
    """
    try:
        from data_visualization.visualization import generate_chart
        
        # Get table
        table_name = config.get("table_name", "current")
        if table_name not in df_dict:
            # Use first available table
            table_name = list(df_dict.keys())[0]
        
        df = df_dict[table_name]
        
        # Extract parameters
        chart_type = config.get("chart_type", "bar")
        x_col = config.get("x_col")
        y_col = config.get("y_col")
        agg_func = config.get("agg_func", "none")
        color_col = config.get("color_col")
        
        # Generate chart using existing module
        fig = generate_chart(
            df=df,
            chart_type=chart_type,
            x_col=x_col,
            y_col=y_col,
            agg_func=agg_func,
            color_col=color_col
        )
        
        return fig
        
    except Exception as e:
        logger.error(f"Error generating chart: {e}", exc_info=True)
        return None

