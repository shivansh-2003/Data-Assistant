"""Chart family registry."""

from __future__ import annotations

from typing import Callable, Dict

import plotly.graph_objects as go
import pandas as pd

from ..core.chart_config import ChartConfig
from .animated import generate_animated
from .basic import generate_area, generate_bar, generate_line, generate_scatter
from .categorical import generate_funnel, generate_pie, generate_sunburst, generate_treemap
from .distribution import generate_box, generate_histogram, generate_violin
from .flow import generate_sankey
from .geo import generate_choropleth, generate_scatter_geo
from .heatmap import generate_heatmap

# type: (pd.DataFrame, ChartConfig) -> go.Figure
ChartFn = Callable[[pd.DataFrame, ChartConfig], go.Figure]

CHART_REGISTRY: Dict[str, ChartFn] = {
    "bar": generate_bar,
    "line": generate_line,
    "scatter": generate_scatter,
    "area": generate_area,
    "box": generate_box,
    "histogram": generate_histogram,
    "pie": generate_pie,
    "heatmap": generate_heatmap,
    "violin": generate_violin,
    "sunburst": generate_sunburst,
    "treemap": generate_treemap,
    "funnel": generate_funnel,
    "sankey": generate_sankey,
    "choropleth": generate_choropleth,
    "scatter_geo": generate_scatter_geo,
    "animated": generate_animated,
}

__all__ = ["CHART_REGISTRY", "ChartFn"]
