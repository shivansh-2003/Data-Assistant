"""
MCP Client using LangChain MCP Adapters.
Connects to the Data Assistant MCP Server and uses OpenAI GPT-5.1 for data manipulation.
"""

import os
import asyncio
import logging
import threading
import time as _time
import httpx
from typing import Optional, List, Dict, Any, Tuple
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langchain_core.callbacks import BaseCallbackHandler
from langfuse import observe

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Per-operation latency ceilings (seconds).  Exceeded → WARNING in logs.
# ---------------------------------------------------------------------------
_BENCHMARKS: dict[str, float] = {
    "mcp.agent_create":  2.00,
    "mcp.tool_fetch":    0.80,
    "mcp.llm_invoke":   12.00,
}


def _perf_warn(name: str, elapsed: float, sid: str = "") -> None:
    """Emit SLOW warning if elapsed exceeds benchmark threshold."""
    threshold = _BENCHMARKS.get(name)
    if threshold and elapsed > threshold:
        logger.warning(
            "[PERF][SLOW] %-40s  session=%s  %.3fs elapsed  (benchmark: %.3fs  |  %.1fx over)",
            name, sid, elapsed, threshold, elapsed / threshold,
        )

from observability.langfuse_client import build_langchain_callback, update_trace_context


# Configuration — use 127.0.0.1 (or FASTAPI_URL) for outbound HTTP; 0.0.0.0 is bind-only.
_base = os.getenv("FASTAPI_URL", "http://127.0.0.1:8000").rstrip("/")
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", f"{_base}/data/mcp")
INGESTION_API_URL = os.getenv("INGESTION_API_URL", _base)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = "gpt-5.1"  # Using GPT-5.1 as requested
# Note: If GPT-5.1 is not available, fallback to latest model
# You can also use: "gpt-4o", "gpt-4-turbo", etc.

# System message for the agent
AGENT_SYSTEM_MESSAGE = """You are a data analysis assistant. You help users manipulate and analyze data 
using the available tools. Always:
1. First initialize the data table using initialize_data_table with the session_id
2. Use appropriate tools to perform data operations
3. Provide clear explanations of what operations were performed
4. Show summaries of the results when available"""

_agent_lock = threading.Lock()
_cached_agent: Optional[Any] = None
_cached_mcp_client: Optional[Any] = None
_cached_agent_config_key: Optional[str] = None


def _mcp_agent_cache_key() -> str:
    return f"{MCP_SERVER_URL}|{OPENAI_MODEL}"


async def _get_or_create_agent() -> Tuple[Any, Any]:
    """Reuse MCP client + LangChain agent across queries (same URL/model)."""
    global _cached_agent, _cached_mcp_client, _cached_agent_config_key
    key = _mcp_agent_cache_key()
    if _cached_agent is not None and _cached_agent_config_key == key:
        return _cached_agent, _cached_mcp_client
    with _agent_lock:
        if _cached_agent is not None and _cached_agent_config_key == key:
            return _cached_agent, _cached_mcp_client
        old_client = _cached_mcp_client
        agent, client = await create_mcp_agent()
        _cached_agent, _cached_mcp_client, _cached_agent_config_key = agent, client, key
    if old_client is not None and old_client is not client:
        await _cleanup_client(old_client)
    return _cached_agent, _cached_mcp_client


def reset_cached_mcp_agent() -> None:
    """Clear cached agent (e.g. after MCP server URL change). Best-effort close is async-only."""
    global _cached_agent, _cached_mcp_client, _cached_agent_config_key
    with _agent_lock:
        _cached_agent = None
        _cached_mcp_client = None
        _cached_agent_config_key = None


async def _cleanup_client(client):
    """Clean up MCP client connections."""
    try:
        if hasattr(client, "close"):
            await client.close()
    except (AttributeError, Exception):
        pass


class ToolUsageCallback(BaseCallbackHandler):
    """Callback to track and display tool usage."""
    
    def __init__(self):
        self.tool_calls = []
    
    def on_tool_start(self, serialized, input_str, **kwargs):
        """Called when a tool starts executing."""
        # Handle both dict and object serialized formats
        if isinstance(serialized, dict):
            tool_name = serialized.get("name", "Unknown")
        else:
            tool_name = getattr(serialized, "name", "Unknown")
        
        logger.info("[TOOL] call  name=%s  input=%.100s", tool_name, str(input_str) if input_str else "")
        self.tool_calls.append({"name": tool_name, "input": input_str})
    
    def on_tool_end(self, output, **kwargs):
        """Called when a tool finishes executing."""
        output_str = str(output)[:200]
        logger.debug("[TOOL] done  output_preview=%.200s", output_str)
    
    def on_tool_error(self, error, **kwargs):
        """Called when a tool encounters an error."""
        logger.error("[TOOL] error  %s", error)
    
    def get_tool_summary(self):
        """Get a summary of all tools called."""
        if not self.tool_calls:
            return "No tools were called."
        summary = f"\n📊 Tool Usage Summary ({len(self.tool_calls)} calls):\n"
        tool_counts = {}
        for call in self.tool_calls:
            tool_name = call["name"]
            tool_counts[tool_name] = tool_counts.get(tool_name, 0) + 1
        for tool_name, count in tool_counts.items():
            summary += f"  • {tool_name}: {count} time(s)\n"
        return summary


