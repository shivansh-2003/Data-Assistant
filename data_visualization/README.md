# Data Visualization (`data_visualization`)

Modular **Visualization Centre** for the Data Assistant Platform: session-backed Plotly charts, a typed **chart registry**, serializable **`ChartConfig`**, cross-filtering, theming, and a **dashboard builder** integrated with the Streamlit UI (`app.py`).

## Overview

| Layer | Role |
|--------|------|
| **`visualization.py`** | Thin orchestrator: loads session tables from the FastAPI API, injects CSS, wires `ui` controls, main chart, export, metrics, filter bar, and `DashboardBuilder`. |
| **`core/`** | `ChartConfig`, `generate_chart` / `generate_from_config`, dataframe loading, aggregation, validation, sampling. |
| **`charts/`** | `CHART_REGISTRY` mapping chart type strings → `(DataFrame, ChartConfig) → Figure` builders; combo charts in `charts/combo.py`. |
| **`theme/`** | Plotly template application, palettes, layout helpers, optional CSS (`theme/css.py`). |
| **`ui/`** | Streamlit controls, chart display, cross-filter bar, export panel, toolbar, metrics, data preview, empty states. |
| **`dashboard/`** | Grid helpers, chart cards, export bits used by the builder. |
| **`interactivity/`** | Cross-filter application and selection handling layered on the dataframe before charting. |
| **`config.py`** | Session state key names, sampling caps (`MAX_ROWS_FULL_RENDER`, `SAMPLE_ROWS`), `BASIC_CHART_TYPES`, `DASHBOARD_LAYOUT_PRESETS`. |

**Upstream data**: Tables come from **`GET {FASTAPI_URL}/api/session/{session_id}/tables`** (summary format). Default **`FASTAPI_URL`** is `https://data-assistant-hj5f.onrender.com` (override with `.env` for local API).

## Public API (`__init__.py`)

```python
from data_visualization import (
    render_visualization_tab,
    get_dataframe_from_session,
    generate_chart,
    generate_from_config,
    ChartRecommendation,
    get_chart_recommendations,
    generate_combo_chart,  # backward compatibility
    DashboardBuilder,
)
```

- **`render_visualization_tab()`** — Streamlit entry: full Visualization Centre tab.
- **`get_dataframe_from_session(session_id, table_name)`** — Builds a `DataFrame` from the API summary preview (`@st.cache_data`).
- **`generate_chart(df, chart_type, x_col, y_col, ...)`** — Builds a `ChartConfig` internally and returns a themed `plotly.graph_objects.Figure` (backward-compatible kwargs forwarded into `ChartConfig`).
- **`generate_from_config(df, config)`** — Preferred path: `ChartConfig` → cross-filter → aggregate → sample → registry → theme.

## Chart pipeline (`generate_from_config`)

1. **`apply_cross_filter`** (`interactivity/cross_filter.py`) — Restricts rows using linked-chart selection state when enabled.
2. **`apply_aggregation`** (`core/aggregator.py`) — Group-by and agg when `agg_func` is not `none`.
3. **`maybe_sample`** (`core/sampling.py`) — Downsample very large frames for responsiveness (see `config.py` limits).
4. **`CHART_REGISTRY[chart_type]`** or **combo** path — Produces a raw `Figure`.
5. **`apply_theme`** (`theme/plotly_templates.py`) — Plotly template + layout consistent with Streamlit theme.

Combo mode (`chart_mode == "combo"`) uses **`charts/combo.generate_combo_chart`** with `y_col` / `y2_col` and `chart1_type` / `chart2_type`.

## Registered chart types (`CHART_REGISTRY`)

| Key | Module |
|-----|--------|
| `bar`, `line`, `scatter`, `area` | `charts/basic.py` |
| `box`, `histogram`, `violin` | `charts/distribution.py` |
| `pie`, `sunburst`, `treemap`, `funnel` | `charts/categorical.py` |
| `heatmap` | `charts/heatmap.py` |
| `sankey` | `charts/flow.py` |
| `choropleth`, `scatter_geo` | `charts/geo.py` |
| `animated` | `charts/animated.py` |

