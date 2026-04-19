"""Chart generation for InsightBot UI."""

import logging

import streamlit as st

logger = logging.getLogger(__name__)


@st.cache_data(show_spinner=False, ttl=300)
def _load_chart_dataframes(session_id: str) -> dict:
    """Load DataFrames for chart rendering — cached per session for 5 minutes.

    Using ``@st.cache_data`` instead of ``st.session_state`` so the cache
    survives Streamlit reruns without holding a live Python dict reference that
    could be mutated by other code paths. TTL=300 keeps stale frames from
    lingering after a data manipulation.
    """
    from chatbot.utils.session_loader import SessionLoader

    try:
        loader = SessionLoader()
        return loader.load_session_dataframes(session_id)
    except Exception as e:
        logger.error("Failed to load DataFrames for chart rendering: %s", e)
        return {}


def generate_chart_from_config_ui(viz_config: dict, session_id: str):
    """Generate chart from configuration for UI display.

    DataFrames are loaded once per (session_id, TTL window) via Streamlit's
    function cache. Repeat calls inside the same rerun — or across reruns while
    the cache is fresh — skip the Redis round-trip entirely.
    """
    try:
        from data_visualization.visualization import generate_chart

        dfs = _load_chart_dataframes(session_id)
        if not dfs:
            logger.warning("No DataFrames available for chart rendering session=%s", session_id)
            return None

        table_name = viz_config.get("table_name", "current")
        if table_name not in dfs:
            table_name = list(dfs.keys())[0]

        df = dfs[table_name]

        chart_type = viz_config.get("chart_type", "bar")

        heatmap_cols = viz_config.get("heatmap_columns")
        if chart_type == "heatmap" and heatmap_cols:
            if heatmap_cols == "auto":
                heatmap_cols = list(df.select_dtypes(include=["number"]).columns)

        fig = generate_chart(
            df=df,
            chart_type=chart_type,
            x_col=viz_config.get("x_col"),
            y_col=viz_config.get("y_col"),
            agg_func=viz_config.get("agg_func", "none"),
            color_col=viz_config.get("color_col"),
            heatmap_columns=heatmap_cols,
        )

        return fig
    except Exception as e:
        logger.error("Error generating chart: %s", e)
        return None


def invalidate_chart_df_cache(session_id: str) -> None:
    """Force the next chart render to re-fetch DataFrames from Redis.

    Call this after any data manipulation that changes the session's tables.
    """
    _load_chart_dataframes.clear()
