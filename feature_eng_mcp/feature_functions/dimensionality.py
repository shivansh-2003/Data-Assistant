"""PCA and truncated SVD."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA, TruncatedSVD

from .core import run_fe_tool, preview_tail, store_fit_object, get_fit_object


def apply_pca_impl(
    df: pd.DataFrame,
    columns: Optional[List[str]],
    n_components: Union[int, float] = 0.95,
    whiten: bool = False,
    center: bool = True,
    fit_id: Optional[str] = None,
    transform_id: Optional[str] = None,
    session_id: str = "",
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    num = df.select_dtypes(include=[np.number])
    if columns:
        num = num[[c for c in columns if c in num.columns]]
    X = num.fillna(0).values
    if transform_id and session_id:
        pca = get_fit_object(session_id, transform_id)
        if pca is None:
            raise ValueError("bad transform_id")
    else:
        pca = PCA(
            n_components=n_components,
            whiten=whiten,
            svd_solver="full" if X.shape[1] < X.shape[0] else "auto",
        )
        pca.fit(X)
        if fit_id and session_id:
            store_fit_object(session_id, fit_id, pca)
    Z = pca.transform(X)
    out = df.copy()
    for j in range(Z.shape[1]):
        out[f"pca_{j}"] = Z[:, j]
    evr = pca.explained_variance_ratio_ if hasattr(pca, "explained_variance_ratio_") else []
    return out, {
        "n_components_selected": Z.shape[1],
        "explained_variance_ratios": [float(x) for x in evr],
        "cumulative_variance": float(np.cumsum(evr)[-1]) if len(evr) else 0.0,
        "singular_values": (
            [float(x) for x in pca.singular_values_] if hasattr(pca, "singular_values_") else []
        ),
        "fit_id": fit_id,
        "preview": preview_tail(out),
        "message": "apply_pca",
    }


def apply_truncated_svd_impl(
    df: pd.DataFrame,
    columns: Optional[List[str]],
    n_components: int = 100,
    n_iter: int = 5,
    random_state: Optional[int] = None,
    fit_id: Optional[str] = None,
    transform_id: Optional[str] = None,
    session_id: str = "",
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    num = df.select_dtypes(include=[np.number])
    if columns:
        num = num[[c for c in columns if c in num.columns]]
    X = num.fillna(0).values
    if transform_id and session_id:
        svd = get_fit_object(session_id, transform_id)
        if svd is None:
            raise ValueError("bad transform_id")
    else:
        max_k = max(1, min(X.shape[1] - 1, X.shape[0] - 1)) if X.size else 1
        svd = TruncatedSVD(
            n_components=max(1, min(n_components, max_k)),
            n_iter=n_iter,
            random_state=random_state,
        )
        svd.fit(X)
        if fit_id and session_id:
            store_fit_object(session_id, fit_id, svd)
    Z = svd.transform(X)
    out = df.copy()
    for j in range(Z.shape[1]):
        out[f"svd_{j}"] = Z[:, j]
    evr = svd.explained_variance_ratio_ if hasattr(svd, "explained_variance_ratio_") else []
    return out, {
        "n_components": Z.shape[1],
        "explained_variance_ratios": [float(x) for x in evr],
        "singular_values": [float(x) for x in svd.singular_values_],
        "fit_id": fit_id,
        "preview": preview_tail(out),
        "message": "apply_truncated_svd",
    }


def apply_pca(
    session_id: str,
    columns: Optional[List[str]] = None,
    n_components: Union[int, float] = 0.95,
    whiten: bool = False,
    center: bool = True,
    fit_id: Optional[str] = None,
    transform_id: Optional[str] = None,
    table_name: str = "current",
) -> Dict[str, Any]:
    return run_fe_tool(
        session_id,
        table_name,
        "apply_pca",
        lambda d: apply_pca_impl(
            d, columns, n_components, whiten, center, fit_id, transform_id, session_id
        ),
    )


def apply_truncated_svd(
    session_id: str,
    columns: Optional[List[str]] = None,
    n_components: int = 100,
    n_iter: int = 5,
    random_state: Optional[int] = None,
    fit_id: Optional[str] = None,
    transform_id: Optional[str] = None,
    table_name: str = "current",
) -> Dict[str, Any]:
    return run_fe_tool(
        session_id,
        table_name,
        "apply_truncated_svd",
        lambda d: apply_truncated_svd_impl(
            d, columns, n_components, n_iter, random_state, fit_id, transform_id, session_id
        ),
    )
