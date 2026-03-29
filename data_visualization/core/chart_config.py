"""
First-class chart configuration: serialization, hashing, cache keys.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


def _norm_col(c: Optional[str]) -> Optional[str]:
    if c is None or c == "None" or c == "":
        return None
    return c


@dataclass
class ChartConfig:
    """Serializable chart configuration used across controls, cache, and dashboard pin."""

    chart_mode: str = "basic"  # basic | combo
    chart_type: str = "bar"
    x_col: Optional[str] = None
    y_col: Optional[str] = None
    color_col: Optional[str] = None
    agg_func: str = "none"
    heatmap_columns: Optional[List[str]] = None
    color_palette: Optional[List[str]] = None
    title_override: Optional[str] = None
    # Hierarchical / flow / geo / animated
    path_cols: Optional[List[str]] = None
    sankey_source: Optional[str] = None
    sankey_target: Optional[str] = None
    sankey_value: Optional[str] = None
    geo_col: Optional[str] = None
    geo_scope: str = "world"
    lat_col: Optional[str] = None
    lon_col: Optional[str] = None
    animation_col: Optional[str] = None
    show_trendline: bool = False
    # Combo chart (dual axis)
    y2_col: Optional[str] = None
    chart1_type: str = "bar"
    chart2_type: str = "line"
    # Cross-filter state for cache differentiation (JSON-serializable dict)
    cross_filter_state: Optional[Dict[str, Any]] = None

    def normalized(self) -> "ChartConfig":
        return ChartConfig(
            chart_mode=self.chart_mode or "basic",
            chart_type=self.chart_type,
            x_col=_norm_col(self.x_col),
            y_col=_norm_col(self.y_col),
            color_col=_norm_col(self.color_col),
            agg_func=self.agg_func or "none",
            heatmap_columns=list(self.heatmap_columns) if self.heatmap_columns else None,
            color_palette=list(self.color_palette) if self.color_palette else None,
            title_override=self.title_override,
            path_cols=list(self.path_cols) if self.path_cols else None,
            sankey_source=_norm_col(self.sankey_source),
            sankey_target=_norm_col(self.sankey_target),
            sankey_value=_norm_col(self.sankey_value),
            geo_col=_norm_col(self.geo_col),
            geo_scope=self.geo_scope or "world",
            lat_col=_norm_col(self.lat_col),
            lon_col=_norm_col(self.lon_col),
            animation_col=_norm_col(self.animation_col),
            show_trendline=self.show_trendline,
            y2_col=_norm_col(self.y2_col),
            chart1_type=self.chart1_type or "bar",
            chart2_type=self.chart2_type or "line",
            cross_filter_state=dict(self.cross_filter_state) if self.cross_filter_state else None,
        )

    def cache_key_tuple(self) -> tuple:
        """Stable tuple for figure memoization / hashing."""
        c = self.normalized()
        return (
            c.chart_mode,
            c.chart_type,
            c.x_col,
            c.y_col,
            c.color_col,
            c.agg_func,
            tuple(c.heatmap_columns or ()),
            tuple(c.color_palette or ()),
            c.title_override,
            tuple(c.path_cols or ()),
            c.sankey_source,
            c.sankey_target,
            c.sankey_value,
            c.geo_col,
            c.geo_scope,
            c.lat_col,
            c.lon_col,
            c.animation_col,
            c.show_trendline,
            c.y2_col,
            c.chart1_type,
            c.chart2_type,
            str(sorted((c.cross_filter_state or {}).items())) if c.cross_filter_state else "",
        )

    def __hash__(self) -> int:
        return hash(self.cache_key_tuple())

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self.normalized())
        return {k: v for k, v in d.items() if v is not None or k in ("chart_type", "agg_func", "show_trendline", "geo_scope")}

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ChartConfig":
        if not d:
            return cls()
        return cls(
            chart_mode=d.get("chart_mode", d.get("mode", "basic")),
            chart_type=d.get("chart_type", "bar"),
            x_col=d.get("x_col"),
            y_col=d.get("y_col"),
            color_col=d.get("color_col"),
            agg_func=d.get("agg_func", "none"),
            heatmap_columns=d.get("heatmap_columns"),
            color_palette=d.get("color_palette"),
            title_override=d.get("title_override"),
            path_cols=d.get("path_cols"),
            sankey_source=d.get("sankey_source"),
            sankey_target=d.get("sankey_target"),
            sankey_value=d.get("sankey_value"),
            geo_col=d.get("geo_col"),
            geo_scope=d.get("geo_scope", "world"),
            lat_col=d.get("lat_col"),
            lon_col=d.get("lon_col"),
            animation_col=d.get("animation_col"),
            show_trendline=bool(d.get("show_trendline", False)),
            y2_col=d.get("y2_col"),
            chart1_type=d.get("chart1_type", "bar"),
            chart2_type=d.get("chart2_type", "line"),
            cross_filter_state=d.get("cross_filter_state"),
        )

    @classmethod
    def from_dashboard_config(cls, config: Dict[str, Any]) -> "ChartConfig":
        """Build from legacy dashboard pin dict (mode + keys)."""
        mode = config.get("mode", "basic")
        if mode == "combo":
            return cls(
                chart_mode="combo",
                chart_type=config.get("chart_type", "bar"),
                x_col=config.get("x_col"),
                y_col=config.get("y_col"),
                y2_col=config.get("y2_col"),
                color_col=config.get("color_col"),
                agg_func=config.get("agg_func", "none"),
                chart1_type=config.get("chart1_type", "bar"),
                chart2_type=config.get("chart2_type", "line"),
                title_override=config.get("title_override"),
            )
        return cls(
            chart_mode="basic",
            chart_type=config.get("chart_type", "bar"),
            x_col=config.get("x_col"),
            y_col=config.get("y_col"),
            color_col=config.get("color_col"),
            agg_func=config.get("agg_func", "none"),
            heatmap_columns=config.get("heatmap_columns"),
            title_override=config.get("title_override"),
            path_cols=config.get("path_cols"),
            sankey_source=config.get("sankey_source"),
            sankey_target=config.get("sankey_target"),
            sankey_value=config.get("sankey_value"),
            geo_col=config.get("geo_col"),
            animation_col=config.get("animation_col"),
            show_trendline=config.get("show_trendline", False),
        )
