"""Multi-step feature pipelines."""

from __future__ import annotations

from typing import Any, Dict, List

from .core import save_pipeline_spec, get_pipeline_spec


def _tool_registry():
    from . import (
        numeric_transforms,
        scaling,
        interaction,
        categorical,
        text_features,
        dimensionality,
        clustering_features,
        datetime_features,
        feature_selection,
    )

    return {
        "log_transform": numeric_transforms.log_transform,
        "power_transform": numeric_transforms.power_transform,
        "binarize": numeric_transforms.binarize,
        "quantize_bins": numeric_transforms.quantize_bins,
        "scale_features": scaling.scale_features,
        "create_polynomial_features": interaction.create_polynomial_features,
        "create_ratio_features": interaction.create_ratio_features,
        "encode_categorical": categorical.encode_categorical,
        "feature_hash": categorical.feature_hash,
        "text_to_bow": text_features.text_to_bow,
        "text_to_tfidf": text_features.text_to_tfidf,
        "extract_text_stats": text_features.extract_text_stats,
        "select_by_variance": feature_selection.select_by_variance,
        "select_by_correlation": feature_selection.select_by_correlation,
        "select_by_mutual_info": feature_selection.select_by_mutual_info,
        "apply_pca": dimensionality.apply_pca,
        "apply_truncated_svd": dimensionality.apply_truncated_svd,
        "kmeans_featurize": clustering_features.kmeans_featurize,
        "create_advanced_date_features": datetime_features.create_advanced_date_features,
        "create_time_since_features": datetime_features.create_time_since_features,
    }


def _run_steps(
    session_id: str,
    steps: List[Dict[str, Any]],
    table_name: str,
) -> Dict[str, Any]:
    reg = _tool_registry()
    completed = 0
    result: Dict[str, Any] = {}
    if not steps:
        return {"success": False, "error": "steps list is empty", "steps_completed": 0}
    for step in steps:
        tool = step.get("tool")
        params = dict(step.get("params", {}))
        if tool not in reg:
            return {
                "success": False,
                "error": f"Unknown tool: {tool}",
                "steps_completed": completed,
            }
        params.setdefault("session_id", session_id)
        params.setdefault("table_name", table_name)
        result = reg[tool](**params)
        completed += 1
        if not result.get("success", True):
            result["steps_completed"] = completed - 1
            return result
    return {
        "success": True,
        "steps_completed": completed,
        "last_step_preview": result.get("preview"),
        "message": f"Completed {completed} steps",
    }


def create_feature_pipeline(
    session_id: str,
    steps: List[Dict[str, Any]],
    pipeline_id: str,
    table_name: str = "current",
) -> Dict[str, Any]:
    out = _run_steps(session_id, steps, table_name)
    out["pipeline_id"] = pipeline_id
    if out.get("success"):
        save_pipeline_spec(pipeline_id, steps, session_id)
    return out


def apply_saved_pipeline(
    session_id: str,
    pipeline_id: str,
    table_name: str = "current",
) -> Dict[str, Any]:
    spec = get_pipeline_spec(pipeline_id)
    if not spec:
        return {
            "success": False,
            "error": f"Unknown pipeline_id: {pipeline_id}",
        }
    steps = spec.get("steps", [])
    out = _run_steps(session_id, steps, table_name)
    out["pipeline_id"] = pipeline_id
    out["replayed"] = True
    return out
