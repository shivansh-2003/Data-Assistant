### 📊 **Recommended MCP Server Tools for Data Manipulation Tab**

You've successfully implemented **Multi-Format Data Upload** with Docling-powered table extraction from images/PDFs/Excel/CSV — great foundation!

Now, to power the **Data Manipulation Tab** (natural language → safe pandas execution via FastMCP server), we need a curated set of **atomic, composable tools** exposing key pandas functionalities.

These tools will be called by the LLM agent only after intent extraction and safety checks. Each tool should:
- Operate on the current DuckDB-backed DataFrame (loaded into pandas for execution)
- Return a summary of changes (e.g., "Removed 42 rows, filled 158 missing values")
- Update the shared state + append to operation history for undo/redo
- Be strictly read/write safe (no file system access, no exec/eval)

Below is a **detailed, prioritized list** of tool categories and specific functions to implement first. Focus on **high-impact, frequently used operations** that cover 90% of real-world data prep needs.

#### 🧹 **1. Data Cleaning Tools** (Highest Priority – Messy real-world data needs this most)

| Tool Name | Description | Pandas Equivalent | Parameters (Example) | Change Summary Example |
|-----------|-------------|-------------------|----------------------|------------------------|
| drop_rows | Remove rows by index, condition, or duplicates | `df.drop()`, `df[~condition]`, `df.drop_duplicates()` | indices: list[int], condition: str (e.g., "sales < 0"), subset: list[str], keep: 'first'/'last' | "Removed 127 duplicate rows (keeping first)" |
| fill_missing | Fill NaN values with strategy | `df.fillna()` | value: any, method: 'ffill'/'bfill', columns: list[str] | "Filled 89 missing values in 'age' with median (32)" |
| drop_missing | Drop rows/columns with missing values | `df.dropna()` | how: 'any'/'all', thresh: int, axis: 0/1, subset: list[str] | "Dropped 45 rows with any missing values" |
| replace_values | Replace specific values (including regex) | `df.replace()` | to_replace: dict/str, value: any, regex: bool | "Replaced 'N/A' → NaN in 3 columns" |
| clean_strings | Strip whitespace, lower/upper case, title case | `str.strip()`, `str.lower()`, etc. | columns: list[str], operation: 'strip'/'lower'/'upper'/'title' | "Cleaned string columns: stripped whitespace from 'name'" |
| remove_outliers | Remove/filter outliers using IQR or std dev | Custom condition | columns: list[str], method: 'iqr' (1.5) or 'zscore' (3) | "Removed 28 outliers from 'revenue' (IQR method)" |

#### 🔄 **2. Data Transformation Tools**

| Tool Name | Description | Pandas Equivalent | Parameters | Change Summary Example |
|-----------|-------------|-------------------|------------|------------------------|
| rename_columns | Rename one or more columns | `df.rename(columns=dict)` | mapping: dict[str,str] | "Renamed 'old_name' → 'customer_name'" |
| reorder_columns | Reorder column positions | `df[columns_list]` | columns: list[str] | "Reordered columns: moved 'date' to front" |
| sort_data | Sort by one or more columns | `df.sort_values()` | by: list[str], ascending: bool/list[bool] | "Sorted by 'date' descending and 'sales' ascending" |
| set_index | Set/reset index column(s) | `df.set_index()`, `df.reset_index()` | columns: list[str], drop: bool, reset: bool | "Set 'id' as index (dropped original)" |
| pivot_table | Create pivot summary | `pd.pivot_table()` | index: list[str], columns: list[str], values: list[str], aggfunc: 'sum'/'mean'/etc. | "Created pivot: sum of sales by region and year" |
| melt_unpivot | Unpivot wide data to long | `df.melt()` | id_vars: list[str], value_vars: list[str], var_name: str, value_name: str | "Unpivoted 12 month columns into 'month' and 'sales'" |
| apply_custom | Apply lambda or simple function to column(s) | `df.apply()` or `df[col].map()` | column: str, function: str (e.g., "lambda x: x*1.1") – limited safe functions only | "Applied tax rate: multiplied 'price' by 1.08" |

#### ✂️ **3. Row/Column Selection & Filtering Tools**

