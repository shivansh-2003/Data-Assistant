"""Visualization node for chart generation.

Design notes (for developers):

- **LLM tools (in `chatbot/tools/simple_charts.py` and `complex_charts.py`)**
  only return lightweight, JSON-serializable **chart configuration dicts**
  (e.g. `{\"chart_type\": \"bar\", \"x_col\": ..., \"y_col\": ...}`).
- This node (`viz_node`) is responsible for:
  - Validating those configs against the actual session data.
  - Storing the cleaned config + derived `viz_type` + `chart_reason` in graph
    state (`state[\"viz_config\"]`, `state[\"viz_type\"]`, `state[\"chart_reason\"]`).
- **It does not build Plotly figures.** Figure creation is done in the
  Streamlit layer (`data_visualization/visualization.generate_chart` and
  `chatbot/ui/chart_ui.py`) so:
  - LangGraph checkpoints remain serializable (no Plotly objects in state).
  - All visual theming and layout stay in the UI code.

So the mental model is:

  LLM tool → config dict → `viz_node` validation + state update →
  Streamlit UI turns `viz_config` into an actual Plotly chart.
"""

import logging
from typing import Dict, Optional, Any
import pandas as pd
import json
from langfuse import observe

from observability.langfuse_client import update_trace_context
from ..constants import (
    VIZ_TOOL_NAMES,
    TOOL_BAR_CHART,
    TOOL_LINE_CHART,
    TOOL_SCATTER_CHART,
    TOOL_CORRELATION_MATRIX,
    TOOL_HEATMAP_CHART,
    TOOL_HISTOGRAM,
    TOOL_BOX_CHART,
    TOOL_AREA_CHART,
    TOOL_COMBO_CHART,
    TOOL_DASHBOARD,
)
from ..utils.profile_formatter import is_suitable_for_chart
from ..utils.session_loader import SessionLoader

logger = logging.getLogger(__name__)

# Data-aware validation limits (cardinality)
MAX_BAR_CATEGORIES = 25
MAX_PIE_CATEGORIES = 10


