"""Sankey diagrams."""

from __future__ import annotations

import plotly.graph_objects as go
import pandas as pd

from ..core.chart_config import ChartConfig
from ..core.validators import column_or_none
from ..utils import create_error_figure


def generate_sankey(df: pd.DataFrame, config: ChartConfig) -> go.Figure:
    src = column_or_none(df, config.sankey_source)
    tgt = column_or_none(df, config.sankey_target)
    val = column_or_none(df, config.sankey_value)
    if not src or not tgt:
        return create_error_figure("Sankey requires Source and Target columns (More Options).")
    if val and val in df.columns:
        agg = df.groupby([src, tgt], dropna=False)[val].sum().reset_index()
    else:
        agg = df.groupby([src, tgt], dropna=False).size().reset_index(name="value")
        val = "value"
    labels = pd.unique(pd.concat([agg[src], agg[tgt]], ignore_index=True))
    lab_map = {lab: i for i, lab in enumerate(labels)}
    source_idx = agg[src].map(lab_map)
    target_idx = agg[tgt].map(lab_map)
    values = agg[val] if val in agg.columns else agg["value"]

    fig = go.Figure(
        data=[
            go.Sankey(
                node=dict(label=list(labels)),
                link=dict(
                    source=source_idx.tolist(),
                    target=target_idx.tolist(),
                    value=values.tolist(),
                ),
            )
        ]
    )
    fig.update_layout(title_text=config.title_override or "Sankey", font=dict(size=12))
    return fig
