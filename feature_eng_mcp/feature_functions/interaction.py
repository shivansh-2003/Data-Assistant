"""Polynomial and ratio features."""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.preprocessing import PolynomialFeatures

from .core import run_fe_tool, preview_tail


def polynomial_features_impl(
    df: pd.DataFrame,
    columns: List[str],
    degree: int = 2,
    interaction_only: bool = False,
    include_bias: bool = False,
    max_features: Optional[int] = None,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    cols = [c for c in columns if c in df.columns]
    if len(cols) < 1:
        raise ValueError("Need at least one column")
    X = df[cols].apply(pd.to_numeric, errors="coerce")
    n_before = len(df.columns)
    poly = PolynomialFeatures(
        degree=degree,
        interaction_only=interaction_only,
        include_bias=include_bias,
    )
    poly.fit(X)
    M = poly.transform(X)
    names = poly.get_feature_names_out(input_features=cols)
    if max_features is not None and M.shape[1] > max_features:
        M = M[:, : max_features]
        names = names[: max_features]
    out = df.copy()
    existing = set(out.columns)
    new_cols: List[str] = []
    for j, raw_name in enumerate(names):
        safe = str(raw_name).replace(" ", "_").replace("^", "pow")
        cand = f"poly_{safe}"
        k = 0
        while cand in existing:
            k += 1
            cand = f"poly_{safe}_{k}"
        existing.add(cand)
        out[cand] = M[:, j]
        new_cols.append(cand)
    return out, {
        "new_columns": new_cols,
        "feature_count_before": n_before,
        "feature_count_after": len(out.columns),
        "preview": preview_tail(out),
        "message": "polynomial features",
    }


def ratio_features_impl(
    df: pd.DataFrame,
    numerators: List[str],
    denominators: List[str],
    all_pairs: bool = False,
    handle_zero_division: str = "nan",
    new_names: Optional[List[str]] = None,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    out = df.copy()
    created: List[str] = []
    zero_counts: Dict[str, int] = {}
    pairs: List[Tuple[str, str]] = []
    if all_pairs:
        for n in numerators:
            for d in denominators:
                if n in df.columns and d in df.columns and n != d:
                    pairs.append((n, d))
    else:
        for n, d in zip(numerators, denominators):
            if n in df.columns and d in df.columns:
                pairs.append((n, d))
    for idx, (n, d) in enumerate(pairs):
        num = pd.to_numeric(out[n], errors="coerce")
        den = pd.to_numeric(out[d], errors="coerce")
        name = (
            new_names[idx]
            if new_names and idx < len(new_names)
            else f"{n}_over_{d}"
        )
        if handle_zero_division == "zero":
            r = num / den.replace(0, np.nan)
            r = r.fillna(0)
            zc = int((den == 0).sum())
        elif handle_zero_division == "clip":
            den_safe = den.replace(0, np.finfo(float).eps)
            r = num / den_safe
            zc = int((den == 0).sum())
        else:
            r = num / den.replace(0, np.nan)
            zc = int((den == 0).sum())
        out[name] = r
        created.append(name)
        zero_counts[name] = zc
    return out, {
        "created_columns": created,
        "zero_division_counts": zero_counts,
        "preview": preview_tail(out),
        "message": "ratio features",
    }


def create_polynomial_features(
    session_id: str,
    columns: List[str],
    degree: int = 2,
    interaction_only: bool = False,
    include_bias: bool = False,
    max_features: Optional[int] = None,
    table_name: str = "current",
) -> Dict[str, Any]:
    return run_fe_tool(
        session_id,
        table_name,
        "create_polynomial_features",
        lambda d: polynomial_features_impl(
            d, columns, degree, interaction_only, include_bias, max_features
        ),
    )


def create_ratio_features(
    session_id: str,
    numerators: List[str],
    denominators: List[str],
    all_pairs: bool = False,
    handle_zero_division: str = "nan",
    new_names: Optional[List[str]] = None,
    table_name: str = "current",
) -> Dict[str, Any]:
    return run_fe_tool(
        session_id,
        table_name,
        "create_ratio_features",
        lambda d: ratio_features_impl(
            d, numerators, denominators, all_pairs, handle_zero_division, new_names
        ),
    )
