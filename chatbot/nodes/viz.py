"""Visualization node for chart generation."""

import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


def validate_viz_config(chart_name: str, config: Dict) -> Optional[str]:
    """
    Validate visualization configuration has required parameters.
    
    Returns:
        Error message if invalid, None if valid
    """
    if chart_name == "bar_chart":
        if not config.get("x_col"):
            return "Bar chart requires x_col parameter"
    
    elif chart_name == "line_chart":
        if not config.get("x_col") or not config.get("y_col"):
            return "Line chart requires both x_col and y_col parameters"
    
    elif chart_name == "scatter_chart":
        if not config.get("x_col") or not config.get("y_col"):
            return "Scatter chart requires both x_col and y_col parameters"
    
    elif chart_name == "histogram":
        if not config.get("column") and not config.get("x_col"):
            return "Histogram requires column parameter"
    
    return None


def viz_node(state: Dict) -> Dict:
    """
    Execute visualization tools and store chart configuration.
    
    Note: Stores config only (not figure) since figures aren't serializable.
    """
    try:
        tool_calls = state.get("tool_calls", [])
        
        # Find viz tool calls
        viz_tools = ["bar_chart", "line_chart", "scatter_chart", "histogram", "combo_chart", "dashboard"]
        viz_calls = [tc for tc in tool_calls if tc.get("name") in viz_tools]
        
        if not viz_calls:
            return state
        
        session_id = state.get("session_id")
        if not session_id:
            logger.warning("No session_id in state for visualization")
            return state
        
        # Process first viz call (can extend to handle multiple)
        viz_call = viz_calls[0]
        viz_config = viz_call.get("args", {})
        chart_name = viz_call.get("name", "unknown")
        
        # Validate required parameters
        validation_error = validate_viz_config(chart_name, viz_config)
        if validation_error:
            logger.warning(f"Invalid viz config: {validation_error}. Skipping visualization but continuing with insights.")
            # Don't set error - just skip viz, insights should still be shown
            return state
        
        # Store config (not figure - figures aren't serializable)
        state["viz_config"] = viz_config
        state["viz_type"] = chart_name.replace("_chart", "")
        
        # Add to sources
        sources = state.get("sources", [])
        sources.append(chart_name)
        state["sources"] = sources
        
        logger.info(f"Stored config for {chart_name}: {viz_config}")
        
        return state
        
    except Exception as e:
        logger.error(f"Error in viz node: {e}", exc_info=True)
        # Don't set error - viz is optional, continue without chart
        logger.warning(f"Continuing without visualization due to error: {e}")
        return state


# Note: Chart generation moved to streamlit_ui.py to avoid serialization issues
# Charts are generated fresh from config when displaying in UI

