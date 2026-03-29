"""Dashboard HTML and JSON export helpers."""

from __future__ import annotations

import json
from typing import Any, Dict, List

import pandas as pd
import plotly.graph_objects as go


def build_dashboard_html(
    figures: List[go.Figure],
    cols: int,
    errors: List[str],
) -> str:
    html_parts: List[str] = []
    html_parts.append(
        """
<!DOCTYPE html>
<html>
<head>
<title>Dashboard Export</title>
<script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
<style>
body { font-family: Arial, sans-serif; margin: 20px; }
.dashboard-grid { display: grid; gap: 20px; margin: 20px 0; }
.chart-container { border: 1px solid #ddd; padding: 10px; border-radius: 5px; }
h2 { color: #333; }
</style>
</head>
<body>
<h1>📊 Dashboard Export</h1>
<p>Generated on """
        + pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
        + """</p>
<div class="dashboard-grid" style="grid-template-columns: repeat("""
        + str(cols)
        + """, 1fr);">
"""
    )
    plotlyjs_included = False
    for chart_idx, fig in enumerate(figures):
        try:
            include_plotlyjs = "cdn" if not plotlyjs_included else False
            chart_html = fig.to_html(full_html=False, include_plotlyjs=include_plotlyjs)
            html_parts.append(f'<div class="chart-container"><h3>Chart {chart_idx + 1}</h3>{chart_html}</div>')
            if not plotlyjs_included:
                plotlyjs_included = True
        except Exception as e:
            html_parts.append(
                f'<div class="chart-container"><p>Error rendering chart {chart_idx + 1}: {str(e)}</p></div>'
            )
    for err in errors:
        html_parts.append(f'<div class="chart-container"><p>{err}</p></div>')
    html_parts.append(
        """
</div>
</body>
</html>
"""
    )
    return "\n".join(html_parts)


def build_dashboard_config_json(
    layout: str,
    selected_table: str,
    charts: List[Dict[str, Any]],
) -> str:
    dashboard_config = {
        "layout": layout,
        "table": selected_table,
        "charts": [{"id": c["id"], "config": c["config"]} for c in charts],
        "exported_at": pd.Timestamp.now().isoformat(),
    }
    return json.dumps(dashboard_config, indent=2)
