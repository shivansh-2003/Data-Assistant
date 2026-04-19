"""
MCP Client using LangChain MCP Adapters.
Connects to the Data Assistant MCP Server and uses OpenAI GPT-5.1 for data manipulation.
"""

import asyncio
import hashlib
import json
import logging
import os
import pathlib
import threading
import time as _time
from typing import Any, AsyncIterator, Dict, List, Tuple

import httpx
from langchain.agents import create_agent
from langchain_core.callbacks import BaseCallbackHandler
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_openai import ChatOpenAI
from langfuse import observe

from observability.langfuse_client import build_langchain_callback, update_trace_context
from redis_db import get_session_store
from model_routing import select_main_or_mini_tier

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
_base = os.getenv("FASTAPI_URL", "http://127.0.0.1:8000").rstrip("/")
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", f"{_base}/data/mcp")
INGESTION_API_URL = os.getenv("INGESTION_API_URL", _base)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MAIN_MODEL = os.getenv("MAIN_MODEL", os.getenv("MCP_MAIN_MODEL", "gpt-5"))
MINI_MODEL = os.getenv("MINI_MODEL", os.getenv("MCP_MINI_MODEL", "gpt-5-mini-2025-08-07"))

# ---------------------------------------------------------------------------
# Per-operation latency ceilings (seconds) — exceeded → WARNING in logs.
# ---------------------------------------------------------------------------
_BENCHMARKS: dict[str, float] = {
    "mcp.agent_create": 2.00,
    "mcp.tool_fetch":   0.80,
    "mcp.llm_invoke":  12.00,
}

# T-3 transform-result cache. Key includes the session's current_version so a
# successful save_version naturally invalidates stale entries (no explicit
# purge needed). Keep TTL short so abandoned/error states age out cleanly.
TRANSFORM_CACHE_TTL = int(os.getenv("MCP_TRANSFORM_CACHE_TTL", "900"))  # 15 min
TRANSFORM_CACHE_ENABLED = os.getenv("MCP_TRANSFORM_CACHE", "1") not in ("0", "false", "False")


def _transform_cache_key(session_id: str, query: str, version: str) -> str:
    raw = f"{session_id}|{query.strip().lower()}|{version}"
    return f"transform_cache:{hashlib.md5(raw.encode()).hexdigest()}"


# ---------------------------------------------------------------------------
# T-4: tool discovery snapshot. We can't reconstruct LangChain Tool objects
# from raw JSON without reimplementing the MCP adapter, so the cache only
# records the tool name list + server health for fast freshness checks; the
# actual agent is warmed in a background thread at app startup so the first
# user query finds it ready.
# ---------------------------------------------------------------------------
TOOL_CACHE_PATH = pathlib.Path(
    os.getenv(
        "MCP_TOOL_CACHE_PATH",
        str(pathlib.Path.home() / ".cache" / "data-assistant" / "mcp_tools.json"),
    )
)
TOOL_CACHE_TTL_SEC = int(os.getenv("MCP_TOOL_CACHE_TTL", "3600"))  # 1h


def _read_tool_snapshot() -> dict:
    """Return persisted snapshot or {} if missing/stale/corrupt."""
    try:
        if not TOOL_CACHE_PATH.exists():
            return {}
        age = _time.time() - TOOL_CACHE_PATH.stat().st_mtime
        if age > TOOL_CACHE_TTL_SEC:
            logger.info(
                "[MCP] tool snapshot stale (age=%.0fs > %ds); will rediscover",
                age, TOOL_CACHE_TTL_SEC,
            )
            return {}
        return json.loads(TOOL_CACHE_PATH.read_text())
    except Exception as e:
        logger.debug("tool snapshot read failed: %s", e)
        return {}


def _write_tool_snapshot(server_url: str, tool_names: List[str]) -> None:
    try:
        TOOL_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "server_url": server_url,
            "tool_names": tool_names,
            "captured_at": _time.time(),
            "healthy": True,
        }
        TOOL_CACHE_PATH.write_text(json.dumps(payload, indent=2))
    except Exception as e:
        logger.debug("tool snapshot write failed: %s", e)


