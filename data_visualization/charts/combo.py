"""
Combo chart entrypoint kept for backward compatibility.

`core.chart_generator` imports `generate_combo_chart` from `data_visualization.charts.combo`.
The implementation lives in `data_visualization.chart_compositions`.
"""

from __future__ import annotations

from ..chart_compositions import generate_combo_chart

__all__ = ["generate_combo_chart"]