async def create_mcp_agent():
    """
    Create a LangChain agent connected to the MCP server with OpenAI GPT-5.1.
    Benchmark: < 2.0 s total (MCP connect + tool discovery + LLM init).

    Returns:
        Agent instance ready to use
    """
    if not OPENAI_API_KEY:
        raise ValueError(
            "OPENAI_API_KEY environment variable is required. "
            "Set it with: export OPENAI_API_KEY='your-key-here'"
        )

    _t_agent_start = _time.perf_counter()
    logger.info("[PERF] mcp.agent_create START  model=%s", OPENAI_MODEL)

    # ── MCP client init ──────────────────────────────────────────────────────
    _t_mcp = _time.perf_counter()
    client = MultiServerMCPClient(
        {
            "data_assistant": {
                "transport": "http",
                "url": MCP_SERVER_URL,
            }
        }
    )

    # ── Tool discovery ───────────────────────────────────────────────────────
    _t_tools = _time.perf_counter()
    logger.info("[PERF] mcp.tool_fetch START  server=%s", MCP_SERVER_URL)
    logger.info("[MCP] Loading tools from server  url=%s", MCP_SERVER_URL)
    tools = await client.get_tools()
    _t_tools_elapsed = _time.perf_counter() - _t_tools
    logger.info(
        "[PERF] mcp.tool_fetch END  tool_count=%d  duration=%.3fs",
        len(tools), _t_tools_elapsed,
    )
    _perf_warn("mcp.tool_fetch", _t_tools_elapsed)

    tool_names = [getattr(t, "name", "?") for t in tools]
    logger.info("[MCP] Loaded %d tools: %s", len(tools), tool_names)

    # ── LLM init ─────────────────────────────────────────────────────────────
    _t_llm_init = _time.perf_counter()
    llm = ChatOpenAI(
        model=OPENAI_MODEL,
        api_key=OPENAI_API_KEY,
        temperature=0.1,
    )
    logger.info(
        "[PERF] mcp.llm_init  model=%s  duration=%.3fs",
        OPENAI_MODEL, _time.perf_counter() - _t_llm_init,
    )

    # ── Agent assembly ────────────────────────────────────────────────────────
    agent = create_agent(llm, tools)

    _t_agent_elapsed = _time.perf_counter() - _t_agent_start
    logger.info(
        "[PERF] mcp.agent_create END  tool_fetch=%.3fs  total=%.3fs",
        _t_tools_elapsed, _t_agent_elapsed,
    )
    _perf_warn("mcp.agent_create", _t_agent_elapsed)

    return agent, client


async def get_available_sessions() -> List[Dict[str, Any]]:
    """
    Get all available session IDs from the ingestion API.
    
    Returns:
        List of session dictionaries with session_id and metadata
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{INGESTION_API_URL}/api/sessions")
            response.raise_for_status()
            data = response.json()
            return data.get("sessions", [])
    except httpx.HTTPError as e:
        logger.error("HTTP error fetching sessions: %s", e)
        return []
    except Exception as e:
        logger.error("Unexpected error fetching sessions: %s", e)
        return []


async def get_session_metadata(session_id: str) -> Optional[Dict[str, Any]]:
    """
    Get metadata for a specific session.
    
    Args:
        session_id: The session ID to get metadata for
        
    Returns:
        Session metadata dictionary or None if session not found
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{INGESTION_API_URL}/api/session/{session_id}/metadata")
            response.raise_for_status()
            data = response.json()
            return data.get("metadata")
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return None
        raise
    except Exception as e:
        logger.error("Error fetching session metadata  session=%s  error=%s", session_id, e)
        return None


def list_sessions_sync() -> List[str]:
    """
    Synchronous wrapper to get list of session IDs.
    Useful for command-line usage.
    
    Returns:
        List of session ID strings
    """
    sessions = asyncio.run(get_available_sessions())
    return [session.get("session_id") for session in sessions if "session_id" in session]