def warmup_agent_in_background(model: str = "") -> None:
    """Fire-and-forget agent warmup. Safe to call from sync code at startup.

    The first user query then finds a hot agent (no `mcp.tool_fetch` on the
    user-facing path). Idempotent: a second call is a near-instant no-op
    because `_get_or_create_agent` already returns the cached entry.
    """
    target_model = model or MAIN_MODEL

    def _runner() -> None:
        try:
            asyncio.run(_get_or_create_agent(model=target_model))
            logger.info("[MCP] background warmup complete  model=%s", target_model)
        except Exception as e:
            logger.warning("[MCP] background warmup failed: %s", e)

    threading.Thread(target=_runner, name="mcp-warmup", daemon=True).start()


def _perf_warn(name: str, elapsed: float, sid: str = "") -> None:
    """Emit a SLOW warning when elapsed exceeds the benchmark for `name`."""
    threshold = _BENCHMARKS.get(name)
    if threshold and elapsed > threshold:
        logger.warning(
            "[PERF][SLOW] %-40s  session=%s  %.3fs elapsed  (benchmark: %.3fs  |  %.1fx over)",
            name, sid, elapsed, threshold, elapsed / threshold,
        )


# ---------------------------------------------------------------------------
# Query-complexity tiers for model routing (see context/MODEL_STRATEGY.md §4)
# ---------------------------------------------------------------------------
def _select_model(query: str) -> str:
    """Route query to MAIN_MODEL or MINI_MODEL based on complexity tier."""
    return MINI_MODEL if select_main_or_mini_tier(query) == "mini" else MAIN_MODEL


