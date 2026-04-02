"""Categorical encoding and feature hashing."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.preprocessing import OneHotEncoder, OrdinalEncoder, LabelEncoder
from sklearn.feature_extraction import FeatureHasher

from .core import run_fe_tool, preview_tail, store_fit_object, get_fit_object


def encode_categorical_impl(
    df: pd.DataFrame,
    columns: List[str],
    method: str = "onehot",
    drop_first: bool = False,
    handle_unknown: str = "ignore",
    min_frequency: Optional[int] = None,
    max_categories: Optional[int] = None,
    ordinal_mapping: Optional[Dict[str, List[str]]] = None,
    target_column: Optional[str] = None,
    smoothing: float = 1.0,
    fit_id: Optional[str] = None,
    transform_id: Optional[str] = None,
    session_id: str = "",
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    out = df.copy()
    created: List[str] = []
    dropped: List[str] = []
    encoding_mapping: Dict[str, Any] = {}
    method = method.lower()

    if transform_id and session_id:
        state = get_fit_object(session_id, transform_id)
        if state is None:
            raise ValueError("Invalid transform_id")
        # Expect dict col -> target map
        for c, meta in state.items():
            if c not in out.columns:
                continue
            if isinstance(meta, dict) and meta.get("type") == "target_map":
                out[c + "_target"] = (
                    out[c].map(meta["map"]).fillna(meta.get("global_mean", 0))
                )
                created.append(c + "_target")
        return out, {
            "created_columns": created,
            "dropped_columns": dropped,
            "encoding_mapping": {},
            "preview": preview_tail(out),
            "message": "encode_categorical transform",
        }

    if method in ("onehot", "dummy"):
        for c in columns:
            if c not in out.columns:
                continue
            s = out[c].astype(str).fillna("__na__")
            if min_frequency:
                vc = s.value_counts()
                rare = vc[vc < min_frequency].index
                s = s.replace({x: "__other__" for x in rare})
            if max_categories:
                vc = s.value_counts()
                keep = list(vc.nlargest(max_categories - 1).index)
                s = s.where(s.isin(keep), "__other__")
            enc = OneHotEncoder(
                sparse_output=False,
                drop="first" if drop_first or method == "dummy" else None,
                handle_unknown="ignore" if handle_unknown != "error" else "error",
            )
            enc.fit(s.values.reshape(-1, 1))
            arr = enc.transform(s.values.reshape(-1, 1))
            names = enc.get_feature_names_out([c])
            for j, fn in enumerate(names):
                colname = str(fn).replace(" ", "_")
                out[colname] = arr[:, j]
                created.append(colname)
        if fit_id and session_id:
            store_fit_object(session_id, fit_id, {"method": "onehot", "columns": columns})
    elif method == "label":
        for c in columns:
            if c not in out.columns:
                continue
            le = LabelEncoder()
            out[c + "_lbl"] = le.fit_transform(out[c].astype(str).fillna("__na__"))
            created.append(c + "_lbl")
            encoding_mapping[c] = [str(x) for x in le.classes_]
    elif method == "ordinal":
        for c in columns:
            if c not in out.columns:
                continue
            cats = list(ordinal_mapping.get(c, [])) if ordinal_mapping else None
            if cats:
                oe = OrdinalEncoder(
                    categories=[cats],
                    handle_unknown="use_encoded_value",
                    unknown_value=-1,
                )
                oe.fit(np.array(cats).reshape(-1, 1))
                out[c + "_ord"] = oe.transform(
                    out[c].astype(str).values.reshape(-1, 1)
                ).ravel()
            else:
                oe = OrdinalEncoder(
                    handle_unknown="use_encoded_value",
                    unknown_value=-1,
                )
                oe.fit(out[[c]].astype(str))
                out[c + "_ord"] = oe.transform(out[[c]].astype(str)).ravel()
            created.append(c + "_ord")
    elif method == "frequency":
        for c in columns:
            if c not in out.columns:
                continue
            s = out[c].astype(str)
            if min_frequency:
                vc = s.value_counts()
                rare = vc[vc < min_frequency].index
                s = s.replace({x: "__other__" for x in rare})
            out[c + "_freq"] = s.map(s.value_counts())
            created.append(c + "_freq")
    elif method == "target":
        if not target_column or target_column not in out.columns:
            raise ValueError("target_column required for target encoding")
        y = pd.to_numeric(out[target_column], errors="coerce")
        global_mean = float(np.nanmean(y.values))
        store_maps: Dict[str, Any] = {}
        for c in columns:
            if c not in out.columns:
                continue
            tmp = out[[c, target_column]].copy()
            tmp["_y"] = pd.to_numeric(tmp[target_column], errors="coerce")
            agg = tmp.groupby(c, dropna=False)["_y"].mean()
            counts = tmp.groupby(c, dropna=False).size()
            smoothed = (agg * counts + global_mean * smoothing) / (counts + smoothing)
            out[c + "_target"] = out[c].map(smoothed).fillna(global_mean)
            created.append(c + "_target")
            store_maps[c] = {
                "type": "target_map",
                "map": smoothed.to_dict(),
                "global_mean": global_mean,
            }
        if fit_id and session_id:
            store_fit_object(session_id, fit_id, store_maps)
    elif method == "effect":
        raise NotImplementedError("effect coding not implemented in v0.1")
    elif method == "binary":
        raise NotImplementedError("binary encoding not implemented in v0.1")
    else:
        raise ValueError(f"Unknown encoding method: {method}")

    return out, {
        "created_columns": created,
        "dropped_columns": dropped,
        "encoding_mapping": encoding_mapping,
        "fit_id": fit_id,
        "preview": preview_tail(out),
        "message": f"encode_categorical ({method})",
    }


def feature_hash_impl(
    df: pd.DataFrame,
    columns: List[str],
    n_features: int = 256,
    alternate_sign: bool = True,
    input_type: str = "string",
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    out = df.copy()
    hasher = FeatureHasher(
        n_features=n_features, alternate_sign=alternate_sign, input_type=input_type
    )
    X_raw = []
    card = 0
    for _, row in df[columns].astype(str).iterrows():
        d = {str(k): str(v) for k, v in row.items()}
        X_raw.append(d)
        card += len(set(row.values))
    M = hasher.transform(X_raw).toarray()
    created: List[str] = []
    for j in range(M.shape[1]):
        name = f"hash_{j}"
        out[name] = M[:, j]
        created.append(name)
    return out, {
        "original_cardinality": card,
        "hashed_dimensions": n_features,
        "collision_estimate": "see hashing trick literature",
        "created_columns": created,
        "preview": preview_tail(out),
        "message": "feature_hash",
    }


def encode_categorical(
    session_id: str,
    columns: List[str],
    method: str = "onehot",
    drop_first: bool = False,
    handle_unknown: str = "ignore",
    min_frequency: Optional[int] = None,
    max_categories: Optional[int] = None,
    ordinal_mapping: Optional[Dict[str, List[str]]] = None,
    target_column: Optional[str] = None,
    smoothing: float = 1.0,
    fit_id: Optional[str] = None,
    transform_id: Optional[str] = None,
    table_name: str = "current",
) -> Dict[str, Any]:
    return run_fe_tool(
        session_id,
        table_name,
        "encode_categorical",
        lambda d: encode_categorical_impl(
            d,
            columns,
            method,
            drop_first,
            handle_unknown,
            min_frequency,
            max_categories,
            ordinal_mapping,
            target_column,
            smoothing,
            fit_id,
            transform_id,
            session_id,
        ),
    )


def feature_hash(
    session_id: str,
    columns: List[str],
    n_features: int = 256,
    alternate_sign: bool = True,
    input_type: str = "string",
    table_name: str = "current",
) -> Dict[str, Any]:
    return run_fe_tool(
        session_id,
        table_name,
        "feature_hash",
        lambda d: feature_hash_impl(d, columns, n_features, alternate_sign, input_type),
    )

