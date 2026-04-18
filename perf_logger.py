"""
Shared latency instrumentation utility.

Usage
-----
    from perf_logger import perf_timer, BENCHMARKS

    with perf_timer("redis.load_session", session_id=sid, extra="info"):
        tables = store.load_session(sid)

Every block emits one INFO line on exit.
If the measured time exceeds the benchmark threshold a WARN line follows.

Set env var  PERF_LOG_LEVEL=DEBUG  to also emit sub-ms timings.
"""

from __future__ import annotations

import logging
import os
import time
from contextlib import contextmanager
from typing import Any

_logger = logging.getLogger("perf")
perf_logger = _logger  # public alias for app / call-site logging

# ---------------------------------------------------------------------------
# Benchmark thresholds (seconds)
# These are the *expected* ceilings for each operation.
# Operations that exceed them are flagged SLOW in logs.
# ---------------------------------------------------------------------------
BENCHMARKS: dict[str, float] = {
    # ── app.py ──────────────────────────────────────────────────────────
    "app.analyze_data_sync":        15.0,   # LLM call — 15 s is the hard ceiling
    "app.analyze_data_sync.llm":    12.0,   # pure LLM inference portion
    "app.post_op.cache_clear":       0.05,  # just Python dict operations
    "app.post_op.save_version_http": 1.50,  # one HTTP POST to FastAPI
    "app.branch_http":               1.00,  # one HTTP POST to /branch
    # ── mcp_client.py ───────────────────────────────────────────────────
    "mcp.agent_create":              2.00,  # MCP connect + tool fetch + LLM init
    "mcp.tool_fetch":                0.80,  # just tool discovery from MCP server
    "mcp.llm_invoke":               12.00,  # agent.ainvoke — mostly OpenAI latency
    # ── main.py (FastAPI endpoints) ─────────────────────────────────────
    "api.save_version":              1.00,  # snapshot + graph update
    "api.save_version.snapshot":     0.30,  # Redis COPY (or fallback serialize)
    "api.save_version.update_graph": 0.50,  # graph read-modify-write
    "api.branch":                    0.50,  # restore version + set current
    "api.branch.restore":            0.30,  # Redis COPY (or fallback)
    # ── redis_store.py ──────────────────────────────────────────────────
    "redis.save_session":            0.50,  # serialize + Upstash REST SET
    "redis.save_session.serialize":  0.15,  # pickle / parquet only
    "redis.save_session.redis_set":  0.30,  # Upstash REST round-trip
    "redis.load_session":            0.50,  # Upstash REST GET + deserialize
    "redis.load_session.redis_get":  0.30,
    "redis.load_session.deserialize":0.15,
    "redis.save_version":            0.50,
    "redis.load_version":            0.50,
    "redis.snapshot_copy":           0.10,  # server-side COPY — should be very fast
    "redis.restore_copy":            0.10,
    "redis.update_graph":            0.40,
    "redis.extend_ttl":              0.20,
    # ── http_client.py ──────────────────────────────────────────────────
    "http.load_tables":              1.00,  # GET + deserialize
    "http.load_tables.http":         0.60,
    "http.load_tables.deserialize":  0.20,
    "http.save_tables":              1.20,  # serialize + PUT
    "http.save_tables.serialize":    0.20,
    "http.save_tables.http":         0.80,
    # ── core.py ─────────────────────────────────────────────────────────
    "core.get_session_state":        1.00,
    "core.save_session_state":       1.20,
}

_SLOW_THRESHOLD_MULTIPLIER = 1.0   # flag if time > 1× benchmark


@contextmanager
def perf_timer(name: str, session_id: str = "", **extra: Any):
    """
    Context-manager that logs entry time and duration of a code block.

    Parameters
    ----------
    name       : dotted operation name, matched against BENCHMARKS
    session_id : used in log line for easy grep
    **extra    : any additional key=value pairs appended to the log line
    """
    t0 = time.perf_counter()
    try:
        yield
    finally:
        elapsed = time.perf_counter() - t0
        threshold = BENCHMARKS.get(name)

        extra_str = "  ".join(f"{k}={v}" for k, v in extra.items()) if extra else ""
        sid_str   = f"session={session_id}  " if session_id else ""

        _logger.info(
            "[PERF] %-40s  %s%s%.3fs",
            name,
            sid_str,
            (extra_str + "  ") if extra_str else "",
            elapsed,
        )

        if threshold is not None and elapsed > threshold * _SLOW_THRESHOLD_MULTIPLIER:
            _logger.warning(
                "[PERF][SLOW] %-40s  %s%.3fs elapsed  (benchmark: %.3fs  |  %.1f× over)",
                name,
                sid_str,
                elapsed,
                threshold,
                elapsed / threshold,
            )
