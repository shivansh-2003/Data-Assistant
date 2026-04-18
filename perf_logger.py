"""
perf_logger.py — DEPRECATED stub.

Latency benchmarks and timing helpers are now inlined into each module
(app.py, mcp_client.py, main.py, redis_store.py, core.py, http_client.py).
This file exists only so any stale import does not raise ImportError.
"""
import logging
import contextlib
from typing import Any

# Backward-compat aliases — these are harmless no-ops
perf_logger = logging.getLogger("perf")
BENCHMARKS: dict[str, float] = {}


@contextlib.contextmanager
def perf_timer(name: str, session_id: str = "", **extra: Any):
    """No-op stub — use the module-level logger directly instead."""
    yield