# ---------------------------------------------------------------------------
# Agent system prompt
# ---------------------------------------------------------------------------
# T-6: kept fully static and front-loaded so OpenAI's 1024-token prompt cache
# can latch onto it across requests (this also benefits the cache work from
# the previous tier-1 rollout). All variable parts (session_id, query) are
# injected via the user message in `analyze_data`, never the system prompt.
AGENT_SYSTEM_MESSAGE = """You are a data analysis assistant. You help users manipulate and analyze tabular data using the available MCP tools.

GENERAL FLOW (apply to every request, in order):
1. Call `initialize_data_table` with the user's session_id BEFORE any other data tool — even if the session was used in a previous turn (the agent runs stateless across requests).
2. Pick the smallest set of tools that satisfies the request. Prefer one transform tool over a chain of generic ones.
3. After the tools run, summarise what changed in plain English: which columns/rows were affected, the resulting shape, and any noteworthy values.
4. If a tool returns an error, explain the cause in one sentence and propose the most likely fix; do not silently retry.

TOOL SELECTION GUIDELINES:
- Filtering / row selection → use `filter_rows` (single condition) or `filter_rows_advanced` (multi-condition / boolean).
- Aggregation (sum/mean/count by group) → use `groupby_aggregate` with `group_by` columns and an `agg` map.
- Sorting / top-N → use `sort_values` with `ascending`; for "top 10" combine with a head/limit step.
- Column ops (rename, drop, cast) → use the dedicated tool, not a free-form transform.
- Multi-table joins → confirm key columns exist on both sides BEFORE calling the join tool.

WORKED EXAMPLES (use as a pattern, do not repeat them verbatim):

Example 1 — filter
User: "Show only orders from California."
Steps:
  - initialize_data_table(session_id)
  - filter_rows(column="state", op="==", value="CA")
Reply: "Filtered to N rows where state == 'CA'. Other columns unchanged."

Example 2 — aggregate
User: "Average revenue by region."
Steps:
  - initialize_data_table(session_id)
  - groupby_aggregate(group_by=["region"], agg={"revenue": "mean"})
Reply: "Grouped by region; reporting mean revenue per region. Highest = <region> at <value>."

Example 3 — sort + limit
User: "Top 5 customers by total spend."
Steps:
  - initialize_data_table(session_id)
  - sort_values(by="total_spend", ascending=False)
  - (head/limit to 5 via the appropriate tool)
Reply: "Sorted by total_spend descending and kept the top 5 customers. Top entry = <name> at <value>."

OUTPUT STYLE:
- Keep replies to 1-3 short sentences unless the user explicitly asks for detail.
- Always state the resulting row count when filtering or aggregating.
- Never invent column names; if the user references a column you can't find, ask for clarification before running tools.

=== TOOL USAGE NOTES ===
The following extended notes exist primarily to lengthen the static system
prefix past OpenAI's 1024-token automatic prompt-cache threshold so that
repeated calls within a session pay the cached-token rate. They are also
real guidance — read them and apply them where relevant — but their
inclusion is deliberate and they MUST stay verbatim across requests.

ARGUMENT SHAPES — getting this wrong is the most common failure mode:
- `column` parameters always take a single string, never a list. If the user
  asks to operate on multiple columns, call the tool once per column unless
  the tool explicitly accepts a `columns` (plural) list.
- `value` parameters in filter ops are JSON-typed: strings stay quoted,
  numbers stay unquoted, booleans are `true`/`false`, missing is `null`.
  Quoting a numeric literal will produce zero matches.
- `op` / comparison operator parameters use the canonical set
  `{"==", "!=", ">", ">=", "<", "<=", "in", "not_in", "contains",
  "startswith", "endswith", "is_null", "is_not_null"}`. Do not invent
  operators such as `between` or `like`; compose them from the canonical
  set (`>=` AND `<=` for ranges, `contains` for substring match).
- Aggregation maps (e.g. for `groupby_aggregate`) are
  `{column: function}` where function is one of `mean`, `sum`, `count`,
  `min`, `max`, `median`, `nunique`, `first`, `last`. Anything else will
  fail server-side with a confusing error.
- `ascending` for sort tools accepts a bool or a list of bools matching the
  length of `by`. Mixed sort directions require the list form.

MULTI-STEP COMPOSITION:
- Compose tools left to right; each tool sees the state mutated by the
  previous tool in the same turn, NOT the original session snapshot.
- Filter BEFORE aggregating when the user wants a conditional aggregate
  ("average price for laptops with RAM > 8"). Doing it the other way
  produces the wrong number and is hard to detect from the response alone.
- Sorting AFTER aggregation is almost always what the user wants for
  "top N by group" queries. `groupby_aggregate` then `sort_values` then
  any head/limit step.
- For "top N per group" (NOT total top N), prefer a single dedicated
  tool if available; otherwise compose `sort_values` + a per-group
  ranking step. Never approximate with a global top-N when the user
  asked for per-group.

TYPE HANDLING:
- Numeric strings ("123", "4.5") are sometimes stored as object dtype on
  upload. If a numeric op fails with a type error, cast first via
  `cast_column(target="float")` and retry exactly once. Do not loop on
  retries; if the second attempt also fails, surface the error.
- Boolean-like columns may arrive as 0/1 ints, true/false strings, or
  Y/N strings. Match the user's literal in the comparison rather than
  silently coercing.
- Date/time columns are stored as ISO strings unless the user uploaded
  Parquet. For range filters, compare against ISO-formatted strings;
  do not parse and reformat.

MISSING DATA:
- `is_null` / `is_not_null` filters apply to true NaN/None only, not to
  empty strings. If the user says "missing" and the column is object
  dtype, also check for `value=""` and surface the disambiguation in
  your reply.
- `fill_missing` accepts `value` (constant), `method="ffill"` /
  `"bfill"`, or `method="mean"` / `"median"` / `"mode"` for numerics.
  Confirm the column dtype before proposing a fill method.

IDEMPOTENCY AND STATE:
- `initialize_data_table` is cheap on the same session within a turn but
  resets any uncommitted scratch state from a previous failed attempt.
  Always call it FIRST in every turn regardless of what the previous
  turn did, because you do not have continuity guarantees across
  requests.
- After mutating tools (filter, drop, fill, etc.), the session's "current
  table" reflects the mutation; subsequent reads in the same turn see
  the mutated data. This is intentional — leverage it for chaining.
- Never call `save_version` from within this agent; the host application
  manages versioning around your turn.

WHEN TO ASK INSTEAD OF GUESSING:
- The user references a column not in the schema -> ask which existing
  column they meant; do not run anything.
- The user gives an ambiguous aggregation ("show sales") on a table with
  multiple plausible measure columns -> ask once, then proceed with
  their answer.
- The user requests an irreversible-looking transformation ("delete all
  rows where revenue is zero") on a large table -> proceed (the host
  app supports version rollback) but state the row count explicitly so
  they can verify.

ERROR RECOVERY:
- A single tool failure does NOT mean the whole task is impossible.
  Read the error, propose ONE corrective step, run it, and report.
- Do not retry the same tool with the same arguments. That is a sign
  the issue is upstream (wrong column, wrong dtype, missing data).
- If a server-side error mentions a column that should exist, call the
  schema-introspection tool before giving up; the user may have a
  spelling variant.
"""

