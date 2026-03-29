"""
Visualization Centre constants: chart registry keys, session keys, limits.
"""

# Session state keys (avoid typos across modules)
SESSION_VIZ_TABLE = "viz_table_select"
SESSION_VIZ_CHART_TYPE = "viz_chart_type"
SESSION_CROSS_FILTER = "viz_cross_filters"

# Sampling / performance
MAX_ROWS_FULL_RENDER = 50_000
SAMPLE_ROWS = 50_000

# Chart type keys (must match CHART_REGISTRY in charts/__init__.py)
BASIC_CHART_TYPES = [
    "bar",
    "line",
    "scatter",
    "area",
    "box",
    "histogram",
    "pie",
    "heatmap",
    "violin",
    "sunburst",
    "treemap",
    "funnel",
    "sankey",
    "choropleth",
    "scatter_geo",
    "animated",
]

# Layout presets for dashboard grid_renderer
DASHBOARD_LAYOUT_PRESETS = {
    "focus": [[3], [1, 1]],  # wide top, two bottom
    "compare": [[1, 1], [1, 1]],
    "overview": [[1, 1, 1], [1, 1, 1]],
    "classic_2x2": [[1, 1], [1, 1]],
}
