"""Bag-of-words, TF-IDF, and simple text stats."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer

from .core import run_fe_tool, preview_tail, store_fit_object


def text_to_bow_impl(
    df: pd.DataFrame,
    text_column: str,
    max_features: Optional[int] = None,
    min_df: float = 1,
    max_df: float = 1.0,
    ngram_range: Tuple[int, int] = (1, 1),
    binary: bool = False,
    stop_words: Optional[str] = "english",
    lowercase: bool = True,
    token_pattern: str = r"(?u)\b\w\w+\b",
    output_format: str = "dense_table",
    fit_id: Optional[str] = None,
    session_id: str = "",
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    if text_column not in df.columns:
        raise ValueError(f"Column {text_column} not found")
    cv = CountVectorizer(
        max_features=max_features,
        min_df=min_df,
        max_df=max_df,
        ngram_range=ngram_range,
        binary=binary,
        stop_words=stop_words,
        lowercase=lowercase,
        token_pattern=token_pattern,
    )
    corpus = df[text_column].fillna("").astype(str)
    X = cv.fit_transform(corpus)
    if fit_id and session_id:
        store_fit_object(session_id, fit_id, cv)
    names = cv.get_feature_names_out()
    out = df.copy()
    if output_format == "sparse_table":
        # still materialize dense for Streamlit/session compatibility
        pass
    arr = X.toarray()
    max_cols = 200
    for j in range(min(arr.shape[1], max_cols)):
        out[f"bow_{names[j]}"] = arr[:, j]
    sparsity = 1.0 - (X.nnz / (X.shape[0] * X.shape[1])) if X.shape[1] else 0.0
    created = [f"bow_{names[j]}" for j in range(min(arr.shape[1], max_cols))]
    return out, {
        "vocabulary_size": len(names),
        "feature_names_sample": list(names[:20]),
        "sparsity_percentage": round(100 * sparsity, 2),
        "fit_id": fit_id,
        "created_columns": created,
        "preview": preview_tail(out),
        "message": "text_to_bow",
    }


def text_to_tfidf_impl(
    df: pd.DataFrame,
    text_column: str,
    max_features: Optional[int] = None,
    min_df: float = 1,
    max_df: float = 1.0,
    ngram_range: Tuple[int, int] = (1, 1),
    sublinear_tf: bool = True,
    norm: str = "l2",
    use_idf: bool = True,
    smooth_idf: bool = True,
    stop_words: Optional[str] = "english",
    fit_id: Optional[str] = None,
    session_id: str = "",
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    if text_column not in df.columns:
        raise ValueError(f"Column {text_column} not found")
    tv = TfidfVectorizer(
        max_features=max_features,
        min_df=min_df,
        max_df=max_df,
        ngram_range=ngram_range,
        sublinear_tf=sublinear_tf,
        norm=norm,
        use_idf=use_idf,
        smooth_idf=smooth_idf,
        stop_words=stop_words,
    )
    corpus = df[text_column].fillna("").astype(str)
    X = tv.fit_transform(corpus)
    if fit_id and session_id:
        store_fit_object(session_id, fit_id, tv)
    names = tv.get_feature_names_out()
    arr = X.toarray()
    max_cols = 200
    out = df.copy()
    for j in range(min(arr.shape[1], max_cols)):
        out[f"tfidf_{names[j]}"] = arr[:, j]
    idf = tv.idf_ if hasattr(tv, "idf_") and tv.idf_ is not None else np.array([])
    idf_stats = {
        "min": float(idf.min()) if len(idf) else None,
        "max": float(idf.max()) if len(idf) else None,
        "mean": float(idf.mean()) if len(idf) else None,
    }
    created = [f"tfidf_{names[j]}" for j in range(min(arr.shape[1], max_cols))]
    return out, {
        "vocabulary_size": len(names),
        "idf_stats": idf_stats,
        "fit_id": fit_id,
        "created_columns": created,
        "preview": preview_tail(out),
        "message": "text_to_tfidf",
    }


def extract_text_stats_impl(
    df: pd.DataFrame,
    text_column: str,
    features: Optional[List[str]] = None,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    if text_column not in df.columns:
        raise ValueError(f"Column {text_column} not found")
    if features is None:
        features = [
            "word_count",
            "char_count",
            "avg_word_length",
            "digit_ratio",
        ]
    out = df.copy()
    s = df[text_column].fillna("").astype(str)
    created = []
    if "word_count" in features:
        out[text_column + "_word_count"] = s.str.split().str.len()
        created.append(text_column + "_word_count")
    if "char_count" in features:
        out[text_column + "_char_count"] = s.str.len()
        created.append(text_column + "_char_count")
    if "avg_word_length" in features:
        wc = s.str.split().str.len().replace(0, np.nan)
        out[text_column + "_avg_word_length"] = s.str.len() / wc
        created.append(text_column + "_avg_word_length")
    if "digit_ratio" in features:
        out[text_column + "_digit_ratio"] = s.str.count(r"\d") / s.str.len().replace(0, np.nan)
        created.append(text_column + "_digit_ratio")
    return out, {
        "created_columns": created,
        "preview": preview_tail(out),
        "message": "extract_text_stats",
    }


def text_to_bow(
    session_id: str,
    text_column: str,
    max_features: Optional[int] = 500,
    min_df: float = 1,
    max_df: float = 1.0,
    ngram_range: Tuple[int, int] = (1, 1),
    binary: bool = False,
    stop_words: Optional[str] = "english",
    lowercase: bool = True,
    token_pattern: str = r"(?u)\b\w\w+\b",
    output_format: str = "dense_table",
    fit_id: Optional[str] = None,
    table_name: str = "current",
) -> Dict[str, Any]:
    return run_fe_tool(
        session_id,
        table_name,
        "text_to_bow",
        lambda d: text_to_bow_impl(
            d,
            text_column,
            max_features,
            min_df,
            max_df,
            ngram_range,
            binary,
            stop_words,
            lowercase,
            token_pattern,
            output_format,
            fit_id,
            session_id,
        ),
    )


def text_to_tfidf(
    session_id: str,
    text_column: str,
    max_features: Optional[int] = 500,
    min_df: float = 1,
    max_df: float = 1.0,
    ngram_range: Tuple[int, int] = (1, 1),
    sublinear_tf: bool = True,
    norm: str = "l2",
    use_idf: bool = True,
    smooth_idf: bool = True,
    stop_words: Optional[str] = "english",
    fit_id: Optional[str] = None,
    table_name: str = "current",
) -> Dict[str, Any]:
    return run_fe_tool(
        session_id,
        table_name,
        "text_to_tfidf",
        lambda d: text_to_tfidf_impl(
            d,
            text_column,
            max_features,
            min_df,
            max_df,
            ngram_range,
            sublinear_tf,
            norm,
            use_idf,
            smooth_idf,
            stop_words,
            fit_id,
            session_id,
        ),
    )


def extract_text_stats(
    session_id: str,
    text_column: str,
    features: Optional[List[str]] = None,
    table_name: str = "current",
) -> Dict[str, Any]:
    return run_fe_tool(
        session_id,
        table_name,
        "extract_text_stats",
        lambda d: extract_text_stats_impl(d, text_column, features),
    )
