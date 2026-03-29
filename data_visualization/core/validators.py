"""Column presence and dtype helpers."""

from __future__ import annotations

from typing import Optional

import pandas as pd


def column_or_none(df: pd.DataFrame, col: Optional[str]) -> Optional[str]:
    if not col or col == "None" or col not in df.columns:
        return None
    return col


def is_datetime_series(s: pd.Series) -> bool:
    return pd.api.types.is_datetime64_any_dtype(s)


def unique_count(s: pd.Series) -> int:
    return int(s.nunique(dropna=True))
