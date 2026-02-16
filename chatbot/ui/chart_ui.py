"""Chart generation for InsightBot UI."""

import logging

logger = logging.getLogger(__name__)


def generate_chart_from_config_ui(viz_config: dict, session_id: str):
    """Generate chart from configuration for UI display."""
    try:
        from data_visualization.visualization import generate_chart
        from ..utils.session_loader import SessionLoader

        loader = SessionLoader()
        dfs = loader.load_session_dataframes(session_id)

        table_name = viz_config.get("table_name", "current")
        if table_name not in dfs:
            table_name = list(dfs.keys())[0]

        df = dfs[table_name]

        chart_type = viz_config.get("chart_type", "bar")

        # Handle heatmap with multiple columns
        heatmap_cols = viz_config.get("heatmap_columns")
        if chart_type == "heatmap" and heatmap_cols:
            if heatmap_cols == "auto":
                heatmap_cols = list(df.select_dtypes(include=['number']).columns)

        fig = generate_chart(
            df=df,
            chart_type=chart_type,
            x_col=viz_config.get("x_col"),
            y_col=viz_config.get("y_col"),
            agg_func=viz_config.get("agg_func", "none"),
            color_col=viz_config.get("color_col"),
            heatmap_columns=heatmap_cols
        )

        return fig
    except Exception as e:
        logger.error(f"Error generating chart: {e}")
        return None
