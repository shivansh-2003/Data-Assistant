"""LangChain agent setup and orchestration for chatbot."""

import os
import logging
from typing import Dict, List, Optional, Any, Tuple
import pandas as pd

# Import pandas dataframe agent from experimental package
# This package handles pandas operations safely
from langchain_experimental.agents.agent_toolkits import create_pandas_dataframe_agent
from langchain_openai import ChatOpenAI

from .session_loader import SessionLoader
from .visualization_detector import VisualizationDetector

logger = logging.getLogger(__name__)

# System prompt for the agent
SYSTEM_PROMPT = """You are a data analysis assistant helping users understand their data.

You have access to:
- Current session data (schema, stats, preview)
- Operation history (recent transformations)
- Conversation history (previous chat messages)

Guidelines:
- Answer questions about data content, patterns, and statistics clearly and concisely
- Explain data transformations and their effects
- When a visualization would help, mention it in your response
- Be thorough but avoid unnecessary details
- Reference specific operations when explaining changes
- If asked about operations or transformations, check the operation history context provided
"""


class ChatbotAgent:
    """LangChain agent orchestrator for chatbot queries."""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        session_loader: Optional[SessionLoader] = None,
        visualization_detector: Optional[VisualizationDetector] = None
    ):
        """
        Initialize ChatbotAgent.
        
        Args:
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
            model_name: OpenAI model name (defaults to OPENAI_MODEL env var or "gpt-4o")
            session_loader: Optional SessionLoader instance (creates default if None)
            visualization_detector: Optional VisualizationDetector instance (creates default if None)
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model_name = model_name or os.getenv("OPENAI_MODEL", "gpt-4o")
        self.session_loader = session_loader or SessionLoader()
        self.visualization_detector = visualization_detector or VisualizationDetector()
        self.logger = logging.getLogger(__name__)
        self.system_prompt = SYSTEM_PROMPT
    
    def create_agent(
        self,
        session_id: str,
        dfs: Dict[str, pd.DataFrame]
    ) -> Any:
        """
        Create a LangChain pandas dataframe agent.
        
        Note: Conversation memory is handled separately through context prompts,
        as the pandas dataframe agent doesn't directly support checkpointer.
        
        Args:
            session_id: Session ID
            dfs: Dictionary of DataFrames keyed by table name
            
        Returns:
            Agent instance
        """
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")
        
        # Create LLM
        llm = ChatOpenAI(
            model=self.model_name,
            api_key=self.api_key,
            temperature=0.1,  # Lower temperature for more deterministic responses
        )
        
        # Convert dict of DataFrames to list for multi-DataFrame support
        df_list = list(dfs.values())
        
        # Create agent with pandas dataframe toolkit
        # Note: The pandas dataframe agent requires allow_dangerous_code=True because it uses
        # a Python REPL tool to execute pandas operations. This is safe in our controlled
        # environment where users are working with their own data.
        # See: https://python.langchain.com/docs/security/
        try:
            # Try with modern API (no agent_type parameter)
            agent = create_pandas_dataframe_agent(
                llm,
                df_list,
                verbose=True,
                allow_dangerous_code=True,  # Required for pandas dataframe agent to work
            )
        except TypeError as e:
            # If that fails, try with older API that might need agent_type
            self.logger.warning(f"Agent creation with default params failed, trying alternative: {e}")
            try:
                # Try importing AgentType for older versions
                from langchain.agents.agent_types import AgentType
                agent = create_pandas_dataframe_agent(
                    llm,
                    df_list,
                    verbose=True,
                    agent_type=AgentType.OPENAI_FUNCTIONS,
                    allow_dangerous_code=True,  # Required for pandas dataframe agent to work
                )
            except (ImportError, TypeError):
                # Last resort: minimal parameters (will still need allow_dangerous_code)
                self.logger.warning("Using minimal agent parameters")
                agent = create_pandas_dataframe_agent(
                    llm,
                    df_list,
                    verbose=True,
                    allow_dangerous_code=True,  # Required for pandas dataframe agent to work
                )
        
        self.logger.info(f"Created chatbot agent for session {session_id} with {len(df_list)} DataFrames")
        return agent
    
    def build_context_prompt(
        self,
        session_id: str,
        schema: Dict[str, Any],
        operation_history: List[Dict[str, Any]],
        conversation_history: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """
        Build context prompt with session information.
        
        Args:
            session_id: Session ID
            schema: Schema information
            operation_history: List of recent operations
            conversation_history: Previous conversation messages
            
        Returns:
            Context prompt string
        """
        context_parts = []
        
        # Add schema information
        if schema and "tables" in schema:
            context_parts.append("Current session data:")
            for table_name, table_info in schema["tables"].items():
                context_parts.append(f"\nTable '{table_name}':")
                context_parts.append(f"  - Rows: {table_info.get('row_count', 'N/A')}")
                context_parts.append(f"  - Columns: {', '.join(table_info.get('columns', []))}")
                if table_info.get('numeric_columns'):
                    context_parts.append(f"  - Numeric columns: {', '.join(table_info.get('numeric_columns', []))}")
                if table_info.get('categorical_columns'):
                    context_parts.append(f"  - Categorical columns: {', '.join(table_info.get('categorical_columns', []))}")
        
        # Add operation history if available
        if operation_history:
            context_parts.append("\nRecent operations performed on this data:")
            for idx, op in enumerate(operation_history[-5:], 1):  # Last 5 operations
                op_desc = op.get('description', op.get('operation', 'Unknown'))
                context_parts.append(f"  {idx}. {op_desc}")
        
        # Add conversation history if available
        if conversation_history:
            context_parts.append("\nPrevious conversation:")
            for msg in conversation_history[-3:]:  # Last 3 messages
                role = msg.get('role', 'unknown')
                content = msg.get('content', '')
                if role == 'user':
                    context_parts.append(f"  User: {content[:100]}...")
                elif role == 'assistant':
                    context_parts.append(f"  Assistant: {content[:100]}...")
        
        return "\n".join(context_parts)
    
    async def invoke_agent(
        self,
        agent: Any,
        query: str,
        context_prompt: str,
        config: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Invoke the agent with a query and context.
        
        Args:
            agent: Agent instance (from create_pandas_dataframe_agent)
            query: User query
            context_prompt: Context information to include
            config: Optional configuration (e.g., for checkpointer thread_id)
            
        Returns:
            Agent response string
        """
        try:
            # Combine context and query
            full_query = f"{context_prompt}\n\nUser Question: {query}"
            
            # Invoke agent - pandas dataframe agent expects string input
            # Run in thread pool since agent.invoke might be sync
            import asyncio
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, lambda: agent.invoke(full_query))
            
            # Extract response content
            # The pandas dataframe agent returns a string directly
            if isinstance(response, str):
                return response
            elif isinstance(response, dict):
                # Sometimes it might return a dict
                if "output" in response:
                    return str(response["output"])
                elif "result" in response:
                    return str(response["result"])
            else:
                # Try to convert to string
                return str(response)
        except Exception as e:
            self.logger.error(f"Error invoking agent: {e}", exc_info=True)
            raise
    
    async def process_chat_query(
        self,
        session_id: str,
        user_query: str,
        streamlit_session_state: Any,
        thread_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Main entry point for processing chat queries.
        
        Args:
            session_id: Session ID
            user_query: User's query
            streamlit_session_state: Streamlit session state object
            thread_id: Optional thread ID for checkpointer (defaults to session_id)
            
        Returns:
            Dictionary with response:
            {
                "text_response": str,
                "visualization": {
                    "needed": bool,
                    "chart_config": Optional[Dict],
                    "chart_type": Optional[str]
                },
                "tools_used": List[str],
                "error": Optional[str]
            }
        """
        if thread_id is None:
            thread_id = session_id
        
        try:
            # 1. Load DataFrames
            self.logger.info(f"Loading DataFrames for session {session_id}")
            dfs = self.session_loader.load_session_dataframes(session_id)
            
            if not dfs:
                return {
                    "text_response": "No data found in this session. Please upload data first.",
                    "visualization": {"needed": False},
                    "tools_used": [],
                    "error": "No data in session"
                }
            
            # 2. Get schema and operation history
            schema = self.session_loader.get_session_schema(session_id)
            operation_history = self.session_loader.get_operation_history(session_id, streamlit_session_state)
            
            # 3. Detect visualization need
            needs_viz, suggested_chart_type = self.visualization_detector.detect_visualization_need(user_query)
            
            # 4. Create agent (could cache this per session for performance)
            agent = self.create_agent(session_id, dfs)
            
            # 5. Get conversation history for context (from Streamlit session state)
            conversation_history = []
            history_key = f"chatbot_history_{session_id}"
            if hasattr(streamlit_session_state, history_key):
                chat_history = getattr(streamlit_session_state, history_key, [])
                # Convert to format expected by build_context_prompt
                conversation_history = [
                    {"role": msg.get("role"), "content": msg.get("content", "")}
                    for msg in chat_history[-10:]  # Last 10 messages
                ]
            
            # 6. Build context prompt
            context_prompt = self.build_context_prompt(session_id, schema, operation_history, conversation_history)
            
            # 7. Invoke agent
            self.logger.info(f"Invoking agent for query: {user_query[:50]}...")
            agent_response = await self.invoke_agent(agent, user_query, context_prompt)
            
            # 7. Extract chart parameters if visualization needed
            chart_config = None
            if needs_viz and dfs:
                # Use the first table for chart generation (could be enhanced for multi-table)
                first_table_name = list(dfs.keys())[0]
                first_df = dfs[first_table_name]
                first_table_schema = schema.get("tables", {}).get(first_table_name, {})
                
                chart_config = self.visualization_detector.extract_chart_parameters(
                    user_query,
                    first_df,
                    first_table_schema,
                    suggested_chart_type
                )
                chart_config["table_name"] = first_table_name
            
            # 8. Format response
            response = {
                "text_response": agent_response,
                "visualization": {
                    "needed": needs_viz,
                    "chart_config": chart_config,
                    "chart_type": suggested_chart_type
                },
                "tools_used": [],  # Could extract from agent response if available
                "error": None
            }
            
            self.logger.info(f"Successfully processed query for session {session_id}")
            return response
            
        except ValueError as e:
            # Session not found or similar
            return {
                "text_response": f"Error: {str(e)}",
                "visualization": {"needed": False},
                "tools_used": [],
                "error": str(e)
            }
        except Exception as e:
            self.logger.error(f"Error processing chat query: {e}", exc_info=True)
            return {
                "text_response": f"I encountered an error while processing your query: {str(e)}",
                "visualization": {"needed": False},
                "tools_used": [],
                "error": str(e)
            }


# Create default instance for backward compatibility
_default_agent = ChatbotAgent()

# Backward compatibility functions
def create_chatbot_agent(
    session_id: str,
    dfs: Dict[str, pd.DataFrame]
) -> Any:
    """Create a LangChain pandas dataframe agent. Uses default ChatbotAgent instance."""
    return _default_agent.create_agent(session_id, dfs)


def build_context_prompt(
    session_id: str,
    schema: Dict[str, Any],
    operation_history: List[Dict[str, Any]],
    conversation_history: Optional[List[Dict[str, Any]]] = None
) -> str:
    """Build context prompt with session information. Uses default ChatbotAgent instance."""
    return _default_agent.build_context_prompt(session_id, schema, operation_history, conversation_history)


async def invoke_agent(
    agent: Any,
    query: str,
    context_prompt: str,
    config: Optional[Dict[str, Any]] = None
) -> str:
    """Invoke the agent with a query and context. Uses default ChatbotAgent instance."""
    return await _default_agent.invoke_agent(agent, query, context_prompt, config)


async def process_chat_query(
    session_id: str,
    user_query: str,
    streamlit_session_state: Any,
    thread_id: Optional[str] = None
) -> Dict[str, Any]:
    """Main entry point for processing chat queries. Uses default ChatbotAgent instance."""
    return await _default_agent.process_chat_query(session_id, user_query, streamlit_session_state, thread_id)