def validate_data_compatibility(
    chart_name: str,
    config: Dict,
    df: pd.DataFrame,
    data_profile: Optional[Dict[str, Any]] = None,
    table_name: str = "current"
) -> Optional[str]:
    """
    Validate that the data supports the requested chart type (cardinality, column types).
    Uses data_profile if available for faster validation.
    Returns an error message if the chart is not suitable; None if valid.
    """
    if df is None or df.empty:
        return "No data available for chart."
    
    # Map chart_name to chart_type for profile_formatter
    chart_type_map = {
        TOOL_BAR_CHART: "bar",
        "pie_chart": "pie",
        TOOL_LINE_CHART: "line",
        TOOL_SCATTER_CHART: "scatter",
        TOOL_HISTOGRAM: "histogram",
        TOOL_BOX_CHART: "box",
        TOOL_AREA_CHART: "area",
    }
    chart_type = chart_type_map.get(chart_name, chart_name)
    
    # Use profile-based validation if available
    if data_profile:
        # Check X column
        x_col = config.get("x_col") or config.get("column")
        if x_col:
            is_suitable, reason = is_suitable_for_chart(data_profile, table_name, x_col, chart_type)
            if not is_suitable:
                return reason
        
        # Check Y column
        y_col = config.get("y_col")
        if y_col:
            is_suitable, reason = is_suitable_for_chart(data_profile, table_name, y_col, chart_type)
            if not is_suitable:
                return reason
    
    # Fallback to direct DataFrame validation (for cases without profile or special cases)
    if chart_name == TOOL_BAR_CHART:
        x_col = config.get("x_col")
        if x_col and x_col in df.columns:
            n_unique = df[x_col].nunique()
            if n_unique > MAX_BAR_CATEGORIES:
                return f"Too many categories for a clear bar chart ({n_unique} distinct). Showing table instead."
        return None
    if chart_name == "pie_chart":
        x_col = config.get("x_col") or config.get("column")
        if x_col and x_col in df.columns:
            n_unique = df[x_col].nunique()
            if n_unique > MAX_PIE_CATEGORIES:
                return f"Too many categories for a clear pie chart ({n_unique} distinct). Showing table instead."
        return None
    if chart_name == TOOL_LINE_CHART:
        x_col = config.get("x_col")
        y_col = config.get("y_col")
        for col, label in [(x_col, "x_col"), (y_col, "y_col")]:
            if col and col in df.columns:
                dtype = df[col].dtype
                if not (pd.api.types.is_numeric_dtype(dtype) or pd.api.types.is_datetime64_any_dtype(dtype)):
                    return f"Line chart expects numeric or date for {label}; '{col}' has type {dtype}. Showing table instead."
        return None
    if chart_name == TOOL_SCATTER_CHART:
        x_col = config.get("x_col")
        y_col = config.get("y_col")
        for col in (x_col, y_col):
            if col and col in df.columns and not pd.api.types.is_numeric_dtype(df[col].dtype):
                return f"Scatter chart expects numeric columns; '{col}' is not numeric. Showing table instead."
        return None
    if chart_name == TOOL_AREA_CHART:
        x_col = config.get("x_col")
        y_col = config.get("y_col")
        if y_col and y_col in df.columns and not pd.api.types.is_numeric_dtype(df[y_col].dtype):
            return f"Area chart expects numeric Y column; '{y_col}' is not numeric. Showing table instead."
        return None
    if chart_name == TOOL_BOX_CHART:
        y_col = config.get("y_col")
        if y_col and y_col in df.columns and not pd.api.types.is_numeric_dtype(df[y_col].dtype):
            return f"Box chart expects numeric Y column; '{y_col}' is not numeric. Showing table instead."
        return None
    if chart_name == TOOL_HEATMAP_CHART:
        columns = config.get("heatmap_columns", [])
        if not columns or len(columns) < 2:
            return "Heatmap requires at least 2 columns. Showing table instead."
        # Check if columns exist
        missing = [c for c in columns if c not in df.columns]
        if missing:
            return f"Heatmap columns not found: {missing}. Showing table instead."
        return None
    if chart_name == TOOL_CORRELATION_MATRIX:
        numeric_cols = list(df.select_dtypes(include=['number']).columns)
        if len(numeric_cols) < 2:
            return "Correlation matrix requires at least 2 numeric columns. Showing table instead."
        return None
    return None


def validate_required_params(chart_name: str, config: Dict) -> Optional[str]:
    """
    Validate that tool args exist (required parameters for the chart type).
    Returns an error message if invalid; None if valid.
    """
    if chart_name == TOOL_BAR_CHART:
        if not config.get("x_col"):
            return "Bar chart requires x_col parameter"
    
    elif chart_name == TOOL_LINE_CHART:
        if not config.get("x_col") or not config.get("y_col"):
            return "Line chart requires both x_col and y_col parameters"
    
    elif chart_name == TOOL_SCATTER_CHART:
        if not config.get("x_col") or not config.get("y_col"):
            return "Scatter chart requires both x_col and y_col parameters"
    
    elif chart_name == TOOL_HISTOGRAM:
        if not config.get("column") and not config.get("x_col"):
            return "Histogram requires column parameter"
    
    elif chart_name == TOOL_AREA_CHART:
        if not config.get("x_col") or not config.get("y_col"):
            return "Area chart requires both x_col and y_col parameters"
    
    elif chart_name == TOOL_BOX_CHART:
        if not config.get("y_col"):
            return "Box chart requires y_col parameter"
    
    elif chart_name == TOOL_HEATMAP_CHART:
        columns = config.get("heatmap_columns", [])
        if not columns or len(columns) < 2:
            return "Heatmap requires at least 2 columns in heatmap_columns"
    
    elif chart_name == TOOL_CORRELATION_MATRIX:
        # No validation needed - auto-selects columns
        pass
    
    return None


