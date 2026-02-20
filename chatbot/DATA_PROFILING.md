# Data Profiling Layer

## Overview

Comprehensive data profiling runs automatically before any query to provide rich context for tool selection, chart validation, and code generation. This reduces hallucination and improves accuracy.

## Profiling Features

### 1. Basic Statistics (Per Column)

- **Data Type**: `dtype` (e.g., "int64", "float64", "object")
- **Unique Count**: `n_unique` - Number of distinct values
- **Null Count**: `n_null` - Number of missing values
- **Missing Percentage**: `missing_pct` - Percentage of null values (0-100)

### 2. Cardinality Classification

Automatically categorizes columns by uniqueness:
- **Low**: < 10 unique values (e.g., status codes, categories)
- **Medium**: 10-100 unique values (e.g., regions, product types)
- **High**: > 100 unique values (e.g., IDs, timestamps, continuous numeric)

### 3. Numeric Distribution Summary

For numeric columns, computes:
- **Mean**: Average value
- **Median**: Middle value
- **Standard Deviation**: Spread measure
- **Min/Max**: Range bounds
- **Quartiles**: Q25, Q75 (interquartile range)

### 4. Categorical Category Counts

For categorical columns, tracks:
- **Top 10 Categories**: Most frequent values with counts
- Useful for understanding data distribution

## Profile Structure

```python
{
    "tables": {
        "table_name": {
            "columns": {
                "column_name": {
                    "dtype": "int64",
                    "n_unique": 100,
                    "n_null": 5,
                    "missing_pct": 5.0,
                    "cardinality": "medium",
                    "is_numeric": True,
                    "is_categorical": False,
                    "numeric_stats": {
                        "mean": 10.5,
                        "median": 10.0,
                        "std": 2.3,
                        "min": 1.0,
                        "max": 20.0,
                        "q25": 8.0,
                        "q75": 13.0
                    },
                    "top_categories": {}  # Only for categorical
                }
            }
        }
    }
}
```

## Usage

### 1. Prompt Injection

Profiles are compressed and injected into prompts for:
- **Analyzer**: Tool selection with data awareness
- **Code Generator**: Better column selection and aggregation choices
- **Chart Selector**: Smart chart type recommendations

**Format Example:**
```
Table 'sales': 
  Price (numeric, 100 unique, 5% missing, medium cardinality, mean=10.5, range=[1.0-20.0]); 
  Region (categorical, 5 unique, 0% missing, low cardinality, top: North=50, South=30)
```

### 2. Chart Validation

Profiles enable pre-validation before chart generation:

- **Bar Chart**: Checks cardinality (< 25 recommended)
- **Pie Chart**: Checks cardinality (< 10 recommended)
- **Histogram**: Validates numeric type
- **Scatter**: Validates both columns are numeric
- **Box Plot**: Validates numeric Y column

**Benefits:**
- Prevents chart generation failures
- Provides clear error messages
- Suggests alternatives when unsuitable

### 3. Smart Chart Selection

Chart selector uses profiles to:
- Detect column types (numeric vs categorical)
- Assess cardinality levels
- Choose appropriate chart types
- Avoid unsuitable visualizations

## Implementation

### Core Functions

**`get_session_profile(session_id)`** (`session_loader.py`)
- Computes comprehensive profile for all tables
- Runs automatically when session data is loaded
- Cached in state for reuse

**`format_profile_for_prompt(profile, max_columns=20)`** (`profile_formatter.py`)
- Compresses profile into prompt-friendly string
- Limits columns to prevent prompt bloat
- Includes key statistics per column

**`is_suitable_for_chart(profile, table, column, chart_type)`** (`profile_formatter.py`)
- Validates column suitability for chart type
- Returns (is_suitable, reason) tuple
- Uses profile data for fast validation

### Integration Points

1. **Session Loader** (`utils/session_loader.py`)
   - `get_session_profile()` computes full profile
   - Called during `prepare_state_dataframes()`

2. **Analyzer Node** (`nodes/analyzer.py`)
   - Uses `format_profile_for_prompt()` for prompt injection
   - Helps LLM select appropriate tools

3. **Viz Node** (`nodes/viz.py`)
   - Uses `is_suitable_for_chart()` for validation
   - Prevents unsuitable chart generation

4. **Chart Selector** (`utils/chart_selector.py`)
   - Uses profile for smart chart recommendations
   - Falls back to DataFrame analysis if profile unavailable

## Benefits

### 1. Reduced Hallucination
- LLM sees actual data characteristics
- Prevents assumptions about column types
- Better column name disambiguation

### 2. Improved Tool Selection
- Analyzer knows cardinality before selecting charts
- Code generator understands data distribution
- Fewer tool selection errors

### 3. Faster Validation
- Profile-based checks faster than DataFrame analysis
- Pre-computed statistics avoid repeated calculations
- Enables early error detection

### 4. Better User Experience
- Clear error messages with data context
- Proactive suggestions for alternatives
- More accurate chart recommendations

## Performance

- **Computation**: ~50-200ms per table (one-time)
- **Storage**: ~1-5KB per table (compressed)
- **Reuse**: Profile cached in state, reused across queries
- **Overhead**: Minimal (computed once per session)

## Future Enhancements

1. **Distribution Detection**: Identify normal, skewed, uniform distributions
2. **Outlier Detection**: Flag columns with outliers
3. **Correlation Pre-computation**: Cache correlation matrices
4. **Temporal Patterns**: Detect time series patterns
5. **Incremental Updates**: Update profile as data changes

## Files

- `utils/session_loader.py` - Profile computation (`get_session_profile`)
- `utils/profile_formatter.py` - Profile formatting and validation
- `nodes/analyzer.py` - Profile injection into prompts
- `nodes/viz.py` - Profile-based chart validation
- `utils/chart_selector.py` - Profile-based chart selection