# ---------------------------------------------------------------------------
# Agent singleton cache — keyed by "url|model" so MAIN and MINI stay warm
# simultaneously without evicting each other.
# ---------------------------------------------------------------------------
_agent_lock = threading.Lock()
_agent_cache: dict = {}  # "url|model" → (agent, client)


async def _get_or_create_agent(model: str = "") -> Tuple[Any, Any]:
    """Return a cached (agent, client) pair, creating one on first access."""
    if not model:
        model = MAIN_MODEL
    key = f"{MCP_SERVER_URL}|{model}"
    if key in _agent_cache:
        return _agent_cache[key]
    with _agent_lock:
        if key in _agent_cache:
            return _agent_cache[key]
        agent, client = await _create_agent(model=model)
        _agent_cache[key] = (agent, client)
    return _agent_cache[key]


# ---------------------------------------------------------------------------
# Tool-usage callback
# ---------------------------------------------------------------------------
class ToolUsageCallback(BaseCallbackHandler):
    """Tracks MCP tool calls for logging and perf counting."""
    
    def __init__(self):
        self.tool_calls: list = []
    
    def on_tool_start(self, serialized, input_str, **kwargs):
        tool_name = (
            serialized.get("name", "Unknown")
            if isinstance(serialized, dict)
            else getattr(serialized, "name", "Unknown")
        )
        logger.info("[TOOL] call  name=%s  input=%.100s", tool_name, str(input_str) if input_str else "")
        self.tool_calls.append({"name": tool_name, "input": input_str})
    
    def on_tool_end(self, output, **kwargs):
        logger.debug("[TOOL] done  output_preview=%.200s", str(output)[:200])
    
    def on_tool_error(self, error, **kwargs):
        logger.error("[TOOL] error  %s", error)