Extra dimensions (sankey columns, geo scope, animation column, etc.) are carried on **`ChartConfig`** and passed through **`generate_chart`** kwargs.

## `ChartConfig` (summary)

Defined in **`core/chart_config.py`**: mode (`basic` / `combo`), `chart_type`, axis columns, `agg_func`, heatmap column lists, palette, title override, hierarchical path columns, sankey source/target/value, geo columns / scope, lat/lon, animation column, trendline flag, combo second axis and trace types, and **`cross_filter_state`** for cache differentiation.

Use **`ChartConfig.normalized()`** and **`cache_key_tuple()`** for stable memoization.

## Dashboard builder

**`DashboardBuilder`** (`dashboard_builder.py`):

- **`pin_chart(chart_config, position=None)`** — Append or replace a pinned chart config in `st.session_state`.
- **`remove_chart(chart_id)`**, **`get_layout_grid(layout)`** — Layout strings like `2x2`, `3x3`.
- **`generate_chart_from_config(df, config_dict)`** — Converts stored dict to `ChartConfig` and calls `generate_from_config`.
- **`render_tab(df, selected_table)`** — Full “Dynamic Dashboard Builder” UI: layout picker, enable dashboard mode, grid of pinned charts, HTML/JSON export.

Layout presets for lower-level grids are listed in **`config.DASHBOARD_LAYOUT_PRESETS`** (used with `dashboard/grid_renderer.py` where applicable).

## Smart recommendations

**`get_chart_recommendations`** (`smart_recommendations.py`) — LLM-assisted (with heuristic fallback) ranked suggestions; returns structures compatible with **`ChartRecommendation`**.

## Module layout

```
data_visualization/
├── __init__.py
├── config.py
├── visualization.py          # Tab orchestrator
├── utils.py
├── chart_compositions.py     # Composition helpers + `generate_combo_chart` (public API)
├── dashboard_builder.py      # DashboardBuilder
├── smart_recommendations.py
├── core/
│   ├── chart_config.py
│   ├── chart_generator.py
│   ├── data_fetcher.py
│   ├── aggregator.py
│   ├── validators.py
│   └── sampling.py
├── charts/
│   ├── __init__.py           # CHART_REGISTRY
│   ├── basic.py
│   ├── distribution.py
│   ├── categorical.py
│   ├── heatmap.py
│   ├── flow.py
│   ├── geo.py
│   ├── combo.py
│   └── animated.py
├── theme/
│   ├── plotly_templates.py
│   ├── palettes.py
│   ├── layout.py
│   └── css.py
├── ui/
│   ├── controls.py
│   ├── chart_display.py
│   ├── filter_bar.py
│   ├── export_panel.py
│   ├── toolbar.py
│   ├── metric_cards.py
│   ├── data_preview.py
│   └── empty_states.py
├── dashboard/
│   ├── state.py
│   ├── grid_renderer.py
│   ├── chart_card.py
│   └── export.py
└── interactivity/
    ├── cross_filter.py
    └── selection_handler.py
```

## Environment

| Variable | Purpose |
|----------|---------|
| **`FASTAPI_URL`** | Base URL for session API (default `https://data-assistant-hj5f.onrender.com`). |
| **`OPENAI_API_KEY`** / **`OPENAI_MODEL`** | Used by smart chart recommendations when enabled. |

## Dependencies

Declared in the project root **`requirements.txt`** (Streamlit, Plotly, Pandas, Kaleido for static exports, etc.).

## Contributing

When adding a chart type:

1. Implement **`generate_<name>(df, config) -> go.Figure`** in an appropriate module under **`charts/`**.
2. Register it in **`charts/__init__.py`** → **`CHART_REGISTRY`**.
3. Add the type string to **`config.BASIC_CHART_TYPES`** if it should appear in the main picker.
4. Extend **`ChartConfig`** only if new fields are required; keep **`normalized()`** and **`cache_key_tuple()`** in sync.

Update this README when the public API or registry changes.

---

Part of the **Data Assistant** monorepo. See the root **[README.md](../README.md)** for platform architecture.

**Last updated:** March 2026