@observe(name="mcp_analyze_data", as_type="agent")
async def analyze_data(session_id: str, query: str) -> str:
    """
    Analyze data using natural language query.
    
    Args:
        session_id: Session ID containing the data in Redis
        query: Natural language query describing what to do with the data
        
    Returns:
        Response from the agent
    """
    agent, _client = await _get_or_create_agent()
    
    # Construct the message with session context
    message = f"""
    Session ID: {session_id}
    
    User Query: {query}
    
    Please help me with this data analysis task. First, initialize the table from the session, 
    then perform the requested operations.
    """
    
    # Create callbacks to track tool usage + Langfuse tracing
    tool_callback = ToolUsageCallback()
    langfuse_callback = build_langchain_callback(
        session_id=session_id,
        metadata={"source": "mcp_client"},
        update_trace=True,
    )
    callbacks = [tool_callback]
    if langfuse_callback:
        callbacks.append(langfuse_callback)

    # ── PERF: LLM agent invoke (the long pole in the tent) ───────────────────
    _t_invoke_start = _time.perf_counter()
    logger.info(
        "[PERF] mcp.llm_invoke START  session=%s  model=%s  query_len=%d",
        session_id, OPENAI_MODEL, len(query),
    )
    logger.info("[MCP] Starting LLM agent invoke  session=%s", session_id)
    response = await agent.ainvoke(
        {
            "messages": [
                {"role": "system", "content": AGENT_SYSTEM_MESSAGE},
                {"role": "user", "content": message},
            ]
        },
        config={"callbacks": callbacks},
    )
    _t_invoke = _time.perf_counter() - _t_invoke_start
    logger.info(
        "[PERF] mcp.llm_invoke END  session=%s  duration=%.3fs  tool_calls=%d",
        session_id, _t_invoke, len(tool_callback.tool_calls),
    )
    _perf_warn("mcp.llm_invoke", _t_invoke, session_id)
    # ──────────────────────────────────────────────────────────────────────────

    logger.info("[MCP] Analysis done  session=%s  tool_calls=%d", session_id, len(tool_callback.tool_calls))
    return response["messages"][-1].content


async def interactive_chat():
    """Interactive CLI chat interface for data analysis."""
    logger.info("MCP interactive mode  server=%s  model=%s", MCP_SERVER_URL, OPENAI_MODEL)
    agent, _client = await _get_or_create_agent()

    logger.info("Fetching available sessions...")
    sessions = await get_available_sessions()

    if sessions:
        logger.info("Available sessions (%d):", len(sessions))
        for idx, session in enumerate(sessions[:10], 1):
            logger.info(
                "  %d. %s  file=%s  tables=%d",
                idx,
                session.get("session_id", "N/A"),
                session.get("file_name", "Unknown"),
                session.get("table_count", 0),
            )
        if len(sessions) > 10:
            logger.info("  ... and %d more sessions", len(sessions) - 10)
    else:
        logger.warning("No sessions found — upload a file via the ingestion API first.")
        return

    session_id = input("Enter session ID: ").strip()
    if not session_id:
        return

    logger.info("Session: %s  (type 'exit' to quit)", session_id)

    while True:
        query = input("You: ").strip()
        if query.lower() in ["exit", "quit", "q"]:
            logger.info("Interactive session ended.")
            break
        if not query:
            continue

        init_message = (
            f"Session ID: {session_id}\n\nUser Query: {query}\n\n"
            "Please help with this task. First initialize the table from the session "
            "using initialize_data_table, then perform the requested operations."
        )

        logger.info("[MCP] Processing query  session=%s  query=%.80s", session_id, query)
        try:
            tool_callback = ToolUsageCallback()
            update_trace_context(session_id=session_id, metadata={"source": "mcp_client_interactive"})
            langfuse_callback = build_langchain_callback(
                session_id=session_id,
                metadata={"source": "mcp_client_interactive"},
                update_trace=True,
            )
            callbacks = [tool_callback]
            if langfuse_callback:
                callbacks.append(langfuse_callback)

            response = await agent.ainvoke(
                {
                    "messages": [
                        {"role": "system", "content": AGENT_SYSTEM_MESSAGE},
                        {"role": "user", "content": init_message},
                    ]
                },
                config={"callbacks": callbacks},
            )

            logger.info("[MCP] Response ready  tool_calls=%d", len(tool_callback.tool_calls))
            answer = response["messages"][-1].content
            print(f"\nAssistant: {answer}\n")
        except Exception as e:
            logger.error("[MCP] Query failed  error=%s", e, exc_info=True)


def main():
    """Main entry point."""
    import sys

    if len(sys.argv) > 1:
        if len(sys.argv) < 3:
            print("Usage: python mcp_client.py <session_id> <query>")
            sys.exit(1)
        session_id = sys.argv[1]
        query = " ".join(sys.argv[2:])
        result = asyncio.run(analyze_data(session_id, query))
        print(result)
    else:
        asyncio.run(interactive_chat())


if __name__ == "__main__":
    main()