| Tool Name | Description | Pandas Equivalent | Parameters | Change Summary Example |
|-----------|-------------|-------------------|------------|------------------------|
| select_columns | Keep or drop specific columns | `df[columns]` or `df.drop(columns=)` | columns: list[str], keep: bool | "Kept only 8 columns: id, name, date, sales..." |
| filter_rows | Filter rows by condition (supports simple expressions) | `df.query()` or boolean indexing | condition: str (e.g., "age >= 18 and country == 'USA'") | "Filtered to 2,847 rows where revenue > 1000" |
| sample_rows | Random or fractional sample | `df.sample()` | n: int or frac: float, random_state: int | "Sampled 10% of rows (5,200 rows)" |

#### 🛠 **4. Data Aggregation & Grouping Tools**

| Tool Name | Description | Pandas Equivalent | Parameters | Change Summary Example |
|-----------|-------------|-------------------|------------|------------------------|
| group_by_agg | Group and aggregate | `df.groupby().agg()` | by: list[str], agg: dict[str,str] (e.g., {"sales": "sum", "profit": "mean"}) | "Grouped by 'region': computed sum(sales), mean(profit)" |
| describe_stats | Get summary statistics (optionally per group) | `df.describe()`, `groupby().describe()` | group_by: list[str] or None | "Generated descriptive stats (mean, std, quartiles)" |

#### ⚙️ **5. Selected Feature Engineering Tools** (Start with simple, high-value ones)

| Tool Name | Description | Pandas Equivalent | Parameters | Change Summary Example |
|-----------|-------------|-------------------|------------|------------------------|
| create_date_features | Extract year, month, day, weekday, quarter from date column | `dt.year`, `dt.month`, etc. | date_column: str, features: list['year','month','day','weekday','quarter','is_weekend'] | "Created 5 new date features from 'order_date'" |
| bin_numeric | Bin continuous column into categories | `pd.cut()` or `pd.qcut()` | column: str, bins: int or list[float], labels: list[str], qcut: bool | "Binned 'age' into 4 quantiles: young, adult..." |
| one_hot_encode | One-hot encode categorical columns | `pd.get_dummies()` | columns: list[str], drop_first: bool | "One-hot encoded 'category' → 12 new binary columns" |
| scale_numeric | Standardize or Min-Max scale | `sklearn` wrappers or manual | columns: list[str], method: 'standard'/'minmax' | "Standardized 'income' and 'spend' columns" |
| create_interaction | Multiply or combine two columns | Custom | col1: str, col2: str, new_name: str, operation: 'multiply'/'ratio' | "Created 'revenue_per_user' = revenue / users" |

#### 🔗 **6. Multi-Table Operations** (Essential for joins after multiple uploads)

| Tool Name | Description | Pandas Equivalent | Parameters | Change Summary Example |
|-----------|-------------|-------------------|------------|------------------------|
| merge_tables | Merge current df with another table in session | `pd.merge()` | right_table: str (session table name), on: list[str], how: 'inner'/'left'/etc. | "Left-joined 'customers' table on 'id' → 15,200 rows" |
| concat_tables | Stack tables vertically/horizontally | `pd.concat()` | tables: list[str], axis: 0/1 | "Concatenated 3 uploaded files vertically" |

### Implementation Tips for FastMCP Server

1. **Safety First**:
   - All tools receive the current DataFrame as input (from DuckDB → pandas).
   - Validate all parameters (e.g., column names exist).
   - Use `df.copy()` internally to avoid side effects until commit.
   - Blacklist dangerous operations (no `eval`, no `to_sql` without whitelist).

2. **Return Format** (for LLM feedback & history):
   ```json
   {
     "success": true,
     "change_summary": "Removed 42 rows where sales < 0",
     "rows_before": 10000,
     "rows_after": 9958,
     "columns_before": 12,
     "columns_after": 12,
     "preview_head": df.head(5).to_dict()
   }
   ```

3. **Start Small** → Implement in this order:
   1. Cleaning tools (drop_rows, fill_missing, drop_missing)
   2. Selection/filtering
   3. Transformation (rename, sort, select_columns)
   4. Aggregation
   5. Basic feature engineering
   6. Multi-table

