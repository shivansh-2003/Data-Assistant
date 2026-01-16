"""
MCP Client using LangChain MCP Adapters.
Connects to the Data Assistant MCP Server and uses OpenAI GPT-5.1 for data manipulation.
"""

import os
import asyncio
import httpx
from typing import Optional, List, Dict, Any
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langchain_core.callbacks import BaseCallbackHandler


# Configuration
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "https://data-analyst-mcp-server.onrender.com/data/mcp")
INGESTION_API_URL = os.getenv("INGESTION_API_URL", "https://data-assistant-m4kl.onrender.com")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.1")  # Using GPT-5.1 as requested
# Note: If GPT-5.1 is not available, fallback to latest model
# You can also use: "gpt-4o", "gpt-4-turbo", etc.

# System message for the agent
AGENT_SYSTEM_MESSAGE = """You are a data analysis assistant. You help users manipulate and analyze data 
using the available tools. Always:
1. First initialize the data table using initialize_data_table with the session_id
2. Use appropriate tools to perform data operations
3. Provide clear explanations of what operations were performed
4. Show summaries of the results when available"""


async def _cleanup_client(client):
    """Clean up MCP client connections."""
    try:
        if hasattr(client, 'close'):
            await client.close()
    except (AttributeError, Exception):
        # Client doesn't have close method or cleanup failed, skip silently
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
        
        print(f"\n🔧 [TOOL CALL] {tool_name}")
        if input_str:
            # Show truncated input
            input_preview = str(input_str)[:100] + "..." if len(str(input_str)) > 100 else str(input_str)
            print(f"   Input: {input_preview}")
        self.tool_calls.append({"name": tool_name, "input": input_str})
    
    def on_tool_end(self, output, **kwargs):
        """Called when a tool finishes executing."""
        # Show truncated output
        output_str = str(output)[:200] + "..." if len(str(output)) > 200 else str(output)
        print(f"   ✅ Tool execution completed")
        if output_str and len(str(output)) < 500:
            print(f"   Output preview: {output_str}")
    
    def on_tool_error(self, error, **kwargs):
        """Called when a tool encounters an error."""
        print(f"   ❌ Tool error: {error}")
    
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
    
    Returns:
        Agent instance ready to use
    """
    if not OPENAI_API_KEY:
        raise ValueError(
            "OPENAI_API_KEY environment variable is required. "
            "Set it with: export OPENAI_API_KEY='your-key-here'"
        )
    
    # Create MCP client connected to the Data Assistant MCP Server
    client = MultiServerMCPClient(
        {
            "data_assistant": {
                "transport": "http",
                "url": MCP_SERVER_URL,
            }
        }
    )
    
    # Get tools from the MCP server
    print("Loading tools from MCP server...")
    tools = await client.get_tools()
    print(f"\n✅ Loaded {len(tools)} tools from MCP server:")
    print("-" * 60)
    for idx, tool in enumerate(tools, 1):
        tool_name = getattr(tool, 'name', 'Unknown')
        tool_desc = getattr(tool, 'description', 'No description')
        print(f"  {idx}. {tool_name}")
        if tool_desc:
            # Truncate long descriptions
            desc = tool_desc[:80] + "..." if len(tool_desc) > 80 else tool_desc
            print(f"     └─ {desc}")
    print("-" * 60)
    print()
    
    # Create OpenAI LLM with GPT-5.1
    llm = ChatOpenAI(
        model=OPENAI_MODEL,
        api_key=OPENAI_API_KEY,
        temperature=0.1,  # Lower temperature for more deterministic data operations
    )
    
    # Create agent with the tools
    agent = create_agent(
        llm,
        tools
    )
    
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
        print(f"Error fetching sessions: {e}")
        return []
    except Exception as e:
        print(f"Unexpected error: {e}")
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
        print(f"Error fetching session metadata: {e}")
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


async def analyze_data(session_id: str, query: str) -> str:
    """
    Analyze data using natural language query.
    
    Args:
        session_id: Session ID containing the data in Redis
        query: Natural language query describing what to do with the data
        
    Returns:
        Response from the agent
    """
    agent, client = await create_mcp_agent()
    
    # Construct the message with session context
    message = f"""
    Session ID: {session_id}
    
    User Query: {query}
    
    Please help me with this data analysis task. First, initialize the table from the session, 
    then perform the requested operations.
    """
    
    # Create callback to track tool usage
    tool_callback = ToolUsageCallback()
    
    try:
        print("\n🚀 Starting analysis...")
        response = await agent.ainvoke(
            {
                "messages": [
                    {"role": "system", "content": AGENT_SYSTEM_MESSAGE},
                    {"role": "user", "content": message}
                ]
            },
            config={"callbacks": [tool_callback]}
        )
        
        # Show tool usage summary
        print(tool_callback.get_tool_summary())
        
        return response["messages"][-1].content
    finally:
        await _cleanup_client(client)


async def interactive_chat():
    """
    Interactive chat interface for data analysis.
    """
    print("=" * 60)
    print("Data Assistant MCP Client - Interactive Mode")
    print("=" * 60)
    print(f"MCP Server: {MCP_SERVER_URL}")
    print(f"Model: {OPENAI_MODEL}")
    print("=" * 60)
    print()
    
    agent, client = await create_mcp_agent()
    
    # Get available sessions and show them to user
    print("Fetching available sessions...")
    sessions = await get_available_sessions()
    
    if sessions:
        print(f"\nAvailable sessions ({len(sessions)}):")
        for idx, session in enumerate(sessions[:10], 1):  # Show first 10
            session_id = session.get("session_id", "N/A")
            file_name = session.get("file_name", "Unknown")
            table_count = session.get("table_count", 0)
            print(f"  {idx}. {session_id} - {file_name} ({table_count} tables)")
        if len(sessions) > 10:
            print(f"  ... and {len(sessions) - 10} more sessions")
        print()
    
    # Get session ID from user
    session_id = input("Enter session ID (or press Enter to list all): ").strip()
    if not session_id:
        if sessions:
            print("\nAll available sessions:")
            for session in sessions:
                session_id_val = session.get("session_id", "N/A")
                file_name = session.get("file_name", "Unknown")
                table_count = session.get("table_count", 0)
                print(f"  - {session_id_val}: {file_name} ({table_count} tables)")
        else:
            print("No sessions found. Upload a file via the ingestion API first.")
        return
    
    print(f"\nSession ID: {session_id}")
    print("Type 'exit' or 'quit' to end the session\n")
    
    try:
        while True:
            query = input("You: ").strip()
            
            if query.lower() in ["exit", "quit", "q"]:
                print("Goodbye!")
                break
            
            if not query:
                continue
            
            # Initialize table first if needed
            init_message = f"""
            Session ID: {session_id}
            
            User Query: {query}
            
            Please help me with this data analysis task. First, initialize the table from the session 
            using initialize_data_table, then perform the requested operations.
            """
            
            print("\n🤔 Thinking...")
            try:
                # Create callback to track tool usage for this query
                tool_callback = ToolUsageCallback()
                
                response = await agent.ainvoke(
                    {
                        "messages": [
                            {"role": "system", "content": AGENT_SYSTEM_MESSAGE},
                            {"role": "user", "content": init_message}
                        ]
                    },
                    config={"callbacks": [tool_callback]}
                )
                
                # Show tool usage summary
                print(tool_callback.get_tool_summary())
                
                answer = response["messages"][-1].content
                print(f"\n🤖 Assistant: {answer}\n")
            except Exception as e:
                print(f"\n❌ Error: {e}\n")
    
    finally:
        await _cleanup_client(client)


def main():
    """Main entry point."""
    import sys
    
    if len(sys.argv) > 1:
        # Command-line mode: analyze_data(session_id, query)
        if len(sys.argv) < 3:
            print("Usage: python mcp_client.py <session_id> <query>")
            print("   or: python mcp_client.py  # for interactive mode")
            sys.exit(1)
        
        session_id = sys.argv[1]
        query = " ".join(sys.argv[2:])
        
        result = asyncio.run(analyze_data(session_id, query))
        print(result)
    else:
        # Interactive mode
        asyncio.run(interactive_chat())


if __name__ == "__main__":
    main()

