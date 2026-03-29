"""
Dashboard grid rendering. The main grid loop lives in ``dashboard_builder.DashboardBuilder.render_tab``
so pinned-chart configs stay compatible; this module holds layout preset helpers for future use.
"""

from __future__ import annotations

from typing import List, Tuple

from ..config import DASHBOARD_LAYOUT_PRESETS


def preset_to_rows_cols(preset_id: str) -> Tuple[int, int]:
    """Map a preset id to (rows, cols) for equal cell grids (fallback)."""
    if preset_id == "focus":
        return 2, 2
    if preset_id == "compare":
        return 2, 2
    if preset_id == "overview":
        return 2, 3
    return 2, 2


def iter_layout_slots(preset_id: str) -> List[List[int]]:
    """Return row definitions as column weight lists (for st.columns)."""
    return DASHBOARD_LAYOUT_PRESETS.get(preset_id, DASHBOARD_LAYOUT_PRESETS["classic_2x2"])