This set will let users handle **95% of typical data prep tasks** in natural language while keeping the system fast, safe, and undoable.

Ready for the next step? Let me know which category to prototype first (e.g., cleaning tools code stubs). 🚀



### 📂 **Recommended Folder Structure for `data-mcp`**

Since you're focusing on **clean, modular Python files** (no utils/config/helper folders or files), we'll keep everything flat but logically grouped by category. Each file will contain related tools/functions that the FastMCP server can import and register.

This structure makes it easy to:
- Add new tools without clutter
- See at a glance what operations are available
- Import selectively in your MCP server registration

```
data-mcp/
├── __init__.py                  # Makes it a package + optional: export all tools
├── cleaning.py                  # Data cleaning tools
├── transformation.py            # Column renaming, sorting, pivoting, etc.
├── selection.py                 # Column selection, row filtering, sampling
├── aggregation.py               # Group-by, describe, pivot summaries
├── feature_engineering.py       # Date features, binning, encoding, scaling
├── multi_table.py               # Merge, concat across session tables
└── core.py                      # Essential shared state tools (load_df, save_df, get_summary, undo/redo helpers)
```

### 📄 **Detailed File Contents (What Goes Where)**

#### 1. `core.py` – Foundation (must exist first)
```python
# core.py
def load_current_dataframe() -> pd.DataFrame:
    """Load the current DataFrame from DuckDB shared state into pandas."""

def commit_dataframe(df: pd.DataFrame, change_summary: str) -> dict:
    """Save back to DuckDB, append to history, return preview/summary."""

def get_data_summary() -> dict:
    """Return rows, columns, dtypes, missing counts, etc."""

def undo_last_operation() -> dict:
    """Revert to previous state in history."""

def redo_operation() -> dict:
    """Re-apply undone operation."""
```

#### 2. `cleaning.py`
```python
# cleaning.py
def drop_rows(...) -> dict:
def fill_missing(...) -> dict:
def drop_missing(...) -> dict:
def replace_values(...) -> dict:
def clean_strings(...) -> dict:
def remove_outliers(...) -> dict:
```

#### 3. `transformation.py`
```python
# transformation.py
def rename_columns(...) -> dict:
def reorder_columns(...) -> dict:
def sort_data(...) -> dict:
def set_index(...) -> dict:
def pivot_table(...) -> dict:
def melt_unpivot(...) -> dict:
def apply_custom(...) -> dict:  # safe lambda only
```

#### 4. `selection.py`
```python
# selection.py
def select_columns(...) -> dict:
def filter_rows(...) -> dict:
def sample_rows(...) -> dict:
```

#### 5. `aggregation.py`
```python
# aggregation.py
def group_by_agg(...) -> dict:
def describe_stats(...) -> dict:
```

#### 6. `feature_engineering.py`
```python
# feature_engineering.py
def create_date_features(...) -> dict:
def bin_numeric(...) -> dict:
def one_hot_encode(...) -> dict:
def scale_numeric(...) -> dict:
def create_interaction(...) -> dict:
```

#### 7. `multi_table.py`
```python
# multi_table.py
def merge_tables(right_table_name: str, on: list[str], how: str = 'inner', ...) -> dict:
def concat_tables(table_names: list[str], axis: int = 0, ...) -> dict:
def list_available_tables() -> list[str]:  # Helper to show session tables
```

### 🚀 **Why This Structure Works Perfectly**

- **Flat & Simple**: No nested folders → easy imports (`from data_mcp.cleaning import drop_rows`)
- **Logical Grouping**: Files mirror natural data prep workflow stages
- **Extensible**: Adding a new tool? Just drop it in the right file
- **FastMCP Ready**: Your MCP server can do:
  ```python
  from data_mcp import cleaning, transformation, selection, aggregation, feature_engineering, multi_table, core
  
  tools = [
      *cleaning.__all__,   # or manually list functions
      *transformation.__all__,
      # ...
  ]
  ```

Start with `core.py` + `cleaning.py` → you'll have a working manipulation loop very quickly.

Want me to generate the full stub code for one of these files first (e.g., `cleaning.py` with actual function signatures and docstrings)? Just say the word! 🚀