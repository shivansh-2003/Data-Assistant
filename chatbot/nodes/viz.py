"""Visualization node for chart generation."""

import logging
from typing import Dict, Optional, Any
import pandas as pd
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

logger = logging.getLogger(__name__)

# Data-aware validation limits (cardinality)
MAX_BAR_CATEGORIES = 25
MAX_PIE_CATEGORIES = 10


def validate_viz_against_data(
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


def validate_viz_config(chart_name: str, config: Dict) -> Optional[str]:
    """
    Validate visualization configuration has required parameters.
    
    Returns:
        Error message if invalid, None if valid
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
    Execute visualization tools and store chart configuration.
    
    Note: Stores config only (not figure) since figures aren't serializable.
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
        
        # Process first viz call (can extend to handle multiple)
        viz_call = viz_calls[0]
        viz_config = viz_call.get("args", {})
        chart_name = viz_call.get("name", "unknown")
        
        # Handle correlation_matrix special case: auto-select numeric columns before validation
        if chart_name == TOOL_CORRELATION_MATRIX:
            from ..utils.session_loader import SessionLoader
            loader = SessionLoader()
            dfs = loader.load_session_dataframes(session_id)
            table_name = viz_config.get("table_name") or (list(dfs.keys())[0] if dfs else None)
            df = dfs.get(table_name) if table_name else None
            if df is not None and not df.empty:
                numeric_cols = list(df.select_dtypes(include=['number']).columns)
                if len(numeric_cols) >= 2:
                    viz_config["heatmap_columns"] = numeric_cols
                    chart_name = TOOL_HEATMAP_CHART  # Treat as heatmap for downstream processing
                else:
                    state["viz_error"] = "Correlation matrix requires at least 2 numeric columns."
                    return state
        
        # Validate required parameters
        validation_error = validate_viz_config(chart_name, viz_config)
        if validation_error:
            logger.warning(f"Invalid viz config: {validation_error}. Skipping visualization but continuing with insights.")
            # Don't set error - just skip viz, insights should still be shown
            return state
        
        # Store config (not figure - figures aren't serializable)
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

        # Load data for data-aware validation and chart generation
        from ..utils.session_loader import SessionLoader
        loader = SessionLoader()
        dfs = loader.load_session_dataframes(session_id)
        table_name = viz_config.get("table_name") or (list(dfs.keys())[0] if dfs else None)
        df = dfs.get(table_name) if table_name else None
        
        # Get data_profile from state for enhanced validation
        data_profile = state.get("data_profile")

        # Data-aware validation: cardinality and column types before calling generate_chart
        if df is not None and not df.empty:
            data_error = validate_viz_against_data(chart_name, viz_config, df, data_profile, table_name)
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
                chart_type = chart_name.replace("_chart", "")
                if chart_type == "histogram":
                    chart_type = "histogram"
                elif chart_type == "correlation_matrix":
                    chart_type = "heatmap"
                
                # Handle heatmap with multiple columns
                heatmap_cols = None
                if chart_type == "heatmap":
                    heatmap_cols = viz_config.get("heatmap_columns")
                    if not heatmap_cols:
                        # Fallback: use x_col and y_col if available
                        if viz_config.get("x_col") and viz_config.get("y_col"):
                            heatmap_cols = [viz_config.get("x_col"), viz_config.get("y_col")]
                
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

