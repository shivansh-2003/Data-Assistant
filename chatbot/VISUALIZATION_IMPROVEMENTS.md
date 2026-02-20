# Visualization System Improvements

## Overview

Enhanced the visualization system with additional chart types and smart auto-selection logic to improve reliability and user experience.

## New Chart Tools Added

### 1. Area Chart (`area_chart`)
- **Use cases**: Cumulative values, stacked area comparisons, trends with filled areas
- **Parameters**: `x_col` (time/date), `y_col` (numeric), `agg_func`, optional `color_col`
- **Example**: "Show cumulative sales over time"

### 2. Box Plot (`box_chart`)
- **Use cases**: Distribution comparison, outlier detection, statistical summary
- **Parameters**: `y_col` (numeric, required), optional `x_col` (categorical for grouping)
- **Example**: "Show distribution of Price by Company"

### 3. Heatmap (`heatmap_chart`)
- **Use cases**: Correlation matrices, pivot table heatmaps, multi-column relationships
- **Parameters**: `columns` (list of 2+ column names)
- **Example**: "Show correlation between Price, Weight, and Ram"

### 4. Correlation Matrix (`correlation_matrix`)
- **Use cases**: Quick correlation overview, finding relationships between all numeric variables
- **Parameters**: None (auto-selects all numeric columns)
- **Example**: "Show correlation matrix" or "What correlations exist?"

## Smart Auto-Chart Selection

### Rule-Based Selection (`utils/chart_selector.py`)

The system now includes intelligent chart selection based on data characteristics:

#### Rules

1. **Correlation Intent** → Scatter chart (2 numeric columns) or correlation matrix
2. **Trend Intent or Datetime X** → Line chart
3. **Compare Intent or Categorical X (low cardinality ≤25)** → Bar chart
4. **Distribution Intent or Single Numeric** → Histogram or box plot
5. **Numeric vs Numeric** → Scatter chart
6. **High Cardinality Categorical (>25)** → Box plot instead of bar chart

#### Benefits

- **Reliability**: Rule-based fallback improves consistency
- **Data-aware**: Uses column types and cardinality from data profile
- **Intent-aware**: Considers query intent (correlate, trend, compare, distribution)

### Integration Points

- **Analyzer Node**: Can use `suggest_chart_for_query()` as validation/fallback
- **Viz Node**: Uses data-aware validation before chart generation
- **Future**: Can be integrated as a pre-selection step before LLM tool calling

## Updated Components

### Tools (`tools/simple_charts.py`)
- Added `area_chart`, `box_chart`, `heatmap_chart`, `correlation_matrix` tools
- All tools follow the same pattern: return config dict with `chart_type` and parameters

### Graph (`graph.py`)
- Updated `route_from_insight()` to recognize new chart types
- Routes to viz node when any chart tool is selected

### Viz Node (`nodes/viz.py`)
- Handles correlation_matrix auto-selection (selects all numeric columns)
- Validates new chart types (area, box, heatmap)
- Maps chart tool names to visualization module chart types
- Supports `heatmap_columns` parameter for multi-column heatmaps

### Analyzer Prompt (`prompts/analyzer_prompt.py`)
- Documents all new chart types with use cases
- Includes examples for correlation, distribution, cumulative queries
- Guides LLM to select appropriate chart types

### Streamlit UI (`streamlit_ui.py`)
- `generate_chart_from_config_ui()` handles `heatmap_columns`
- Supports "auto" marker for correlation_matrix (selects all numeric columns)

## Architecture Benefits

### Why Structured Tools > Code Execution Alone

1. **Consistency**: All charts use the same visualization module (`data_visualization`)
2. **Validation**: Pre-validate chart parameters before generation
3. **UI Integration**: Charts integrate seamlessly with Streamlit UI
4. **Error Handling**: Structured tools enable better error messages
5. **Maintainability**: Chart logic centralized in visualization module

### Smart Selection Benefits

1. **Reliability**: Rule-based selection reduces LLM errors
2. **Performance**: Faster than LLM for simple cases
3. **Validation**: Can validate LLM-selected charts against data
4. **Fallback**: Provides backup when LLM selection fails

## Usage Examples

### User Queries That Now Work Better

- "Show correlation matrix" → `correlation_matrix()` → Auto-selects all numeric columns
- "Distribution of Price by Company" → `box_chart(y_col="Price", x_col="Company")`
- "Cumulative sales over time" → `area_chart(x_col="Date", y_col="Sales", agg_func="sum")`
- "Correlation between Price and Weight" → `scatter_chart(x_col="Price", y_col="Weight")` or `heatmap_chart(columns=["Price", "Weight"])`

## Future Enhancements

1. **Auto-selection integration**: Use `chart_selector` as primary selection method with LLM as fallback
2. **More chart types**: Violin plots, radar charts, treemaps
3. **Multi-chart responses**: Generate multiple charts for complex queries
4. **Chart recommendations**: Suggest alternative chart types when primary fails

## Files Changed

- `tools/simple_charts.py` - Added 4 new chart tools
- `tools/__init__.py` - Registered new tools
- `nodes/viz.py` - Handles new chart types, correlation_matrix auto-selection
- `graph.py` - Recognizes new chart types in routing
- `prompts/analyzer_prompt.py` - Documents new chart types
- `streamlit_ui.py` - Handles heatmap_columns in chart generation
- `utils/chart_selector.py` - NEW: Smart auto-selection logic
- `utils/README.md` - NEW: Documentation for chart selector