def _get_chart_reason(chart_name: str, config: Dict) -> str:
    """Return a one-line reason for the chart type choice (template-based)."""
    x_col = config.get("x_col", "")
    y_col = config.get("y_col", "")
    if chart_name == TOOL_BAR_CHART:
        if x_col and y_col:
            return f"Bar chart to compare {y_col} by {x_col}."
        if x_col:
            return f"Bar chart to compare categories by {x_col}."
        return "Bar chart to compare categories."
    if chart_name == TOOL_LINE_CHART:
        return f"Line chart to show trend over {x_col}" + (f" for {y_col}." if y_col else ".")
    if chart_name == TOOL_SCATTER_CHART:
        return f"Scatter chart to show relationship between {x_col} and {y_col}." if (x_col and y_col) else "Scatter chart to show relationship between two numeric variables."
    if chart_name == TOOL_HISTOGRAM:
        col = config.get("column") or x_col or "values"
        return f"Histogram to show distribution of {col}."
    if chart_name == TOOL_AREA_CHART:
        return f"Area chart to show cumulative values over {x_col}" + (f" for {y_col}." if y_col else ".")
    if chart_name == TOOL_BOX_CHART:
        return f"Box plot to show distribution of {y_col}" + (f" by {x_col}." if x_col else ".")
    if chart_name == TOOL_HEATMAP_CHART:
        cols = config.get("heatmap_columns", [])
        return f"Heatmap to show relationships between {len(cols)} columns."
    if chart_name == TOOL_CORRELATION_MATRIX:
        return "Correlation matrix to show relationships between all numeric columns."
    if chart_name == TOOL_COMBO_CHART:
        return "Combo chart to show multiple series together."
    if chart_name == TOOL_DASHBOARD:
        return "Dashboard view with multiple charts."
    return "Chart to visualize the data."


