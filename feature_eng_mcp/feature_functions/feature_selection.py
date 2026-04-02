"""Variance, correlation, and mutual information selection."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.feature_selection import mutual_info_classif, mutual_info_regression

from .core import run_fe_tool, preview_tail


def select_by_variance_impl(
    df: pd.DataFrame,
    columns: Optional[List[str]],
    threshold: float = 0.0,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    num = df.select_dtypes(include=[np.number])
    if columns:
        num = num[[c for c in columns if c in num.columns]]
    variances = num.var()
    remove = list(variances[variances <= threshold].index)
    keep = [c for c in df.columns if c not in remove]
    out = df[keep].copy()
    return out, {
        "removed_columns": remove,
        "remaining_columns": list(out.columns),
        "variance_stats": variances.to_dict(),
        "preview": preview_tail(out),
        "message": "select_by_variance",
    }


def select_by_correlation_impl(
    df: pd.DataFrame,
    columns: Optional[List[str]],
    threshold: float = 0.95,
    method: str = "pearson",
    keep: str = "first",
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    num = df.select_dtypes(include=[np.number])
    if columns:
        num = num[[c for c in columns if c in num.columns]]
    corr = num.corr(method=method)
    remove: List[str] = []
    pairs: List[Dict[str, Any]] = []
    cols = list(corr.columns)
    for i, a in enumerate(cols):
        for b in cols[i + 1 :]:
            v = corr.loc[a, b]
            if pd.notna(v) and abs(float(v)) >= threshold:
                drop = b if keep == "first" else a
                if drop not in remove:
                    remove.append(drop)
                pairs.append({"pair": [a, b], "correlation": float(v), "removed": drop})
    keep_cols = [c for c in df.columns if c not in remove]
    out = df[keep_cols].copy()
    return out, {
        "removed_columns": remove,
        "correlation_pairs": pairs,
        "preview": preview_tail(out),
        "message": "select_by_correlation",
    }


def select_by_mutual_info_impl(
    df: pd.DataFrame,
    target_column: str,
    columns: Optional[List[str]],
    n_features: Optional[int] = None,
    threshold: Optional[float] = None,
    task: str = "classification",
    random_state: Optional[int] = None,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    if target_column not in df.columns:
        raise ValueError("target_column missing")
    num = df.select_dtypes(include=[np.number]).drop(columns=[target_column], errors="ignore")
    if columns:
        num = num[[c for c in columns if c in num.columns]]
    y = df[target_column]
    if y.dtype == object or str(y.dtype) == "category":
        from sklearn.preprocessing import LabelEncoder

        y = LabelEncoder().fit_transform(y.astype(str))
    X = num.fillna(0).values
    if task == "classification":
        scores = mutual_info_classif(X, y, random_state=random_state)
    else:
        scores = mutual_info_regression(X, y, random_state=random_state)
    score_map = dict(zip(num.columns, scores))
    ranked = sorted(score_map.items(), key=lambda x: -x[1])
    selected = [c for c, _ in ranked]
    if n_features is not None:
        selected = selected[:n_features]
    if threshold is not None:
        selected = [c for c, s in score_map.items() if s >= threshold]
    removed = [c for c in num.columns if c not in selected]
    keep_cols = [c for c in df.columns if c in selected or c not in num.columns]
    out = df[keep_cols].copy()
    return out, {
        "selected_columns": selected,
        "removed_columns": removed,
        "mutual_info_scores": {k: float(v) for k, v in score_map.items()},
        "preview": preview_tail(out),
        "message": "select_by_mutual_info",
    }


def select_by_variance(
    session_id: str,
    columns: Optional[List[str]] = None,
    threshold: float = 0.0,
    table_name: str = "current",
) -> Dict[str, Any]:
    return run_fe_tool(
        session_id,
        table_name,
        "select_by_variance",
        lambda d: select_by_variance_impl(d, columns, threshold),
    )


def select_by_correlation(
    session_id: str,
    columns: Optional[List[str]] = None,
    threshold: float = 0.95,
    method: str = "pearson",
    keep: str = "first",
    table_name: str = "current",
) -> Dict[str, Any]:
    return run_fe_tool(
        session_id,
        table_name,
        "select_by_correlation",
        lambda d: select_by_correlation_impl(d, columns, threshold, method, keep),
    )


def select_by_mutual_info(
    session_id: str,
    target_column: str,
    columns: Optional[List[str]] = None,
    n_features: Optional[int] = None,
    threshold: Optional[float] = None,
    task: str = "classification",
    random_state: Optional[int] = None,
    table_name: str = "current",
) -> Dict[str, Any]:
    return run_fe_tool(
        session_id,
        table_name,
        "select_by_mutual_info",
        lambda d: select_by_mutual_info_impl(
            d, target_column, columns, n_features, threshold, task, random_state
        ),
    )
