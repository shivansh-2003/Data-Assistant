"""Serializer for DataFrame dicts stored in Redis.

R-3: Replaces the original whole-dict pickle blob with an Arrow IPC stream
per DataFrame, fronted by a magic header so the deserializer can detect the
format. Pickle is kept as a per-frame fallback (for object columns Arrow
can't represent) and as the global fallback when a stored blob predates
this change.

Wire format
-----------
    b"AR1\\0" + uint32(n_tables) +
        for each table:
            uint32(name_len) | utf8(name) |
            uint8(table_kind)            # 0 = arrow IPC, 1 = pickle
            uint32(payload_len) | payload_bytes

Anything that doesn't start with the b"AR1\\0" magic is treated as a legacy
pickle blob and decoded with `pickle.loads`. New writes always use the
Arrow-first path; over a 30-day TTL window all stored entries upgrade
naturally.
"""

from __future__ import annotations

import logging
import pickle
import struct
from typing import Dict, Optional

import pandas as pd

logger = logging.getLogger(__name__)

# 4-byte magic so length-prefixed table count starts on a known offset
_MAGIC = b"AR1\x00"

_KIND_ARROW = 0
_KIND_PICKLE = 1

try:
    import pyarrow as pa  # type: ignore
    import pyarrow.ipc as ipc  # type: ignore
    _ARROW_AVAILABLE = True
except Exception as _e:
    logger.warning(
        "pyarrow unavailable; redis serializer will fall back to pickle: %s", _e
    )
    pa = None  # type: ignore[assignment]
    ipc = None  # type: ignore[assignment]
    _ARROW_AVAILABLE = False


def _encode_one(df: pd.DataFrame) -> tuple[int, bytes]:
    """Return (kind, payload) for a single DataFrame."""
    if not _ARROW_AVAILABLE:
        return _KIND_PICKLE, pickle.dumps(df, protocol=pickle.HIGHEST_PROTOCOL)
    try:
        table = pa.Table.from_pandas(df, preserve_index=True)
        sink = pa.BufferOutputStream()
        with ipc.new_stream(sink, table.schema) as writer:
            writer.write_table(table)
        return _KIND_ARROW, sink.getvalue().to_pybytes()
    except Exception as e:
        logger.debug("Arrow encode failed for table; using pickle: %s", e)
        return _KIND_PICKLE, pickle.dumps(df, protocol=pickle.HIGHEST_PROTOCOL)


def _decode_one(kind: int, payload: bytes) -> pd.DataFrame:
    if kind == _KIND_ARROW:
        if not _ARROW_AVAILABLE:
            raise RuntimeError(
                "Stored payload is Arrow-encoded but pyarrow is not installed"
            )
        reader = ipc.open_stream(pa.BufferReader(payload))
        return reader.read_all().to_pandas()
    if kind == _KIND_PICKLE:
        return pickle.loads(payload)
    raise ValueError(f"Unknown serializer table kind: {kind}")


class DataFrameSerializer:
    """Encode/decode `dict[str, pd.DataFrame]` for Redis storage.

    Backward compatible: blobs written by the previous all-pickle implementation
    are detected by the absence of the magic header and decoded with pickle.
    """

    def __init__(self, protocol: int = pickle.HIGHEST_PROTOCOL):
        self.protocol = protocol

    # ── encode ────────────────────────────────────────────────────────────
    def serialize(self, tables: Dict[str, pd.DataFrame]) -> bytes:
        try:
            if not _ARROW_AVAILABLE:
                # No Arrow runtime — fall through to the legacy whole-dict
                # pickle so we don't tag bytes with a header we can't honor.
                return pickle.dumps(tables, protocol=self.protocol)

            parts: list[bytes] = [_MAGIC, struct.pack(">I", len(tables))]
            for name, df in tables.items():
                name_bytes = name.encode("utf-8")
                kind, payload = _encode_one(df)
                parts.append(struct.pack(">I", len(name_bytes)))
                parts.append(name_bytes)
                parts.append(struct.pack(">B", kind))
                parts.append(struct.pack(">I", len(payload)))
                parts.append(payload)
            return b"".join(parts)
        except Exception as e:
            logger.error("Serialization failed (Arrow path): %s — falling back to pickle", e)
            try:
                return pickle.dumps(tables, protocol=self.protocol)
            except Exception:
                logger.error("Pickle fallback also failed", exc_info=True)
                raise

    # ── decode ────────────────────────────────────────────────────────────
    def deserialize(self, blob: Optional[bytes]) -> Dict[str, pd.DataFrame]:
        if blob is None:
            return {}
        try:
            if not blob.startswith(_MAGIC):
                # Legacy: the whole-dict pickle written before R-3
                return pickle.loads(blob)

            offset = len(_MAGIC)
            (n_tables,) = struct.unpack_from(">I", blob, offset)
            offset += 4

            out: Dict[str, pd.DataFrame] = {}
            for _ in range(n_tables):
                (name_len,) = struct.unpack_from(">I", blob, offset)
                offset += 4
                name = blob[offset : offset + name_len].decode("utf-8")
                offset += name_len
                (kind,) = struct.unpack_from(">B", blob, offset)
                offset += 1
                (payload_len,) = struct.unpack_from(">I", blob, offset)
                offset += 4
                payload = blob[offset : offset + payload_len]
                offset += payload_len
                out[name] = _decode_one(kind, payload)
            return out
        except Exception as e:
            logger.error("Deserialization failed: %s", e)
            raise
