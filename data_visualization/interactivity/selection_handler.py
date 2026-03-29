"""Map Plotly st.plotly_chart selection events to filter values."""

from __future__ import annotations

from typing import Any, List, Optional, Tuple


def selection_to_filter_values(
    selection: Any,
    x_col: Optional[str],
) -> Tuple[Optional[str], List[Any]]:
    """
    Extract column + values from Streamlit Plotly selection payload.
    Falls back to point x-values when column is known.
    """
    if not selection:
        return None, []
    points = []
    if isinstance(selection, dict):
        points = selection.get("points") or []
    else:
        points = getattr(selection, "points", None) or []
    if not points:
        return None, []
    values: List[Any] = []
    for p in points:
        if isinstance(p, dict):
            if "x" in p and p["x"] is not None:
                values.append(p["x"])
            elif "label" in p:
                values.append(p["label"])
        else:
            x = getattr(p, "x", None)
            if x is not None:
                values.append(x)
    # dedupe preserve order
    seen = set()
    out: List[Any] = []
    for v in values:
        key = repr(v)
        if key not in seen:
            seen.add(key)
            out.append(v)
    col = x_col if x_col and x_col != "None" else None
    return col, out