@observe(name="chatbot_viz", as_type="chain")
def viz_node(state: Dict) -> Dict:
    """
    Execute visualization tools (bar_chart, line_chart, etc.) and store chart configuration.
    
    This node executes chart tools that were selected by the analyzer node.
    Unlike LangChain's ToolNode (which auto-executes any tool), this node provides
    specialized execution logic for visualization:
    
    Process:
    1. Extract chart tool calls from state["tool_calls"] (e.g., bar_chart, line_chart)
    2. Validate tool parameters against schema and data profile
    3. Store chart configuration in state["viz_config"] (JSON-serializable dict)
    4. Note: Actual Plotly figures are generated later in Streamlit UI layer
    
    The tools return config dicts (not Plotly figures) to keep LangGraph state serializable.
    See: chatbot/tools/simple_charts.py for tool definitions.
    """
    try:
        update_trace_context(session_id=state.get("session_id"), metadata={"node": "viz"})
        tool_calls = state.get("tool_calls", [])
        
        # Find viz tool calls (single source: constants.VIZ_TOOL_NAMES)
        viz_calls = [tc for tc in tool_calls if tc.get("name") in VIZ_TOOL_NAMES]
        
        if not viz_calls:
            return state
        
        session_id = state.get("session_id")
        if not session_id:
            logger.warning("No session_id in state for visualization")
            return state

        # Load session data once for validation and fallback
        dfs = SessionLoader().load_session_dataframes(session_id)

        # Process first viz call (can extend to handle multiple)
        viz_call = viz_calls[0]
        viz_config = viz_call.get("args", {})
        chart_name = viz_call.get("name", "unknown")
        table_name = viz_config.get("table_name") or (list(dfs.keys())[0] if dfs else None)
        df = dfs.get(table_name) if table_name else None

        # Normalize heatmap_chart args: tool takes "columns" but config needs "heatmap_columns"
        if chart_name == TOOL_HEATMAP_CHART:
            if "columns" in viz_config and "heatmap_columns" not in viz_config:
                viz_config["heatmap_columns"] = viz_config.pop("columns")

        # Normalize histogram args: tool takes "column" but generate_chart expects "x_col"
        if chart_name == TOOL_HISTOGRAM:
            if viz_config.get("column") and not viz_config.get("x_col"):
                viz_config["x_col"] = viz_config.get("column")

        # Handle correlation_matrix: auto-select numeric columns before validation
        if chart_name == TOOL_CORRELATION_MATRIX and df is not None and not df.empty:
            numeric_cols = list(df.select_dtypes(include=["number"]).columns)
            if len(numeric_cols) >= 2:
                viz_config["heatmap_columns"] = numeric_cols
                chart_name = TOOL_HEATMAP_CHART
            else:
                state["viz_error"] = "Correlation matrix requires at least 2 numeric columns."
                return state
        
        # Validate required parameters
        validation_error = validate_required_params(chart_name, viz_config)
        if validation_error:
            logger.warning(f"Invalid viz config: {validation_error}. Skipping visualization but continuing with insights.")
            # Don't set error - just skip viz, insights should still be shown
            return state
        
        # Store config (not figure - figures aren't serializable)
        # Ensure chart_type is set in config for UI rendering
        if "chart_type" not in viz_config:
            if chart_name in (TOOL_CORRELATION_MATRIX, TOOL_HEATMAP_CHART):
                viz_config["chart_type"] = "heatmap"
            else:
                viz_config["chart_type"] = chart_name.replace("_chart", "")
        state["viz_config"] = viz_config
        # Map chart_name to viz_type (remove _chart suffix, handle special cases)
        if chart_name in (TOOL_CORRELATION_MATRIX, TOOL_HEATMAP_CHART):
            state["viz_type"] = "heatmap"
        elif chart_name == TOOL_HISTOGRAM:
            state["viz_type"] = "histogram"
        elif chart_name == TOOL_BOX_CHART:
            state["viz_type"] = "box"
        elif chart_name == TOOL_AREA_CHART:
            state["viz_type"] = "area"
        else:
            state["viz_type"] = chart_name.replace("_chart", "")
        state["viz_error"] = None

        # One-line reason for chart type (template-based for low latency)
        chart_reason = _get_chart_reason(chart_name, viz_config)
        state["chart_reason"] = chart_reason

        data_profile = state.get("data_profile")

        # Data-aware validation: cardinality and column types before calling generate_chart
        if df is not None and not df.empty:
            data_error = validate_data_compatibility(chart_name, viz_config, df, data_profile, table_name)
            if data_error:
                state["viz_error"] = data_error
                sources = state.get("sources", [])
                sources.append(chart_name)
                state["sources"] = sources
                logger.info(f"Viz skipped (data validation): {data_error}")
                return state

        # Try to generate chart to detect failures (e.g. too many categories); we don't store the figure
        try:
            from data_visualization.visualization import generate_chart
            if table_name and df is not None:
                chart_type = "heatmap" if chart_name in (TOOL_CORRELATION_MATRIX, TOOL_HEATMAP_CHART) else chart_name.replace("_chart", "")
                heatmap_cols = viz_config.get("heatmap_columns")
                if chart_type == "heatmap" and not heatmap_cols and viz_config.get("x_col") and viz_config.get("y_col"):
                    heatmap_cols = [viz_config["x_col"], viz_config["y_col"]]
                generate_chart(
                    df=df,
                    chart_type=chart_type,
                    x_col=viz_config.get("x_col"),
                    y_col=viz_config.get("y_col"),
                    agg_func=viz_config.get("agg_func", "none"),
                    color_col=viz_config.get("color_col"),
                    heatmap_columns=heatmap_cols
                )
        except Exception as viz_err:
            err_msg = str(viz_err)
            state["viz_error"] = "Too many categories or invalid chart data." if "categories" in err_msg.lower() or "unique" in err_msg.lower() else err_msg[:200]
            # Fallback: top 10 table for the same x/y/agg if possible
            try:
                x_col = viz_config.get("x_col")
                y_col = viz_config.get("y_col")
                agg_func = viz_config.get("agg_func") or "count"
                if table_name and table_name in dfs and x_col and x_col in dfs[table_name].columns:
                    _df = dfs[table_name]
                    if y_col and y_col in _df.columns and agg_func != "none":
                        fallback_df = _df.groupby(x_col)[y_col].agg(agg_func).head(10).reset_index()
                    else:
                        fallback_df = _df.groupby(x_col).size().head(10).reset_index(name="count")
                    records = json.loads(fallback_df.to_json(orient="records"))
                    rows, cols = (int(fallback_df.shape[0]), int(fallback_df.shape[1]))
                    state["insight_data"] = {
                        "type": "dataframe",
                        "data": records,
                        "columns": list(fallback_df.columns),
                        "shape": (rows, cols),
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