# ---------------------------------------------------------------------------
# Agent factory (called once per model on first request)
# ---------------------------------------------------------------------------
async def _create_agent(model: str = "") -> Tuple[Any, Any]:
    """
    Build a LangChain MCP agent for the given model.
    Benchmark target: < 2.0 s total (connect + tool discovery + LLM init).
    """
    if not model:
        model = MAIN_MODEL
    if not OPENAI_API_KEY:
        raise ValueError(
            "OPENAI_API_KEY environment variable is required. "
            "Set it with: export OPENAI_API_KEY='your-key-here'"
        )
    
    t0 = _time.perf_counter()
    logger.info("[PERF] mcp.agent_create START  model=%s", model)

    client = MultiServerMCPClient(
        {"data_assistant": {"transport": "http", "url": MCP_SERVER_URL}}
    )

    t_tools = _time.perf_counter()
    snapshot = _read_tool_snapshot()
    if snapshot.get("server_url") == MCP_SERVER_URL and snapshot.get("tool_names"):
        logger.info(
            "[MCP] tool snapshot present (n=%d, age=%.0fs) — still need live discovery for Tool objects",
            len(snapshot["tool_names"]),
            _time.time() - snapshot.get("captured_at", _time.time()),
        )
    logger.info("[PERF] mcp.tool_fetch START  server=%s", MCP_SERVER_URL)
    tools = await client.get_tools()
    t_tools_elapsed = _time.perf_counter() - t_tools
    logger.info("[PERF] mcp.tool_fetch END  tool_count=%d  duration=%.3fs", len(tools), t_tools_elapsed)
    _perf_warn("mcp.tool_fetch", t_tools_elapsed)
    tool_names = [getattr(t, "name", "?") for t in tools]
    logger.info("[MCP] Loaded %d tools: %s", len(tools), tool_names)
    _write_tool_snapshot(MCP_SERVER_URL, tool_names)

    llm = ChatOpenAI(model=model, api_key=OPENAI_API_KEY, temperature=0.1)
    agent = create_agent(llm, tools)

    t_total = _time.perf_counter() - t0
    logger.info("[PERF] mcp.agent_create END  tool_fetch=%.3fs  total=%.3fs", t_tools_elapsed, t_total)
    _perf_warn("mcp.agent_create", t_total)
    
    return agent, client


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def _build_user_message(session_id: str, query: str) -> str:
    return (
        f"Session ID: {session_id}\n\n"
        f"User Query: {query}\n\n"
        "Please help me with this data analysis task. First initialize the table from "
        "the session using initialize_data_table, then perform the requested operations."
    )


