"""Streamlit UI components for chatbot tab."""

import streamlit as st
import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

from .agent import ChatbotAgent
from .response_formatter import ResponseFormatter
from .session_loader import SessionLoader

logger = logging.getLogger(__name__)


class ChatbotUI:
    """Streamlit UI for chatbot tab."""
    
    def __init__(
        self,
        agent: Optional[ChatbotAgent] = None,
        response_formatter: Optional[ResponseFormatter] = None,
        session_loader: Optional[SessionLoader] = None
    ):
        """
        Initialize ChatbotUI.
        
        Args:
            agent: Optional ChatbotAgent instance (creates default if None)
            response_formatter: Optional ResponseFormatter instance (creates default if None)
            session_loader: Optional SessionLoader instance (creates default if None)
        """
        self.agent = agent or ChatbotAgent()
        self.response_formatter = response_formatter or ResponseFormatter()
        self.session_loader = session_loader or SessionLoader()
        self.logger = logging.getLogger(__name__)
    
    def initialize_chatbot_state(self, session_id: str):
        """Initialize Streamlit session state for chatbot."""
        history_key = f"chatbot_history_{session_id}"
        thread_id_key = f"chatbot_thread_id_{session_id}"
        
        if history_key not in st.session_state:
            st.session_state[history_key] = []
        
        if thread_id_key not in st.session_state:
            st.session_state[thread_id_key] = session_id  # Use session_id as thread_id
    
    def display_chat_message(self, message: Dict[str, Any], is_user: bool = False):
        """
        Display a chat message with optional chart.
        
        Args:
            message: Message dictionary with:
                - content: str (text content)
                - timestamp: Optional[float]
                - visualization: Optional[Dict] (chart data)
            is_user: Whether this is a user message
        """
        if is_user:
            with st.chat_message("user"):
                st.write(message.get("content", ""))
        else:
            with st.chat_message("assistant"):
                # Display text response
                st.write(message.get("content", ""))
                
                # Display visualization if present
                viz = message.get("visualization")
                if viz and viz.get("needed") and viz.get("chart_figure"):
                    st.plotly_chart(
                        viz["chart_figure"],
                        use_container_width=True,
                        key=f"chart_{message.get('timestamp', 'unknown')}"
                    )
    
    def render_chatbot_tab(self):
        """Main function to render the chatbot tab."""
        st.header("💬 Chatbot - Ask Anything About Your Data")
        
        session_id = st.session_state.get("current_session_id")
        
        # Check if session exists
        if not session_id:
            st.warning("⚠️ No active session found. Please upload a file in the Upload tab first.")
            st.info("💡 After uploading a file, you can ask questions about your data here.")
            
            # Show example queries
            with st.expander("💡 Example Queries (after uploading data)"):
                st.markdown("""
                **Statistical Queries:**
                - "What's the average salary by department?"
                - "Show me the median age"
                - "What's the standard deviation of revenue?"
                
                **Comparative Queries:**
                - "Which department has the highest average salary?"
                - "Compare sales between Q1 and Q2"
                - "Show me the top 10 customers by revenue"
                
                **Trend Queries:**
                - "Show me sales over time"
                - "How has revenue changed in the last quarter?"
                - "Display monthly trends for user signups"
                
                **Distribution Queries:**
                - "What is the distribution of ages?"
                - "Show me how salaries are distributed"
                
                **Debug Queries:**
                - "Why did the row count drop after my last change?"
                - "What operations were performed on this data?"
                """)
            return
        
        # Initialize chatbot state
        self.initialize_chatbot_state(session_id)
        
        history_key = f"chatbot_history_{session_id}"
        thread_id_key = f"chatbot_thread_id_{session_id}"
        
        # Get session summary for context display
        try:
            session_summary = self.session_loader.get_session_summary(session_id)
            
            # Display session info
            with st.expander("📋 Session Information", expanded=False):
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**Session ID:** {session_id[:20]}...")
                    st.write(f"**Tables:** {session_summary.get('table_count', 0)}")
                with col2:
                    if session_summary.get('file_name'):
                        st.write(f"**File:** {session_summary.get('file_name')}")
                    if session_summary.get('file_type'):
                        st.write(f"**Type:** {session_summary.get('file_type')}")
        except Exception as e:
            self.logger.warning(f"Could not load session summary: {e}")
        
        st.divider()
        
        # Display chat history
        chat_history = st.session_state.get(history_key, [])
        
        # Display all messages
        for msg in chat_history:
            is_user = msg.get("role") == "user"
            self.display_chat_message(msg, is_user=is_user)
        
        # Chat input
        user_query = st.chat_input("Ask anything about your data...")
        
        if user_query:
            # Add user message to history
            user_message = {
                "role": "user",
                "content": user_query,
                "timestamp": datetime.now().timestamp()
            }
            chat_history.append(user_message)
            st.session_state[history_key] = chat_history
            
            # Display user message
            self.display_chat_message(user_message, is_user=True)
            
            # Process query and get response
            with st.spinner("🤔 Thinking..."):
                try:
                    # Run async function
                    thread_id = st.session_state.get(thread_id_key, session_id)
                    response_dict = asyncio.run(
                        self.agent.process_chat_query(
                            session_id,
                            user_query,
                            st.session_state,
                            thread_id
                        )
                    )
                    
                    # Format response with visualization if needed
                    viz_config = response_dict.get("visualization", {}).get("chart_config")
                    formatted_response = self.response_formatter.format_response(
                        response_dict.get("text_response", ""),
                        viz_config,
                        session_id
                    )
                    
                    # Extract visualization if generated
                    visualization_data = None
                    if formatted_response.get("visualization", {}).get("chart_figure"):
                        visualization_data = {
                            "needed": True,
                            "chart_figure": formatted_response["visualization"]["chart_figure"],
                            "chart_type": formatted_response["visualization"]["chart_type"]
                        }
                    
                    # Create assistant message
                    assistant_message = {
                        "role": "assistant",
                        "content": formatted_response.get("text_response", ""),
                        "timestamp": datetime.now().timestamp(),
                        "visualization": visualization_data,
                        "tools_used": formatted_response.get("tools_used", [])
                    }
                    
                    # Add to history
                    chat_history.append(assistant_message)
                    st.session_state[history_key] = chat_history
                    
                    # Display assistant message
                    self.display_chat_message(assistant_message, is_user=False)
                    
                except Exception as e:
                    self.logger.error(f"Error processing chat query: {e}", exc_info=True)
                    error_message = {
                        "role": "assistant",
                        "content": f"Sorry, I encountered an error: {str(e)}",
                        "timestamp": datetime.now().timestamp(),
                        "error": True
                    }
                    chat_history.append(error_message)
                    st.session_state[history_key] = chat_history
                    self.display_chat_message(error_message, is_user=False)
                    st.error(f"Error: {str(e)}")
        
        # Clear chat button
        if chat_history:
            st.divider()
            col1, col2 = st.columns([4, 1])
            with col2:
                if st.button("🗑️ Clear Chat", key="clear_chat"):
                    st.session_state[history_key] = []
                    st.rerun()


# Create default instance for backward compatibility
_default_ui = ChatbotUI()

# Backward compatibility function
def render_chatbot_tab():
    """Main function to render the chatbot tab. Uses default ChatbotUI instance."""
    return _default_ui.render_chatbot_tab()
