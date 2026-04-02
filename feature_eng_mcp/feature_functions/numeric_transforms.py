"""Numeric transforms: log, power (Box-Cox / Yeo-Johnson), binarize, quantization."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from .core import preview_tail


def _col_stats(s: pd.Series) -> Dict[str, float]:
    s = pd.to_numeric(s, errors="coerce").dropna()
    if s.empty:
        return {"min": None, "max": None, "skew": None}
    return {
        "min": float(s.min()),
        "max": float(s.max()),
        "skew": float(s.skew()) if len(s) > 2 else 0.0,
    }


def log_transform_impl(
    df: pd.DataFrame,
    columns: List[str],
    base: str = "log10",
    offset: float = 1.0,
    new_suffix: str = "_log",
    replace: bool = False,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    stats_before = {}
    stats_after = {}
    created = []
    out = df.copy()
    for c in columns:
        if c not in out.columns:
            continue
        stats_before[c] = _col_stats(out[c])
        x = pd.to_numeric(out[c], errors="coerce").astype(float) + offset
        if base == "ln":
            vals = np.log(np.clip(x, 1e-300, None))
        elif base == "log2":
            vals = np.log2(np.clip(x, 1e-300, None))
        else:
            vals = np.log10(np.clip(x, 1e-300, None))
        name = c if replace else f"{c}{new_suffix}"
        out[name] = vals
        if not replace:
            created.append(name)
        stats_after[name if not replace else c] = _col_stats(out[name])
    return out, {
        "created_columns": created if not replace else columns,
        "stats_before": stats_before,
        "stats_after": stats_after,
        "preview": preview_tail(out),
        "message": f"log_transform applied ({base})",
    }


def power_transform_impl(
    df: pd.DataFrame,
    columns: List[str],
    method: str = "box-cox",
    lmbda: Optional[float] = None,
    standardize: bool = True,
    new_suffix: str = "_power",
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    from sklearn.preprocessing import PowerTransformer

    out = df.copy()
    fitted: Dict[str, float] = {}
    stats_before = {}
    stats_after = {}
    created = []
    for c in columns:
        if c not in out.columns:
            continue
        stats_before[c] = _col_stats(out[c])
        x = pd.to_numeric(out[c], errors="coerce").astype(float)
        col_data = x.values.reshape(-1, 1)
        valid = ~np.isnan(col_data.ravel())
        if valid.sum() < 2:
            continue
        method_lc = method.lower().replace("_", "-")
        pt_kind = "box-cox" if method_lc == "box-cox" else "yeo-johnson"
        pt = PowerTransformer(method=pt_kind, standardize=standardize)
        # Box-Cox requires strictly positive
        if pt_kind == "box-cox":
            if (col_data[valid] <= 0).any():
                raise ValueError(f"Column {c}: Box-Cox requires positive values")
        pt.fit(col_data[valid])
        transformed = np.full_like(col_data.ravel(), np.nan, dtype=float)
        transformed[valid] = pt.transform(col_data[valid]).ravel()
        new_c = f"{c}{new_suffix}"
        out[new_c] = transformed
        created.append(new_c)
        if hasattr(pt, "lambdas_"):
            fitted[new_c] = float(pt.lambdas_[0])
        stats_after[new_c] = _col_stats(out[new_c])
    return out, {
        "created_columns": created,
        "fitted_lambdas": fitted,
        "stats_before": stats_before,
        "stats_after": stats_after,
        "preview": preview_tail(out),
        "message": "power_transform applied",
    }


def binarize_impl(
    df: pd.DataFrame,
    columns: List[str],
    threshold: float = 0.0,
    new_suffix: str = "_binary",
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    out = df.copy()
    created = []
    counts: Dict[str, Dict[int, int]] = {}
    for c in columns:
        if c not in out.columns:
            continue
        x = pd.to_numeric(out[c], errors="coerce").fillna(0)
        b = (x > threshold).astype(int)
        name = f"{c}{new_suffix}"
        out[name] = b
        created.append(name)
        vc = b.value_counts().to_dict()
        counts[name] = {int(k): int(v) for k, v in vc.items()}
    return out, {
        "created_columns": created,
        "value_counts": counts,
        "preview": preview_tail(out),
        "message": "binarize applied",
    }


def quantize_bins_impl(
    df: pd.DataFrame,
    column: str,
    strategy: str = "uniform",
    n_bins: int = 4,
    custom_edges: Optional[List[float]] = None,
    labels: Optional[List[str]] = None,
    encode: str = "ordinal",
    new_suffix: str = "_binned",
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    if column not in df.columns:
        raise ValueError(f"Column {column} not found")
    x = pd.to_numeric(df[column], errors="coerce")
    out = df.copy()
    new_col = f"{column}{new_suffix}"
    strategy = strategy.lower()
    if strategy == "custom" and custom_edges:
        edges = sorted(custom_edges)
        cats = pd.cut(x, bins=edges, labels=False, include_lowest=True)
    elif strategy == "quantile":
        cats = pd.qcut(x, q=n_bins, labels=labels, duplicates="drop")
        if encode == "ordinal" and hasattr(cats, "cat"):
            cats = cats.cat.codes
    elif strategy == "log":
        xp = np.log1p(x.clip(lower=0))
        cats = pd.cut(xp, bins=n_bins, labels=False, duplicates="drop")
    else:
        cats = pd.cut(x, bins=n_bins, labels=labels, duplicates="drop")
        if encode == "ordinal" and hasattr(cats, "cat"):
            try:
                cats = cats.cat.codes
            except Exception:
                pass
    out[new_col] = cats
    dist = out[new_col].value_counts(dropna=False).to_dict()
    dist_ser = {str(k): int(v) for k, v in dist.items()}
    return out, {
        "new_column": new_col,
        "bin_edges": custom_edges if strategy == "custom" else None,
        "value_distribution": dist_ser,
        "preview": preview_tail(out),
        "message": "quantize_bins applied",
    }


def log_transform(
    session_id: str,
    columns: List[str],
    base: str = "log10",
    offset: float = 1.0,
    new_suffix: str = "_log",
    replace: bool = False,
    table_name: str = "current",
) -> Dict[str, Any]:
    from .core import run_fe_tool

    return run_fe_tool(
        session_id,
        table_name,
        "log_transform",
        lambda d: log_transform_impl(d, columns, base, offset, new_suffix, replace),
    )


def power_transform(
    session_id: str,
    columns: List[str],
    method: str = "box-cox",
    lmbda: Optional[float] = None,
    standardize: bool = True,
    new_suffix: str = "_power",
    table_name: str = "current",
) -> Dict[str, Any]:
    from .core import run_fe_tool

    # sklearn PowerTransformer estimates lambda; explicit lmbda not wired (use scipy per column if needed)
    return run_fe_tool(
        session_id,
        table_name,
        "power_transform",
        lambda d: power_transform_impl(d, columns, method, lmbda, standardize, new_suffix),
    )


def binarize(
    session_id: str,
    columns: List[str],
    threshold: float = 0.0,
    new_suffix: str = "_binary",
    table_name: str = "current",
) -> Dict[str, Any]:
    from .core import run_fe_tool

    return run_fe_tool(
        session_id,
        table_name,
        "binarize",
        lambda d: binarize_impl(d, columns, threshold, new_suffix),
    )


def quantize_bins(
    session_id: str,
    column: str,
    strategy: str = "uniform",
    n_bins: int = 4,
    custom_edges: Optional[List[float]] = None,
    labels: Optional[List[str]] = None,
    encode: str = "ordinal",
    new_suffix: str = "_binned",
    table_name: str = "current",
) -> Dict[str, Any]:
    from .core import run_fe_tool

    return run_fe_tool(
        session_id,
        table_name,
        "quantize_bins",
        lambda d: quantize_bins_impl(
            d, column, strategy, n_bins, custom_edges, labels, encode, new_suffix
        ),
    )