def _extract_chunk_text(chunk: Any) -> str:
    """Pull a string out of a streamed AIMessageChunk regardless of content shape."""
    if chunk is None:
        return ""
    content = getattr(chunk, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        # Multi-part content (e.g. some providers return [{"type":"text","text":"..."}, ...])
        return "".join(
            p.get("text", "")
            for p in content
            if isinstance(p, dict) and p.get("type") == "text"
        )
    return ""


async def analyze_data_stream(
    session_id: str, query: str
) -> AsyncIterator[Tuple[str, Any]]:
    """T-2: stream NL Transform output as ``(event_type, payload)`` tuples.

    Event vocabulary the UI/wrapper consumes:

    * ``("token", str)``       — chunk of assistant text (append to body)
    * ``("tool_start", str)``  — tool name about to run (update status caption)
    * ``("tool_end", str)``    — tool name finished
    * ``("cached", str)``      — cache hit; full response text (no token stream)
    * ``("final", str)``       — terminal event with the full assembled text;
                                 caller writes the T-3 cache here exactly once
    * ``("error", str)``       — fatal error during streaming

    Streaming API choice (see context/LATENCY_README.md T-2): we prefer
    ``agent.astream_events(version="v2")`` because every LangChain Runnable
    supports it regardless of whether ``create_agent`` returns a LangGraph
    ``CompiledGraph`` or a plain LCEL chain. ``astream(stream_mode=[...])`` is
    LangGraph-specific and would silently no-op on a non-graph runnable, so it
    is only used when ``astream_events`` is unavailable on the installed
    LangChain version.
    """
    model = _select_model(query)
    logger.info("[MODEL] selected=%s  query_preview=%.60s", model, query)

    # T-3: short-circuit on identical (session, query, version) before doing any
    # LLM / tool work. The version key invalidates the entry on save_version.
    cache_key: str | None = None
    store = None
    if TRANSFORM_CACHE_ENABLED:
        try:
            store = get_session_store()
            version = store.get_current_version(session_id) or "v0"
            cache_key = _transform_cache_key(session_id, query, version)
            cached = store.raw_get(cache_key)
            if cached:
                if isinstance(cached, bytes):
                    cached = cached.decode("utf-8", errors="replace")
                logger.info(
                    "[CACHE HIT] transform_cache  session=%s  version=%s  key=%s",
                    session_id, version, cache_key,
                )
                yield ("cached", cached)
                yield ("final", cached)
                return
        except Exception as e:
            logger.warning("transform_cache lookup skipped: %s", e)
            cache_key = None

    agent, _client = await _get_or_create_agent(model=model)

    tool_callback = ToolUsageCallback()
    langfuse_callback = build_langchain_callback(
        session_id=session_id,
        metadata={"source": "mcp_client"},
        update_trace=True,
    )
    callbacks = [tool_callback, *([langfuse_callback] if langfuse_callback else [])]

    inputs = {
        "messages": [
            {"role": "system", "content": AGENT_SYSTEM_MESSAGE},
            {"role": "user",   "content": _build_user_message(session_id, query)},
        ]
    }
    config = {"callbacks": callbacks}

    t0 = _time.perf_counter()
    logger.info(
        "[PERF] mcp.llm_invoke START  session=%s  model=%s  query_len=%d",
        session_id, model, len(query),
    )

    full_text_parts: List[str] = []
    first_token_logged = False
    use_events = callable(getattr(agent, "astream_events", None))

    try:
        if use_events:
            async for event in agent.astream_events(inputs, version="v2", config=config):
                ev_name = event.get("event", "")
                if ev_name == "on_chat_model_stream":
                    chunk = (event.get("data") or {}).get("chunk")
                    text = _extract_chunk_text(chunk)
                    if text:
                        if not first_token_logged:
                            logger.info(
                                "[STREAM] first_token  session=%s  elapsed=%.3fs",
                                session_id, _time.perf_counter() - t0,
                            )
                            first_token_logged = True
                        full_text_parts.append(text)
                        yield ("token", text)
                elif ev_name == "on_tool_start":
                    yield ("tool_start", event.get("name", "tool"))
                elif ev_name == "on_tool_end":
                    yield ("tool_end", event.get("name", "tool"))
        else:
            # LangGraph fallback: agent is a CompiledGraph exposing astream.
            logger.info("[STREAM] astream_events unavailable; using astream fallback")
            async for mode, data in agent.astream(
                inputs, stream_mode=["messages", "updates"], config=config,
            ):
                if mode == "messages":
                    chunk, _meta = data if isinstance(data, tuple) else (data, {})
                    text = _extract_chunk_text(chunk)
                    if text:
                        if not first_token_logged:
                            logger.info(
                                "[STREAM] first_token  session=%s  elapsed=%.3fs",
                                session_id, _time.perf_counter() - t0,
                            )
                            first_token_logged = True
                        full_text_parts.append(text)
                        yield ("token", text)
                # `updates` mode lacks per-tool boundaries; UI degrades to
                # showing only token stream + a generic "Processing…" caption.

        full_text = "".join(full_text_parts)

        t_invoke = _time.perf_counter() - t0
        logger.info(
            "[PERF] mcp.llm_invoke END  session=%s  duration=%.3fs  tool_calls=%d",
            session_id, t_invoke, len(tool_callback.tool_calls),
        )
        _perf_warn("mcp.llm_invoke", t_invoke, session_id)

        # T-3: write cache exactly once, on the final, complete text.
        if TRANSFORM_CACHE_ENABLED and cache_key and store is not None and full_text:
            try:
                store.raw_setex(cache_key, TRANSFORM_CACHE_TTL, full_text)
                logger.info(
                    "[CACHE SET] transform_cache  session=%s  ttl=%ss  bytes=%d",
                    session_id, TRANSFORM_CACHE_TTL, len(full_text),
                )
            except Exception as e:
                logger.warning("transform_cache write failed: %s", e)

        yield ("final", full_text)

    except Exception as e:
        logger.error(
            "[STREAM] error  session=%s  error=%s", session_id, e, exc_info=True,
        )
        yield ("error", str(e))


@observe(name="mcp_analyze_data", as_type="agent")
async def analyze_data(session_id: str, query: str) -> str:
    """Non-streaming wrapper: drains :func:`analyze_data_stream` to a string.

    Preserves the historical sync entry point (CLI, ``analyze_data_sync`` in
    ``app.py`` if streaming UI is disabled, tests). The ``@observe`` boundary
    here gives Langfuse a top-level "agent" span; finer-grained LLM and tool
    spans come from the LangChain callback inside ``analyze_data_stream``.

    Model routing (see context/MODEL_STRATEGY.md §4):
      Tier 1 — simple single-op (≤12 words + keyword) → MINI_MODEL
      Tier 2/3 — complex / ambiguous                  → MAIN_MODEL
    """
    parts: List[str] = []
    final_text = ""
    error_text = ""
    async for ev_type, payload in analyze_data_stream(session_id, query):
        if ev_type == "token":
            parts.append(payload)
        elif ev_type == "cached":
            return payload
        elif ev_type == "final":
            final_text = payload
        elif ev_type == "error":
            error_text = payload
    if error_text and not final_text:
        raise RuntimeError(error_text)
    return final_text or "".join(parts)


# ---------------------------------------------------------------------------
# CLI utilities (python mcp_client.py [session_id query])
# ---------------------------------------------------------------------------
async def _get_available_sessions() -> List[Dict[str, Any]]:
    """Fetch all sessions from the ingestion API (CLI use only)."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{INGESTION_API_URL}/api/sessions")
            response.raise_for_status()
            return response.json().get("sessions", [])
    except Exception as e:
        logger.error("Error fetching sessions: %s", e)
        return []


async def interactive_chat():
    """Interactive CLI session for manual testing."""
    logger.info("MCP interactive mode  server=%s  model=%s", MCP_SERVER_URL, MAIN_MODEL)
    agent, _client = await _get_or_create_agent(model=MAIN_MODEL)

    sessions = await _get_available_sessions()
    if not sessions:
        logger.warning("No sessions found — upload a file via the ingestion API first.")
        return

    logger.info("Available sessions (%d):", len(sessions))
    for idx, s in enumerate(sessions[:10], 1):
        logger.info("  %d. %s  file=%s  tables=%d", idx,
                    s.get("session_id", "N/A"), s.get("file_name", "Unknown"), s.get("table_count", 0))
    if len(sessions) > 10:
        logger.info("  ... and %d more", len(sessions) - 10)

    session_id = input("Enter session ID: ").strip()
    if not session_id:
        return

    logger.info("Session: %s  (type 'exit' to quit)", session_id)
    while True:
        query = input("You: ").strip()
        if query.lower() in {"exit", "quit", "q"}:
            break
        if not query:
            continue

        message = (
            f"Session ID: {session_id}\n\nUser Query: {query}\n\n"
            "Please help with this task. First initialize the table from the session "
            "using initialize_data_table, then perform the requested operations."
        )
        try:
            tool_callback = ToolUsageCallback()
            update_trace_context(session_id=session_id, metadata={"source": "mcp_client_interactive"})
            lf_cb = build_langchain_callback(
                session_id=session_id,
                metadata={"source": "mcp_client_interactive"},
                update_trace=True,
            )
            callbacks = [tool_callback, *([lf_cb] if lf_cb else [])]
            response = await agent.ainvoke(
                {"messages": [
                    {"role": "system", "content": AGENT_SYSTEM_MESSAGE},
                    {"role": "user",   "content": message},
                ]},
                config={"callbacks": callbacks},
            )
            print(f"\nAssistant: {response['messages'][-1].content}\n")
        except Exception as e:
            logger.error("[MCP] Query failed  error=%s", e, exc_info=True)


def main():
    """Entry point: single-query or interactive mode."""
    import sys
    if len(sys.argv) > 1:
        if len(sys.argv) < 3:
            print("Usage: python mcp_client.py <session_id> <query>")
            sys.exit(1)
        result = asyncio.run(analyze_data(sys.argv[1], " ".join(sys.argv[2:])))
        print(result)
    else:
        asyncio.run(interactive_chat())


if __name__ == "__main__":
    main()
