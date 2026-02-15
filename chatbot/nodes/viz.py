"""Visualization node for chart generation."""

import logging
from typing import Dict, Optional, Any
import pandas as pd
from langfuse import observe

from observability.langfuse_client import update_trace_context

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


def _get_chart_reason(chart_name: str, config: Dict) -> str:
    """Return a one-line reason for the chart type choice (template-based)."""
    x_col = config.get("x_col", "")
    y_col = config.get("y_col", "")
    if chart_name == "bar_chart":
        if x_col and y_col:
            return f"Bar chart to compare {y_col} by {x_col}."
        if x_col:
            return f"Bar chart to compare categories by {x_col}."
        return "Bar chart to compare categories."
    if chart_name == "line_chart":
        return f"Line chart to show trend over {x_col}" + (f" for {y_col}." if y_col else ".")
    if chart_name == "scatter_chart":
        return f"Scatter chart to show relationship between {x_col} and {y_col}." if (x_col and y_col) else "Scatter chart to show relationship between two numeric variables."
    if chart_name == "histogram":
        col = config.get("column") or x_col or "values"
        return f"Histogram to show distribution of {col}."
    if chart_name == "combo_chart":
        return "Combo chart to show multiple series together."
    if chart_name == "dashboard":
        return "Dashboard view with multiple charts."
    return "Chart to visualize the data."


@observe(name="chatbot_viz", as_type="chain")
def viz_node(state: Dict) -> Dict:
    """
    Execute visualization tools and store chart configuration.
    
    Note: Stores config only (not figure) since figures aren't serializable.
    """
    try:
        update_trace_context(session_id=state.get("session_id"), metadata={"node": "viz"})
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
        state["viz_error"] = None

        # One-line reason for chart type (template-based for low latency)
        chart_reason = _get_chart_reason(chart_name, viz_config)
        state["chart_reason"] = chart_reason

        # Try to generate chart to detect failures (e.g. too many categories); we don't store the figure
        try:
            from ..utils.session_loader import SessionLoader
            from data_visualization.visualization import generate_chart
            loader = SessionLoader()
            dfs = loader.load_session_dataframes(session_id)
            table_name = viz_config.get("table_name") or (list(dfs.keys())[0] if dfs else None)
            if table_name and table_name in dfs:
                df = dfs[table_name]
                chart_type = (chart_name.replace("_chart", "") if chart_name != "histogram" else "histogram")
                generate_chart(
                    df=df,
                    chart_type=chart_type,
                    x_col=viz_config.get("x_col"),
                    y_col=viz_config.get("y_col"),
                    agg_func=viz_config.get("agg_func", "none"),
                    color_col=viz_config.get("color_col")
                )
        except Exception as viz_err:
            err_msg = str(viz_err)
            state["viz_error"] = "Too many categories or invalid chart data." if "categories" in err_msg.lower() or "unique" in err_msg.lower() else err_msg[:200]
            # Fallback: top 10 table for the same x/y/agg if possible
            try:
                from ..utils.session_loader import SessionLoader
                loader = SessionLoader()
                dfs = loader.load_session_dataframes(session_id)
                tname = viz_config.get("table_name") or (list(dfs.keys())[0] if dfs else None)
                x_col = viz_config.get("x_col")
                y_col = viz_config.get("y_col")
                agg_func = viz_config.get("agg_func") or "count"
                if tname and tname in dfs and x_col and x_col in dfs[tname].columns:
                    df = dfs[tname]
                    if y_col and y_col in df.columns and agg_func != "none":
                        fallback_df = df.groupby(x_col)[y_col].agg(agg_func).head(10).reset_index()
                    else:
                        fallback_df = df.groupby(x_col).size().head(10).reset_index(name="count")
                    state["insight_data"] = {
                        "type": "dataframe",
                        "data": fallback_df.to_dict("records"),
                        "columns": list(fallback_df.columns),
                        "shape": fallback_df.shape
                    }
            except Exception:
                pass
        
        # Add to sources
        sources = state.get("sources", [])
        sources.append(chart_name)
        state["sources"] = sources
        
        logger.info(f"Stored config for {chart_name}: {viz_config}")
        
        return state
        
    except Exception as e:
        logger.error(f"Error in viz node: {e}", exc_info=True)
        state["viz_error"] = str(e)[:200]
        return state


# Note: Chart generation moved to streamlit_ui.py to avoid serialization issues
# Charts are generated fresh from config when displaying in UI

