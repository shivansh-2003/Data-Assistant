"""
Schema validation against expected column names and coarse dtypes.
"""

from __future__ import annotations

from typing import Any, Dict, List

from .core import get_table_data


def _types_compatible(expected: str, actual: str) -> bool:
    exp = expected.lower().strip()
    actual_lower = actual.lower()
    type_map: Dict[str, List[str]] = {
        "string": ["object", "string", "str", "category"],
        "int": ["int64", "int32", "int16", "int8", "int"],
        "float": ["float64", "float32", "float16", "float"],
        "bool": ["bool"],
        "datetime": ["datetime64", "datetime"],
    }
    allowed = type_map.get(exp, [exp])
    return any(actual_lower.startswith(a) or a in actual_lower for a in allowed)


def validate_schema(
    session_id: str,
    expected_schema: Dict[str, str],
    table_name: str = "current",
) -> Dict[str, Any]:
    """
    Validate table columns and coarse dtypes against expected_schema.
    expected_schema maps column name -> logical type: string, int, float, bool, datetime.
    """
    df = get_table_data(session_id, table_name)
    if df is None:
        return {"success": False, "error": "Table not found", "session_id": session_id}

    expected_cols = set(expected_schema.keys())
    actual_cols = set(df.columns)
    missing_columns = list(expected_cols - actual_cols)
    extra_columns = list(actual_cols - expected_cols)
    type_mismatches: List[Dict[str, str]] = []

    for col, expected_type in expected_schema.items():
        if col not in df.columns:
            continue
        actual_type = str(df[col].dtype)
        if not _types_compatible(expected_type, actual_type):
            type_mismatches.append(
                {"column": col, "expected": expected_type, "actual": actual_type}
            )

    success = len(missing_columns) == 0 and len(type_mismatches) == 0
    return {
        "success": success,
        "session_id": session_id,
        "table_name": table_name,
        "missing_columns": missing_columns,
        "extra_columns": extra_columns,
        "type_mismatches": type_mismatches,
    }
