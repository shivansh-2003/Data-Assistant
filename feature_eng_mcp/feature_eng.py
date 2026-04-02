#!/usr/bin/env python3
"""
Feature Engineering MCP — FastMCP tool definitions.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import numpy as np
import pandas as pd
from fastmcp import FastMCP

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from feature_eng_mcp.feature_functions.core import (  # noqa: E402
    initialize_table,
    get_data_summary,
    list_available_tables,
    undo_last_operation,
    redo_operation_fe,
)
from feature_eng_mcp.feature_functions import numeric_transforms  # noqa: E402
from feature_eng_mcp.feature_functions import scaling  # noqa: E402
from feature_eng_mcp.feature_functions import interaction  # noqa: E402
from feature_eng_mcp.feature_functions import categorical  # noqa: E402
from feature_eng_mcp.feature_functions import text_features  # noqa: E402
from feature_eng_mcp.feature_functions import feature_selection  # noqa: E402
from feature_eng_mcp.feature_functions import dimensionality  # noqa: E402
from feature_eng_mcp.feature_functions import clustering_features  # noqa: E402
from feature_eng_mcp.feature_functions import datetime_features  # noqa: E402
from feature_eng_mcp.feature_functions import pipeline as fe_pipeline  # noqa: E402

mcp = FastMCP(
    name="Feature Engineering MCP Server",
    instructions="""
    Advanced feature engineering for ML: numeric transforms, scaling, interactions,
    categorical encoding, text (BoW/TF-IDF), dimensionality reduction, k-means features,
    datetime features, feature selection, and multi-step pipelines. Session-based;
    use initialize_data_table then pass session_id and table_name to each tool.
    """,
)


def _to_serializable(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _to_serializable(val) for key, val in value.items()}
    if isinstance(value, list):
        return [_to_serializable(item) for item in value]
    if isinstance(value, tuple):
        return [_to_serializable(item) for item in value]
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if pd.isna(value):
        return None
    return value


# --- Session ---


@mcp.tool()
def initialize_data_table(session_id: str, table_name: str = "current") -> dict:
    """Load session tables into MCP memory; call before feature tools."""
    try:
        return initialize_table(session_id, table_name)
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def get_table_summary(session_id: str, table_name: str = "current") -> dict:
    try:
        return _to_serializable(get_data_summary(session_id, table_name))
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def list_tables(session_id: str) -> dict:
    try:
        tables = list_available_tables(session_id)
        return {"success": True, "tables": tables, "count": len(tables)}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def undo_operation(session_id: str, table_name: str = "current") -> dict:
    try:
        return undo_last_operation(session_id, table_name)
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def redo_operation(session_id: str, table_name: str = "current") -> dict:
    try:
        return redo_operation_fe(session_id, table_name)
    except Exception as e:
        return {"success": False, "error": str(e)}


# --- Phase 1 numeric / scaling / interaction ---


@mcp.tool()
def log_transform(
    session_id: str,
    columns: List[str],
    base: str = "log10",
    offset: float = 1.0,
    new_suffix: str = "_log",
    replace: bool = False,
    table_name: str = "current",
) -> dict:
    return _to_serializable(
        numeric_transforms.log_transform(
            session_id, columns, base, offset, new_suffix, replace, table_name
        )
    )


@mcp.tool()
def power_transform(
    session_id: str,
    columns: List[str],
    method: str = "box-cox",
    standardize: bool = True,
    new_suffix: str = "_power",
    table_name: str = "current",
) -> dict:
    return _to_serializable(
        numeric_transforms.power_transform(
            session_id, columns, method, None, standardize, new_suffix, table_name
        )
    )


@mcp.tool()
def binarize(
    session_id: str,
    columns: List[str],
    threshold: float = 0.0,
    new_suffix: str = "_binary",
    table_name: str = "current",
) -> dict:
    return _to_serializable(
        numeric_transforms.binarize(session_id, columns, threshold, new_suffix, table_name)
    )


@mcp.tool()
def quantize_bins(
    session_id: str,
    column: str,
    strategy: str = "uniform",
    n_bins: int = 4,
    custom_edges: Optional[List[float]] = None,
    encode: str = "ordinal",
    new_suffix: str = "_binned",
    table_name: str = "current",
) -> dict:
    return _to_serializable(
        numeric_transforms.quantize_bins(
            session_id,
            column,
            strategy,
            n_bins,
            custom_edges,
            None,
            encode,
            new_suffix,
            table_name,
        )
    )


@mcp.tool()
def scale_features(
    session_id: str,
    columns: List[str],
    method: str = "standard",
    feature_range: Optional[List[float]] = None,
    with_centering: bool = True,
    fit_id: Optional[str] = None,
    transform_id: Optional[str] = None,
    new_suffix: str = "",
    table_name: str = "current",
) -> dict:
    fr = tuple(feature_range) if feature_range and len(feature_range) == 2 else (0, 1)
    return _to_serializable(
        scaling.scale_features(
            session_id,
            columns,
            method,
            fr,
            with_centering,
            fit_id,
            transform_id,
            new_suffix,
            table_name,
        )
    )


@mcp.tool()
def create_polynomial_features(
    session_id: str,
    columns: List[str],
    degree: int = 2,
    interaction_only: bool = False,
    include_bias: bool = False,
    max_features: Optional[int] = None,
    table_name: str = "current",
) -> dict:
    return _to_serializable(
        interaction.create_polynomial_features(
            session_id,
            columns,
            degree,
            interaction_only,
            include_bias,
            max_features,
            table_name,
        )
    )


@mcp.tool()
def create_ratio_features(
    session_id: str,
    numerators: List[str],
    denominators: List[str],
    all_pairs: bool = False,
    handle_zero_division: str = "nan",
    table_name: str = "current",
) -> dict:
    return _to_serializable(
        interaction.create_ratio_features(
            session_id,
            numerators,
            denominators,
            all_pairs,
            handle_zero_division,
            None,
            table_name,
        )
    )


# --- Phase 2 categorical / selection ---


@mcp.tool()
def encode_categorical(
    session_id: str,
    columns: List[str],
    method: str = "onehot",
    drop_first: bool = False,
    target_column: Optional[str] = None,
    smoothing: float = 1.0,
    fit_id: Optional[str] = None,
    transform_id: Optional[str] = None,
    table_name: str = "current",
) -> dict:
    return _to_serializable(
        categorical.encode_categorical(
            session_id,
            columns,
            method,
            drop_first,
            "ignore",
            None,
            None,
            None,
            target_column,
            smoothing,
            fit_id,
            transform_id,
            table_name,
        )
    )


@mcp.tool()
def feature_hash(
    session_id: str,
    columns: List[str],
    n_features: int = 256,
    alternate_sign: bool = True,
    table_name: str = "current",
) -> dict:
    return _to_serializable(
        categorical.feature_hash(
            session_id, columns, n_features, alternate_sign, "string", table_name
        )
    )


@mcp.tool()
def select_by_variance(
    session_id: str,
    columns: Optional[List[str]] = None,
    threshold: float = 0.0,
    table_name: str = "current",
) -> dict:
    return _to_serializable(
        feature_selection.select_by_variance(session_id, columns, threshold, table_name)
    )


@mcp.tool()
def select_by_correlation(
    session_id: str,
    columns: Optional[List[str]] = None,
    threshold: float = 0.95,
    method: str = "pearson",
    table_name: str = "current",
) -> dict:
    return _to_serializable(
        feature_selection.select_by_correlation(
            session_id, columns, threshold, method, "first", table_name
        )
    )


# --- Phase 3 text ---


@mcp.tool()
def text_to_bow(
    session_id: str,
    text_column: str,
    max_features: Optional[int] = 500,
    min_df: float = 1,
    max_df: float = 1.0,
    ngram_min: int = 1,
    ngram_max: int = 1,
    binary: bool = False,
    fit_id: Optional[str] = None,
    table_name: str = "current",
) -> dict:
    return _to_serializable(
        text_features.text_to_bow(
            session_id,
            text_column,
            max_features,
            min_df,
            max_df,
            (ngram_min, ngram_max),
            binary,
            "english",
            True,
            r"(?u)\b\w\w+\b",
            "dense_table",
            fit_id,
            table_name,
        )
    )


@mcp.tool()
def text_to_tfidf(
    session_id: str,
    text_column: str,
    max_features: Optional[int] = 500,
    min_df: float = 1,
    max_df: float = 1.0,
    ngram_min: int = 1,
    ngram_max: int = 1,
    fit_id: Optional[str] = None,
    table_name: str = "current",
) -> dict:
    return _to_serializable(
        text_features.text_to_tfidf(
            session_id,
            text_column,
            max_features,
            min_df,
            max_df,
            (ngram_min, ngram_max),
            True,
            "l2",
            True,
            True,
            "english",
            fit_id,
            table_name,
        )
    )


@mcp.tool()
def extract_text_stats(
    session_id: str,
    text_column: str,
    features: Optional[List[str]] = None,
    table_name: str = "current",
) -> dict:
    return _to_serializable(
        text_features.extract_text_stats(session_id, text_column, features, table_name)
    )


# --- Phase 4 advanced ---


@mcp.tool()
def apply_pca(
    session_id: str,
    columns: Optional[List[str]] = None,
    n_components: Union[int, float] = 0.95,
    whiten: bool = False,
    fit_id: Optional[str] = None,
    transform_id: Optional[str] = None,
    table_name: str = "current",
) -> dict:
    return _to_serializable(
        dimensionality.apply_pca(
            session_id,
            columns,
            n_components,
            whiten,
            True,
            fit_id,
            transform_id,
            table_name,
        )
    )


@mcp.tool()
def apply_truncated_svd(
    session_id: str,
    columns: Optional[List[str]] = None,
    n_components: int = 100,
    fit_id: Optional[str] = None,
    transform_id: Optional[str] = None,
    table_name: str = "current",
) -> dict:
    return _to_serializable(
        dimensionality.apply_truncated_svd(
            session_id,
            columns,
            n_components,
            5,
            None,
            fit_id,
            transform_id,
            table_name,
        )
    )


@mcp.tool()
def kmeans_featurize(
    session_id: str,
    columns: List[str],
    n_clusters: int = 8,
    output_type: str = "soft",
    scale_first: bool = True,
    fit_id: Optional[str] = None,
    transform_id: Optional[str] = None,
    table_name: str = "current",
) -> dict:
    return _to_serializable(
        clustering_features.kmeans_featurize(
            session_id,
            columns,
            n_clusters,
            output_type,
            scale_first,
            None,
            10,
            300,
            fit_id,
            transform_id,
            table_name,
        )
    )


@mcp.tool()
def create_advanced_date_features(
    session_id: str,
    date_column: str,
    features: List[str],
    date_format: Optional[str] = None,
    table_name: str = "current",
) -> dict:
    return _to_serializable(
        datetime_features.create_advanced_date_features(
            session_id,
            date_column,
            features,
            None,
            None,
            date_format,
            table_name,
        )
    )


@mcp.tool()
def create_time_since_features(
    session_id: str,
    date_column: str,
    reference_column: Optional[str] = None,
    reference_date: Optional[str] = None,
    unit: str = "days",
    table_name: str = "current",
) -> dict:
    return _to_serializable(
        datetime_features.create_time_since_features(
            session_id,
            date_column,
            reference_column,
            reference_date,
            unit,
            None,
            table_name,
        )
    )


@mcp.tool()
def select_by_mutual_info(
    session_id: str,
    target_column: str,
    columns: Optional[List[str]] = None,
    n_features: Optional[int] = None,
    task: str = "classification",
    table_name: str = "current",
) -> dict:
    return _to_serializable(
        feature_selection.select_by_mutual_info(
            session_id,
            target_column,
            columns,
            n_features,
            None,
            task,
            None,
            table_name,
        )
    )


# --- Phase 5 pipeline ---


@mcp.tool()
def create_feature_pipeline(
    session_id: str,
    steps: List[Dict[str, Any]],
    pipeline_id: str,
    table_name: str = "current",
) -> dict:
    return _to_serializable(
        fe_pipeline.create_feature_pipeline(session_id, steps, pipeline_id, table_name)
    )


@mcp.tool()
def apply_saved_pipeline(
    session_id: str,
    pipeline_id: str,
    table_name: str = "current",
) -> dict:
    return _to_serializable(
        fe_pipeline.apply_saved_pipeline(session_id, pipeline_id, table_name)
    )
