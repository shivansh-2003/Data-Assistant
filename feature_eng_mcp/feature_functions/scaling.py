"""Feature scaling with fit/transform persistence."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.preprocessing import (
    StandardScaler,
    MinMaxScaler,
    RobustScaler,
    MaxAbsScaler,
    Normalizer,
)

from .core import run_fe_tool, store_fit_object, get_fit_object, preview_tail


def _make_scaler(method: str, feature_range, with_centering: bool):
    m = method.lower()
    if m == "standard":
        return StandardScaler()
    if m == "minmax":
        return MinMaxScaler(feature_range=feature_range)
    if m == "robust":
        return RobustScaler(with_centering=with_centering, with_scaling=True)
    if m == "maxabs":
        return MaxAbsScaler()
    if m == "l2":
        return Normalizer(norm="l2")
    return StandardScaler()


def scale_features_impl(
    df: pd.DataFrame,
    columns: List[str],
    method: str = "standard",
    feature_range: Tuple[float, float] = (0, 1),
    with_centering: bool = True,
    fit_id: Optional[str] = None,
    transform_id: Optional[str] = None,
    session_id: str = "",
    new_suffix: str = "",
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    out = df.copy()
    cols = [c for c in columns if c in out.columns]
    if not cols:
        raise ValueError("No valid columns to scale")
    X = out[cols].apply(pd.to_numeric, errors="coerce")

    scaler = None
    if transform_id and session_id:
        blob = get_fit_object(session_id, transform_id)
        if blob is None:
            raise ValueError(f"No fitted params for transform_id={transform_id}")
        scaler = blob
    else:
        scaler = _make_scaler(method, feature_range, with_centering)
        scaler.fit(X.values)
        if fit_id and session_id:
            store_fit_object(session_id, fit_id, scaler)

    Xt = scaler.transform(X.values)
    fitted_params = {}
    for i, c in enumerate(cols):
        if hasattr(scaler, "mean_"):
            fitted_params[c] = {
                "mean": float(scaler.mean_[i]) if scaler.mean_ is not None else None,
                "scale": float(scaler.scale_[i]) if hasattr(scaler, "scale_") else None,
            }
        elif hasattr(scaler, "data_min_"):
            fitted_params[c] = {
                "min": float(scaler.data_min_[i]),
                "max": float(scaler.data_max_[i]),
            }

    for i, c in enumerate(cols):
        if new_suffix:
            out[f"{c}{new_suffix}"] = Xt[:, i]
        else:
            out[c] = Xt[:, i]

    scaled_names = [f"{c}{new_suffix}" if new_suffix else c for c in cols]
    meta: Dict[str, Any] = {
        "scaled_columns": scaled_names,
        "fitted_params": fitted_params,
        "fit_id": fit_id,
        "preview": preview_tail(out),
        "message": "scale_features applied",
    }
    if fit_id:
        meta["fit_id"] = fit_id
    return out, meta


def scale_features(
    session_id: str,
    columns: List[str],
    method: str = "standard",
    feature_range: Tuple[float, float] = (0, 1),
    with_centering: bool = True,
    fit_id: Optional[str] = None,
    transform_id: Optional[str] = None,
    new_suffix: str = "",
    table_name: str = "current",
) -> Dict[str, Any]:
    return run_fe_tool(
        session_id,
        table_name,
        "scale_features",
        lambda d: scale_features_impl(
            d,
            columns,
            method,
            feature_range,
            with_centering,
            fit_id,
            transform_id,
            session_id,
            new_suffix,
        ),
    )
