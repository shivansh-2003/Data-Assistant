"""Smart row sampling for large DataFrames before Plotly render."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

import pandas as pd

from ..config import MAX_ROWS_FULL_RENDER, SAMPLE_ROWS


@dataclass
class SamplingMeta:
    sampled: bool
    original_rows: int
    shown_rows: int
    strategy: str


def maybe_sample(df: pd.DataFrame, chart_type: str) -> Tuple[pd.DataFrame, SamplingMeta]:
    """
    If df has more than MAX_ROWS_FULL_RENDER rows, sample down for heavy chart types.
    Bar/line/area rely on aggregation upstream when possible.
    """
    n = len(df)
    if n <= MAX_ROWS_FULL_RENDER:
        return df, SamplingMeta(False, n, n, "none")

    strategy = "random"
    if chart_type in ("line",):
        step = max(1, n // SAMPLE_ROWS)
        out = df.iloc[::step].copy()
        strategy = f"every_{step}th"
    elif chart_type in ("scatter",):
        out = df.sample(n=min(SAMPLE_ROWS, n), random_state=42)
        strategy = "random"
    elif chart_type in ("bar", "histogram", "pie", "box", "violin"):
        # categorical / aggregated views — still cap width
        out = df.sample(n=min(SAMPLE_ROWS, n), random_state=42)
        strategy = "random"
    else:
        out = df.sample(n=min(SAMPLE_ROWS, n), random_state=42)

    return out, SamplingMeta(True, n, len(out), strategy)
