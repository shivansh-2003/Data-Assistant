"""Data manipulation tools package for MCP server."""

# Core functions
from .core import (
    load_current_dataframe,
    commit_dataframe,
    get_data_summary,
    undo_last_operation,
    redo_operation,
    list_available_tables,
    initialize_table
)

# Cleaning tools
from .cleaning import (
    drop_rows,
    fill_missing,
    drop_missing,
    replace_values,
    clean_strings,
    remove_outliers
)

# Transformation tools
from .transformation import (
    rename_columns,
    reorder_columns,
    sort_data,
    set_index,
    pivot_table,
    melt_unpivot,
    apply_custom
)

# Selection tools
from .selection import (
    select_columns,
    filter_rows,
    sample_rows
)

# Aggregation tools
from .aggregation import (
    group_by_agg,
    describe_stats
)

# Feature engineering tools
from .feature_engineering import (
    create_date_features,
    bin_numeric,
    one_hot_encode,
    scale_numeric,
    create_interaction
)

# Multi-table tools
from .multi_table import (
    merge_tables,
    concat_tables
)

# Define __all__ for each module
__all__ = [
    # Core
    "load_current_dataframe",
    "commit_dataframe",
    "get_data_summary",
    "undo_last_operation",
    "redo_operation",
    "list_available_tables",
    "initialize_table",
    # Cleaning
    "drop_rows",
    "fill_missing",
    "drop_missing",
    "replace_values",
    "clean_strings",
    "remove_outliers",
    # Transformation
    "rename_columns",
    "reorder_columns",
    "sort_data",
    "set_index",
    "pivot_table",
    "melt_unpivot",
    "apply_custom",
    # Selection
    "select_columns",
    "filter_rows",
    "sample_rows",
    # Aggregation
    "group_by_agg",
    "describe_stats",
    # Feature engineering
    "create_date_features",
    "bin_numeric",
    "one_hot_encode",
    "scale_numeric",
    "create_interaction",
    # Multi-table
    "merge_tables",
    "concat_tables"
]

