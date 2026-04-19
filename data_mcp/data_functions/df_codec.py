"""Versioned DataFrame ↔ base64 codec for the FastAPI ↔ MCP client boundary.

T-5: Apache Arrow IPC is ~5x smaller and ~3x faster to (de)serialize than
pickle for numeric DataFrames; we keep pickle as a fallback for object
columns Arrow can't handle and for backward compatibility with payloads
written before this change.

Wire format (the str returned by `encode_df` / accepted by `decode_df`):
    "AR1:<base64 of Arrow IPC stream>"   ← preferred
    "PK1:<base64 of pickle.dumps(df)>"   ← Arrow conversion fallback
    "<base64 of pickle.dumps(df)>"       ← legacy (no prefix), still accepted

Helpers also expose the dict variant used by the /tables endpoints, so
both producers (`main.py`) and consumers (`http_client.py`) can switch in
lock-step.
"""

from __future__ import annotations

import base64
import logging
import pickle
from typing import Any, Dict

import pandas as pd

logger = logging.getLogger(__name__)

ARROW_PREFIX = "AR1:"
PICKLE_PREFIX = "PK1:"

try:
    import pyarrow as pa  # type: ignore
    import pyarrow.ipc as ipc  # type: ignore
    _ARROW_AVAILABLE = True
except Exception as _e:
    logger.warning("pyarrow unavailable; df_codec will use pickle only: %s", _e)
    pa = None  # type: ignore[assignment]
    ipc = None  # type: ignore[assignment]
    _ARROW_AVAILABLE = False


def _encode_pickle(df: pd.DataFrame) -> str:
    return PICKLE_PREFIX + base64.b64encode(pickle.dumps(df)).decode("utf-8")


def encode_df(df: pd.DataFrame) -> str:
    """Encode a DataFrame to a base64 string, preferring Arrow IPC.

    Falls back to pickle for any frame Arrow can't represent (mixed-type
    object columns, custom extension dtypes, etc).
    """
    if not _ARROW_AVAILABLE:
        return _encode_pickle(df)
    try:
        table = pa.Table.from_pandas(df, preserve_index=True)
        sink = pa.BufferOutputStream()
        with ipc.new_stream(sink, table.schema) as writer:
            writer.write_table(table)
        raw = sink.getvalue().to_pybytes()
        return ARROW_PREFIX + base64.b64encode(raw).decode("utf-8")
    except Exception as e:
        logger.debug("Arrow encode failed (%s); falling back to pickle", e)
        return _encode_pickle(df)


def decode_df(s: str) -> pd.DataFrame:
    """Decode an `encode_df` string. Accepts legacy unprefixed pickle blobs."""
    if not isinstance(s, str):
        raise TypeError(f"decode_df expects str, got {type(s).__name__}")

    if s.startswith(ARROW_PREFIX):
        if not _ARROW_AVAILABLE:
            raise RuntimeError(
                "Received Arrow-encoded payload but pyarrow is not installed"
            )
        raw = base64.b64decode(s[len(ARROW_PREFIX):].encode("utf-8"))
        reader = ipc.open_stream(pa.BufferReader(raw))
        return reader.read_all().to_pandas()

    if s.startswith(PICKLE_PREFIX):
        raw = base64.b64decode(s[len(PICKLE_PREFIX):].encode("utf-8"))
        return pickle.loads(raw)

    # Legacy: no prefix means raw pickle (pre-T-5 payloads)
    raw = base64.b64decode(s.encode("utf-8"))
    obj = pickle.loads(raw)
    if not isinstance(obj, pd.DataFrame):
        raise ValueError(
            f"Legacy payload deserialized to {type(obj).__name__}, expected DataFrame"
        )
    return obj


def encode_table_info(name: str, df: pd.DataFrame) -> Dict[str, Any]:
    """Build the per-table dict shape used by the /tables endpoints."""
    return {
        "table_name": name,
        "data": encode_df(df),
        "row_count": len(df),
        "column_count": len(df.columns),
        "columns": list(df.columns),
        "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
    }
