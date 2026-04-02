"""K-means featurization."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

from .core import run_fe_tool, preview_tail, store_fit_object, get_fit_object


def kmeans_featurize_impl(
    df: pd.DataFrame,
    columns: List[str],
    n_clusters: int = 8,
    output_type: str = "soft",
    scale_first: bool = True,
    random_state: Optional[int] = None,
    n_init: int = 10,
    max_iter: int = 300,
    fit_id: Optional[str] = None,
    transform_id: Optional[str] = None,
    session_id: str = "",
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    cols = [c for c in columns if c in df.columns]
    Xraw = df[cols].apply(pd.to_numeric, errors="coerce").fillna(0).values
    if scale_first:
        X = StandardScaler().fit_transform(Xraw)
    else:
        X = Xraw
    if transform_id and session_id:
        km = get_fit_object(session_id, transform_id)
        if km is None:
            raise ValueError("bad transform_id")
    else:
        km = KMeans(
            n_clusters=n_clusters,
            random_state=random_state,
            n_init=n_init,
            max_iter=max_iter,
        )
        km.fit(X)
        if fit_id and session_id:
            store_fit_object(session_id, fit_id, km)
    out = df.copy()
    created: List[str] = []
    if output_type in ("hard", "both"):
        labels = km.predict(X)
        out["kmeans_cluster"] = labels
        created.append("kmeans_cluster")
    if output_type in ("soft", "both"):
        dists = np.linalg.norm(X[:, None, :] - km.cluster_centers_[None, :, :], axis=2)
        for k in range(dists.shape[1]):
            name = f"kmeans_dist_{k}"
            out[name] = dists[:, k]
            created.append(name)
    pred = km.predict(X)
    sizes = pd.Series(pred).value_counts().to_dict()
    return out, {
        "created_columns": created,
        "cluster_sizes": {str(k): int(v) for k, v in sizes.items()},
        "inertia": float(km.inertia_) if hasattr(km, "inertia_") else None,
        "fit_id": fit_id,
        "preview": preview_tail(out),
        "message": "kmeans_featurize",
    }


def kmeans_featurize(
    session_id: str,
    columns: List[str],
    n_clusters: int = 8,
    output_type: str = "soft",
    scale_first: bool = True,
    random_state: Optional[int] = None,
    n_init: int = 10,
    max_iter: int = 300,
    fit_id: Optional[str] = None,
    transform_id: Optional[str] = None,
    table_name: str = "current",
) -> Dict[str, Any]:
    return run_fe_tool(
        session_id,
        table_name,
        "kmeans_featurize",
        lambda d: kmeans_featurize_impl(
            d,
            columns,
            n_clusters,
            output_type,
            scale_first,
            random_state,
            n_init,
            max_iter,
            fit_id,
            transform_id,
            session_id,
        ),
    )
