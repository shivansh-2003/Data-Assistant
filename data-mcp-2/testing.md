# Manual Testing Guide (MCP Inspector)

This guide is for validating `data-mcp-2/server.py` manually using MCP Inspector (no automated tests).

## Prerequisites

- Python venv activated with project deps installed.
- Server running locally: `python server.py` in `data-mcp-2/`.
- MCP Inspector running (`npx @modelcontextprotocol/inspector`).
- MCP endpoint should be: `http://localhost:8000/data/mcp`.

## Connection Setup (MCP Inspector)

1. Transport Type: `Streamable HTTP`
2. URL: `http://localhost:8000/data/mcp`
3. Connection Type: `Via Proxy`
4. Click **Connect**.

Expected:
- Connection succeeds.
- “Tools” tab lists server tools.
- No 404 errors in the server logs.

## Core Server Health

1. Visit `http://localhost:8000/health` in the browser.
2. Visit `http://localhost:8000/docs` and ensure FastAPI docs load.

Expected:
- `/health` returns `{ "status": "healthy", ... }`
- `/docs` renders without errors.

## Session + Table Initialization

### Scenario: Initialize Table
Tool: `initialize_data_table`
Inputs:
- `session_id`: any UUID (new or existing)
- `table_name`: `current`

Expected:
- Success if ingestion API has data for the session.
- If no data exists, returns a clear error with `tables_available` empty.

### Scenario: List Tables
Tool: `list_tables`
Inputs:
- `session_id`: same as above

Expected:
- Returns array of table names.

### Scenario: Summary Serialization
Tool: `get_table_summary`
Inputs:
- `session_id`
- `table_name`

Expected:
- Success response with numeric fields serialized as JSON primitives.
- No serialization errors like `numpy.int64` in MCP Inspector.

## Selection Operations

### Scenario: Select Columns (keep)
Tool: `select_table_columns`
Inputs:
- `session_id`
- `columns`: valid column list
- `keep`: `true`

Expected:
- Column count reduced.
- `selected_columns` matches requested columns.

### Scenario: Select Columns (regex/dtypes)
Tool: `select_table_columns`
Inputs:
- `pattern`: `^date_`
- `dtypes`: `["number"]`

Expected:
- Returned columns match regex/dtype filters.

### Scenario: Filter Rows
Tool: `filter_table_rows`
Inputs:
- `condition`: `Price > 1000` (or any valid column)
- Also try lowercase column name: `price > 11`

Expected:
- Filtered row count in response.
- Lowercase column names should be auto-normalized to match actual columns.

### Scenario: Sample Rows (stratified)
Tool: `sample_table_rows`
Inputs:
- `by`: categorical column
- `n`: small integer
- `replace`: `false`

Expected:
- Sampled rows returned per group.

## Cleaning Operations

### Scenario: Drop Rows by Condition
Tool: `drop_rows_from_table`
Inputs:
- `condition`: `Price < 0` (or any valid condition)

Expected:
- `dropped_count` reflects removed rows.

### Scenario: Fill Missing (per-column)
Tool: `fill_missing_values`
Inputs:
- `methods`: `{"Price": "median"}`
- `values`: `{"Brand": "Unknown"}`

Expected:
- `fill_details` shows per-column methods.

### Scenario: Replace Values (case-insensitive)
Tool: `replace_table_values`
Inputs:
- `to_replace`: `{"Brand": {"dell": "Dell"}}`
- `case_insensitive`: `true`

Expected:
- Replacement succeeds with count reported.

### Scenario: Replace Values (schema validation)
Tool: `replace_table_values`
Inputs:
- `to_replace`: `{"Price": {"1000": "LaptopPrice"}}`

Expected:
- Validation passes because `to_replace` is a dict of dicts.
- A plain string value like `{"Price": "LaptopPrice"}` should fail validation.

### Scenario: Remove Outliers (cap)
Tool: `remove_outliers_from_table`
Inputs:
- `columns`: numeric columns
- `handle_method`: `cap`
- `include_boxplot`: `true`

Expected:
- Outlier stats returned, no row drops when capping.

## Transformation Operations

### Scenario: Rename Columns (new table)
Tool: `rename_table_columns`
Inputs:
- `mapping`: `{"Price": "Cost"}`
- `inplace`: `false`
- `new_table_name`: `renamed_table`

Expected:
- New table created, original unaffected.

### Scenario: Sort Data (multi-column)
Tool: `sort_table_data`
Inputs:
- `by`: `["Brand", "Price"]`
- `ascending`: `[true, false]`
- `na_position`: `last`

Expected:
- Sorted output, no errors.

### Scenario: Apply Custom Function (whitelist)
Tool: `apply_custom_function`
Inputs:
- `column`: numeric column
- `function`: `double`
- `new_column`: `Price_dbl`

Expected:
- New column created successfully.
- Non-whitelisted function should return a clear error.

## Aggregation Operations

### Scenario: Group By + Aggregation
Tool: `group_by_aggregate`
Inputs:
- `by`: `["Brand"]`
- `agg`: `{"Price": "mean"}`

Expected:
- Aggregated table returned.

### Scenario: Describe Stats
Tool: `describe_table_stats`
Inputs:
- `group_by`: optional

Expected:
- `statistics` field populated.

## Feature Engineering

### Scenario: Create Date Features
Tool: `create_date_features_for_column`
Inputs:
- `date_column`: valid date column
- `features`: `["year", "month"]`

Expected:
- New date feature columns present.

### Scenario: One Hot Encode
Tool: `one_hot_encode_columns`
Inputs:
- `columns`: categorical column list

Expected:
- New dummy columns created.

## Multi-table Operations

### Scenario: Merge Tables
Tool: `merge_data_tables`
Inputs:
- `left_table`, `right_table`, `on` or `left_on/right_on`

Expected:
- Merged table returned.

### Scenario: Concat Tables
Tool: `concat_data_tables`
Inputs:
- `tables`: list of tables
- `axis`: `0`

Expected:
- Concatenated table returned.

## Negative/Edge Cases

- Invalid column names for any tool → clear error message.
- Invalid aggregation function → clear error message.
- Sort with mismatched `ascending` list length → error.
- `apply_custom_function` with unsupported name → error.
- `filter_table_rows` with invalid condition → error.

## Pass/Fail Criteria

- No MCP Inspector connection errors.
- All tested tools return JSON-serializable responses.
- Error cases return descriptive messages (no server crashes).
