# Data Visualization Module

A comprehensive visualization module for the Data Assistant Platform that provides zero-latency chart generation, smart AI-powered recommendations, advanced chart compositions, and dynamic dashboard building capabilities.

## 📋 Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Module Structure](#module-structure)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [API Documentation](#api-documentation)
- [Usage Examples](#usage-examples)
- [Integration Guide](#integration-guide)

## 🎯 Overview

The `data_visualization` module is a powerful visualization toolkit that enables users to:

- **Generate charts instantly** with zero-latency using Plotly
- **Get AI-powered recommendations** for optimal chart types based on data characteristics
- **Create advanced compositions** with combo charts, small multiples, faceted views, and layered visualizations
- **Build dynamic dashboards** with flexible grid layouts and chart pinning
- **Export visualizations** in multiple formats (PNG, SVG, HTML)

All visualizations are fully interactive, theme-aware, and automatically update with data manipulation changes.

## ✨ Features

### 1. **Basic Chart Generation**
- 8 chart types: Bar, Line, Scatter, Area, Box, Histogram, Pie, Heatmap
- Smart column selection with automatic defaults
- Aggregation support (sum, mean, count, min, max)
- Theme-aware (light/dark mode support)
- Real-time data integration from session storage

### 2. **Smart Chart Recommendations** 🤖
- AI-powered analysis using LangChain and OpenAI
- Analyzes data distribution, cardinality, correlations, and patterns
- Provides 3-5 ranked recommendations with reasoning
- One-click application of recommendations
- Fallback to rule-based recommendations if AI unavailable

### 3. **Custom Chart Compositions** 🎨
- **Combo Charts**: Dual y-axes combining different chart types (bar + line, scatter + area, etc.)
- **Small Multiples**: Grid of charts faceted by category (up to 12 panels)
- **Faceted Charts**: Automatic subplot creation (up to 4x4 grid) based on grouping
- **Layered Visualizations**: Multiple traces with adjustable opacity/transparency

### 4. **Dynamic Dashboard Builder** 📊
- Flexible grid layouts (2x2, 3x3, 2x3, 1x2, etc.)
- Chart pinning system for multi-view analysis
- Drag-and-drop style arrangement
- Individual chart management (remove, view info)
- State persistence across sessions

### 5. **Export Capabilities** 📥
- PNG export (static images)
- SVG export (vector graphics)
- HTML export (interactive charts)
- Automatic sizing for composition charts

## 📁 Module Structure

```
data_visualization/
├── __init__.py                 # Module exports and initialization
├── visualization.py            # Core visualization tab and chart generation
├── smart_recommendations.py    # AI-powered chart recommendations
├── chart_compositions.py        # Advanced chart composition functions
├── dashboard_builder.py         # Dynamic dashboard builder
└── README.md                   # This file
```

## 📦 Installation

The module requires the following dependencies (already included in main `requirements.txt`):

```python
streamlit>=1.28.0
plotly>=5.17.0
pandas>=2.1.3
numpy>=1.24.0
langchain-openai>=0.0.5
kaleido>=0.2.1  # For static image exports
```

## 🚀 Quick Start

### Basic Usage

```python
from data_visualization import render_visualization_tab

# In your Streamlit app
render_visualization_tab()
```

### Generate a Chart Programmatically

```python
from data_visualization import generate_chart
import pandas as pd

df = pd.DataFrame({
    'category': ['A', 'B', 'C', 'D'],
    'value': [10, 20, 15, 25]
})

fig = generate_chart(
    df=df,
    chart_type='bar',
    x_col='category',
    y_col='value',
    agg_func='none',
    color_col=None
)

# Display in Streamlit
st.plotly_chart(fig)
```

### Get Smart Recommendations

```python
from data_visualization import get_chart_recommendations

recommendations = get_chart_recommendations(
    df=df,
    user_query="Show sales trends over time"
)

for rec in recommendations:
    print(f"Chart: {rec['chart_type']}, Relevance: {rec['relevance']}")
```

## 📚 API Documentation

### Core Functions

#### `render_visualization_tab()`
Main function to render the complete visualization tab in Streamlit.

**Returns:** None (renders UI directly)

**Usage:**
```python
from data_visualization import render_visualization_tab

render_visualization_tab()
```

#### `generate_chart(df, chart_type, x_col, y_col, agg_func='none', color_col=None)`
Generate a basic Plotly chart.

**Parameters:**
- `df` (pd.DataFrame): Data to visualize
- `chart_type` (str): Chart type ('bar', 'line', 'scatter', 'area', 'box', 'histogram', 'pie', 'heatmap')
- `x_col` (str, optional): X-axis column name
- `y_col` (str, optional): Y-axis column name
- `agg_func` (str): Aggregation function ('none', 'sum', 'mean', 'count', 'min', 'max')
- `color_col` (str, optional): Column for color/grouping

**Returns:** `plotly.graph_objects.Figure`

#### `get_dataframe_from_session(session_id, table_name)`
Fetch DataFrame from session storage.

**Parameters:**
- `session_id` (str): Session identifier
- `table_name` (str): Name of the table to fetch

**Returns:** `pd.DataFrame` or `None`

### Smart Recommendations

#### `get_chart_recommendations(df, user_query=None)`
Get AI-powered chart recommendations.

**Parameters:**
- `df` (pd.DataFrame): Data to analyze
- `user_query` (str, optional): User's visualization goal

**Returns:** `List[Dict[str, Any]]` - List of recommendation dictionaries with:
- `chart_type`: Recommended chart type
- `x_column`: Suggested X-axis column
- `y_column`: Suggested Y-axis column
- `relevance`: Relevance score (1-5, lower is better)
- `reasoning`: Explanation for the recommendation

### Chart Compositions

#### `generate_combo_chart(df, x_col, y1_col, y2_col, chart1_type='bar', chart2_type='line', color_col=None)`
Generate combo chart with dual y-axes.

**Parameters:**
- `df` (pd.DataFrame): Data to visualize
- `x_col` (str): X-axis column
- `y1_col` (str): First Y-axis column (left)
- `y2_col` (str): Second Y-axis column (right)
- `chart1_type` (str): Type for first chart ('bar', 'line', 'scatter', 'area')
- `chart2_type` (str): Type for second chart ('bar', 'line', 'scatter', 'area')
- `color_col` (str, optional): Color/grouping column

**Returns:** `plotly.graph_objects.Figure`

#### `generate_small_multiples(df, x_col, y_col, facet_col, chart_type='bar', max_facets=12)`
Generate small multiples (grid of charts).

**Parameters:**
- `df` (pd.DataFrame): Data to visualize
- `x_col` (str): X-axis column
- `y_col` (str): Y-axis column
- `facet_col` (str): Column to facet by
- `chart_type` (str): Base chart type ('bar', 'line', 'scatter', 'histogram')
- `max_facets` (int): Maximum number of facets to show

**Returns:** `plotly.graph_objects.Figure`

#### `generate_faceted_chart(df, x_col, y_col, facet_col, chart_type='scatter', max_facets=16)`
Generate faceted chart with automatic subplot creation.

**Parameters:**
- `df` (pd.DataFrame): Data to visualize
- `x_col` (str): X-axis column
- `y_col` (str): Y-axis column
- `facet_col` (str): Column to facet by
- `chart_type` (str): Chart type ('scatter', 'bar', 'line', 'box')
- `max_facets` (int): Maximum facets (up to 4x4 grid)

**Returns:** `plotly.graph_objects.Figure`

#### `generate_layered_chart(df, x_col, y_cols, layer_types, opacity=0.7, color_col=None)`
Generate layered visualization with multiple traces.

**Parameters:**
- `df` (pd.DataFrame): Data to visualize
- `x_col` (str): X-axis column
- `y_cols` (List[str]): List of Y-axis columns to layer
- `layer_types` (List[str]): Chart types for each layer
- `opacity` (float): Opacity level (0-1)
- `color_col` (str, optional): Color/grouping column

**Returns:** `plotly.graph_objects.Figure`

### Dashboard Builder

#### `initialize_dashboard_state()`
Initialize dashboard state variables in Streamlit session state.

**Returns:** None

#### `pin_chart_to_dashboard(chart_config, position=None)`
Pin a chart configuration to the dashboard.

**Parameters:**
- `chart_config` (Dict[str, Any]): Chart configuration dictionary
- `position` (int, optional): Position index (None = append)

**Returns:** `bool` - True if successful

#### `render_dashboard_tab(df, selected_table)`
Render the dashboard builder interface.

**Parameters:**
- `df` (pd.DataFrame): Data to visualize
- `selected_table` (str): Name of the selected table

**Returns:** `bool` - Dashboard active status

#### `get_current_chart_config(chart_mode, chart_type, x_col, y_col, agg_func, color_col, composition_params)`
Get current chart configuration for pinning.

**Parameters:**
- `chart_mode` (str): Chart mode ('basic', 'combo', 'small_multiples', 'faceted', 'layered')
- `chart_type` (str): Chart type
- `x_col` (str): X column
- `y_col` (str): Y column
- `agg_func` (str): Aggregation function
- `color_col` (str, optional): Color column
- `composition_params` (Dict): Composition-specific parameters

**Returns:** `Dict[str, Any]` - Configuration dictionary

## 💡 Usage Examples

### Example 1: Basic Bar Chart

```python
from data_visualization import generate_chart
import pandas as pd

df = pd.DataFrame({
    'Department': ['Sales', 'Marketing', 'Engineering'],
    'Revenue': [100000, 80000, 120000]
})

fig = generate_chart(
    df=df,
    chart_type='bar',
    x_col='Department',
    y_col='Revenue'
)
```

### Example 2: Combo Chart (Bar + Line)

```python
from data_visualization import generate_combo_chart
import pandas as pd

df = pd.DataFrame({
    'Month': ['Jan', 'Feb', 'Mar', 'Apr'],
    'Sales': [1000, 1200, 1100, 1300],
    'Profit': [200, 250, 220, 280]
})

fig = generate_combo_chart(
    df=df,
    x_col='Month',
    y1_col='Sales',
    y2_col='Profit',
    chart1_type='bar',
    chart2_type='line'
)
```

### Example 3: Small Multiples

```python
from data_visualization import generate_small_multiples
import pandas as pd

df = pd.DataFrame({
    'Region': ['North', 'South', 'North', 'South', 'East', 'West'],
    'Product': ['A', 'A', 'B', 'B', 'A', 'B'],
    'Sales': [100, 150, 120, 180, 90, 110]
})

fig = generate_small_multiples(
    df=df,
    x_col='Product',
    y_col='Sales',
    facet_col='Region',
    chart_type='bar'
)
```

### Example 4: Get Recommendations

```python
from data_visualization import get_chart_recommendations
import pandas as pd

df = pd.DataFrame({
    'Date': pd.date_range('2024-01-01', periods=30),
    'Sales': range(100, 130),
    'Region': ['North'] * 15 + ['South'] * 15
})

recommendations = get_chart_recommendations(
    df=df,
    user_query="Show sales trends by region"
)

for idx, rec in enumerate(recommendations, 1):
    print(f"{idx}. {rec['chart_type']}: {rec['reasoning']}")
```

### Example 5: Dashboard Building

```python
from data_visualization import (
    initialize_dashboard_state,
    pin_chart_to_dashboard,
    get_current_chart_config
)

# Initialize dashboard
initialize_dashboard_state()

# Pin a chart
chart_config = get_current_chart_config(
    chart_mode='basic',
    chart_type='bar',
    x_col='Department',
    y_col='Revenue',
    agg_func='none',
    color_col=None,
    composition_params={}
)

pin_chart_to_dashboard(chart_config)
```

## 🔗 Integration Guide

### Integration with Streamlit App

The module is designed to integrate seamlessly with the main Streamlit application:

```python
# In app.py
from data_visualization import render_visualization_tab

# In your main function
tab1, tab2, tab3 = st.tabs(["Upload", "Manipulation", "Visualization"])

with tab3:
    render_visualization_tab()
```

### Session Data Integration

The module automatically fetches data from the session storage:

```python
from data_visualization import get_dataframe_from_session

df = get_dataframe_from_session(
    session_id="your-session-id",
    table_name="table_name"
)
```

### Environment Variables

The module uses the following environment variables:

- `FASTAPI_URL`: FastAPI backend URL (default: `http://localhost:8001`)
- `OPENAI_API_KEY`: OpenAI API key for smart recommendations
- `OPENAI_MODEL`: OpenAI model to use (default: `gpt-4o`)

## 🎨 Chart Types Reference

### Basic Charts

| Chart Type | Best For | Required Columns |
|------------|----------|------------------|
| Bar | Categorical comparisons | X (category), Y (value) |
| Line | Trends over time | X (time), Y (value) |
| Scatter | Correlations | X (numeric), Y (numeric) |
| Area | Cumulative values | X (time), Y (value) |
| Box | Distribution analysis | Y (numeric) |
| Histogram | Distribution shape | X (numeric) |
| Pie | Proportional breakdown | X or Y (categorical) |
| Heatmap | Correlation matrices | X, Y (both numeric) |

### Composition Charts

| Composition | Best For | Key Features |
|-------------|----------|--------------|
| Combo | Comparing different metrics | Dual y-axes, mixed chart types |
| Small Multiples | Comparing across categories | Grid layout, consistent scales |
| Faceted | Deep categorical analysis | Automatic subplots, shared legends |
| Layered | Overlaying multiple series | Transparency controls, blending |

## 🛠️ Advanced Features

### Theme Detection

Charts automatically adapt to Streamlit's theme:

```python
# Automatically detects dark/light mode
fig = generate_chart(df, 'bar', 'x', 'y')
# Chart uses plotly_dark or plotly_white template
```

### Aggregation Support

Apply aggregations directly in chart generation:

```python
fig = generate_chart(
    df=df,
    chart_type='bar',
    x_col='Department',
    y_col='Sales',
    agg_func='mean'  # Automatically groups and aggregates
)
```

### Export Options

All charts support multiple export formats:

```python
# PNG export
img_bytes = fig.to_image(format="png", width=1200, height=800)

# SVG export
svg_bytes = fig.to_image(format="svg", width=1200, height=800)

# HTML export
html_str = fig.to_html(full_html=False)
```

## 📝 Notes

- **Performance**: Charts are generated with zero latency using Plotly's efficient rendering
- **Interactivity**: All charts support zoom, pan, hover, and selection
- **Data Updates**: Charts automatically reflect changes from data manipulation operations
- **Session Persistence**: Dashboard state persists across page refreshes
- **Error Handling**: Graceful fallbacks for missing data or invalid configurations

## 🤝 Contributing

When adding new features:

1. Follow the existing module structure
2. Add type hints to all functions
3. Include docstrings with parameter descriptions
4. Update this README with new features
5. Ensure compatibility with existing chart types

## 📄 License

Part of the Data Assistant Platform project.

---

**Last Updated:** 2024
**Version:** 1.0.0

