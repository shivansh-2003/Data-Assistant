# Chatbot Utilities

Utility modules for InsightBot.

## chart_selector.py

Smart auto-chart selection based on data characteristics.

### Features

- **Rule-based chart selection**: Automatically selects the best chart type based on:
  - Column types (datetime, numeric, categorical)
  - Cardinality (number of unique values)
  - Query intent (correlate, trend, compare, distribution)
  - Data profile information

### Usage

```python
from chatbot.utils.chart_selector import auto_select_chart, suggest_chart_for_query

# Auto-select based on DataFrame and columns
chart_type, config = auto_select_chart(
    df=df,
    x_col="Company",
    y_col="Price",
    query_intent="compare",
    data_profile=profile
)

# Suggest chart from query text
suggestion = suggest_chart_for_query(
    query="Show correlation between Price and Weight",
    schema=schema,
    data_profile=profile,
    mentioned_columns=["Price", "Weight"]
)
```

### Rules

1. **Correlation intent** → scatter chart (if 2 numeric columns) or correlation matrix
2. **Trend intent or datetime X** → line chart
3. **Compare intent or categorical X (low cardinality)** → bar chart
4. **Distribution intent or single numeric** → histogram or box plot
5. **Numeric vs numeric** → scatter chart
6. **High cardinality categorical (>25)** → box plot instead of bar

### Integration

The chart selector can be used as a fallback when LLM tool selection fails, or as a validation step to ensure chart types match data characteristics.
