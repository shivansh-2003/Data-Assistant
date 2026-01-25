"""
Core data management module for MCP Server.
Handles session state, table initialization, and data persistence via HTTP API.
"""

import logging
import os
import sys
import time
from typing import Dict, Any, Optional, List
import pandas as pd
from dotenv import load_dotenv
from .http_client import get_ingestion_client

logger = logging.getLogger(__name__)

load_dotenv()

# Feature Flags
ENABLE_HTTP_SYNC = os.getenv("ENABLE_HTTP_SYNC", "true").lower() == "true"
ENABLE_CACHE_IN_MEMORY = os.getenv("ENABLE_CACHE_IN_MEMORY", "true").lower() == "true"

# Lazy function to get Redis store from main.py if running in same process
def _get_shared_store():
    """Get Redis store from main.py if available (lazy check at runtime)."""
    try:
        # First try: check if main is already in sys.modules
        if 'main' in sys.modules:
            main_module = sys.modules['main']
            if hasattr(main_module, '_default_store'):
                store = main_module._default_store
                if store is not None:
                    logger.debug("Using shared Redis store from main.py (via sys.modules)")
                    return store
    except Exception as e:
        logger.debug(f"Could not access store via sys.modules: {e}")
    
    try:
        # Second try: import main module directly
        import main
        if hasattr(main, '_default_store'):
            store = main._default_store
            if store is not None:
                logger.info("Using shared Redis store from main.py (direct import)")
                return store
    except (ImportError, AttributeError) as e:
        logger.debug(f"Could not import main module: {e}")
    except Exception as e:
        logger.debug(f"Unexpected error accessing shared store: {e}")
    return None

# Global session state (in-memory cache)
# Structure: {session_id: {table_name: dataframe}}
session_state: Dict[str, Dict[str, pd.DataFrame]] = {}

# Global operation history for undo/redo
operation_history: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}


def _get_session_state(session_id: str) -> Dict[str, pd.DataFrame]:
    """
    Get or create session state for a given session ID.
    Automatically loads from HTTP API if session not in memory.
    
    Args:
        session_id: Unique session identifier
        
    Returns:
        Dictionary mapping table names to DataFrames
    """
    if session_id not in session_state:
        # Try direct Redis access first (same process) - lazy check
        shared_store = _get_shared_store()
        if shared_store is not None:
            try:
                tables = shared_store.load_session(session_id)
                if tables is not None and len(tables) > 0:
                    session_state[session_id] = tables
                    logger.info(f"Loaded session {session_id} from Redis store with {len(tables)} tables")
                    # Extend TTL on access
                    shared_store.extend_ttl(session_id)
                else:
                    session_state[session_id] = {}
                    logger.info(f"Session {session_id} not found in Redis store or has no tables")
            except Exception as e:
                logger.error(f"Failed to load session {session_id} from Redis store: {e}")
                session_state[session_id] = {}
        elif ENABLE_HTTP_SYNC:
            # Fall back to HTTP API (different process)
            client = get_ingestion_client()
            try:
                tables = client.load_tables_from_api(session_id)
                if tables is not None:
                    session_state[session_id] = tables
                    logger.info(f"Loaded session {session_id} from HTTP API with {len(tables)} tables")
                else:
                    # Session doesn't exist in API, create empty state
                    session_state[session_id] = {}
                    logger.info(f"Created new empty session {session_id}")
            except Exception as e:
                logger.error(f"Failed to load session {session_id} from HTTP API: {e}")
                # Create empty state as fallback
                session_state[session_id] = {}
        else:
            # Create empty state if HTTP sync is disabled
            session_state[session_id] = {}
            logger.info(f"Created new empty session {session_id} (HTTP sync disabled)")
    
    return session_state[session_id]


def _save_session_state(session_id: str, table_name: str) -> bool:
    """
    Save session state back to Redis store or HTTP API.
    
    Args:
        session_id: Unique session identifier
        table_name: Name of the table that was modified
        
    Returns:
        True if successful, False otherwise
    """
    if session_id not in session_state:
        logger.warning(f"Session {session_id} not found in memory")
        return False
    
    # Try direct Redis access first (same process) - lazy check
    shared_store = _get_shared_store()
    if shared_store is not None:
        try:
            tables_dict = session_state[session_id]
            # Get existing metadata or create new
            existing_metadata = shared_store.get_metadata(session_id) or {}
            metadata = {
                **existing_metadata,
                "last_operation": time.time(),
                "last_table_modified": table_name,
                "table_count": len(tables_dict),
                "sync_method": "direct_redis"
            }
            
            success = shared_store.save_session(session_id, tables_dict, metadata)
            if success:
                logger.info(f"Successfully saved session {session_id} to Redis store")
            else:
                logger.error(f"Failed to save session {session_id} to Redis store")
            return success
        except Exception as e:
            logger.error(f"Error saving session {session_id} to Redis store: {e}")
            return False
    
    # Fall back to HTTP API (different process)
    if not ENABLE_HTTP_SYNC:
        logger.debug(f"HTTP sync disabled, skipping save for session {session_id}")
        return True
    
    client = get_ingestion_client()
    try:
        # Save all tables in the session
        tables_dict = session_state[session_id]
        
        # Prepare metadata
        metadata = {
            "last_operation": time.time(),
            "last_table_modified": table_name,
            "table_count": len(tables_dict),
            "sync_method": "http_api"
        }
        
        success = client.save_tables_to_api(session_id, tables_dict, metadata)
        
        if success:
            logger.info(f"Successfully saved session {session_id} via HTTP API")
        else:
            logger.error(f"Failed to save session {session_id} via HTTP API")
        
        return success
        
    except Exception as e:
        logger.error(f"Error saving session {session_id} via HTTP API: {e}")
        return False


def _record_operation(session_id: str, table_name: str, operation: Dict[str, Any]) -> None:
    """
    Record an operation in the history for undo/redo functionality.
    
    Args:
        session_id: Unique session identifier
        table_name: Name of the table the operation was performed on
        operation: Operation details (type, parameters, timestamp)
    """
    if session_id not in operation_history:
        operation_history[session_id] = {}
    
    if table_name not in operation_history[session_id]:
        operation_history[session_id][table_name] = []
    
    # Add timestamp and append to history
    operation["timestamp"] = time.time()
    operation_history[session_id][table_name].append(operation)
    
    # Limit history size to prevent memory issues
    max_history = 50
    if len(operation_history[session_id][table_name]) > max_history:
        operation_history[session_id][table_name] = operation_history[session_id][table_name][-max_history:]


def initialize_table(session_id: str, table_name: str = "current") -> Dict[str, Any]:
    """
    Initialize a data table in session by loading from HTTP API.
    This should be called first to load data into the session.
    
    Args:
        session_id: Unique session identifier
        table_name: Name for the table (default: "current")
    
    Returns:
        Dictionary with success status and initialization details
    """
    try:
        # Get session state (this will auto-load from HTTP API if needed)
        session_tables = _get_session_state(session_id)
        
        if not session_tables:
            return {
                "success": False,
                "error": f"No tables found in session {session_id}. Please upload data first using the ingestion API.",
                "tables_available": [],
                "session_id": session_id
            }
        
        # If specific table_name is requested and exists, return success
        if table_name in session_tables:
            df = session_tables[table_name]
            return {
                "success": True,
                "message": f"Table '{table_name}' initialized successfully",
                "session_id": session_id,
                "table_name": table_name,
                "row_count": len(df),
                "column_count": len(df.columns),
                "columns": list(df.columns),
                "available_tables": list(session_tables.keys())
            }
        
        # If table_name doesn't exist but there are tables, suggest available ones
        available_tables = list(session_tables.keys())
        if available_tables:
            return {
                "success": True,
                "message": f"Session initialized with {len(available_tables)} tables",
                "session_id": session_id,
                "requested_table": table_name,
                "available_tables": available_tables,
                "suggestion": f"Table '{table_name}' not found. Available tables: {', '.join(available_tables)}"
            }
        
        return {
            "success": False,
            "error": f"No tables available in session {session_id}",
            "session_id": session_id
        }
        
    except Exception as e:
        logger.error(f"Failed to initialize table: {e}")
        return {
            "success": False,
            "error": f"Failed to initialize table: {str(e)}",
            "session_id": session_id
        }


def get_data_summary(session_id: str, table_name: str = "current") -> Dict[str, Any]:
    """
    Get summary statistics for a table including row count, column info, data types, and missing values.
    
    Args:
        session_id: Unique session identifier
        table_name: Name of the table (default: "current")
    
    Returns:
        Dictionary containing table summary with rows, columns, dtypes, and missing counts
    """
    try:
        session_tables = _get_session_state(session_id)
        
        if table_name not in session_tables:
            available_tables = list(session_tables.keys())
            return {
                "success": False,
                "error": f"Table '{table_name}' not found in session {session_id}",
                "available_tables": available_tables,
                "suggestion": f"Available tables: {', '.join(available_tables)}" if available_tables else "No tables available"
            }
        
        df = session_tables[table_name]
        
        # Calculate missing values
        missing_counts = df.isnull().sum().to_dict()
        missing_percentages = {
            col: (count / len(df)) * 100 for col, count in missing_counts.items()
        }
        
        # Get memory usage
        memory_usage = df.memory_usage(deep=True).sum()
        
        # Get numeric columns for basic stats
        numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
        
        summary = {
            "success": True,
            "session_id": session_id,
            "table_name": table_name,
            "shape": {
                "rows": len(df),
                "columns": len(df.columns)
            },
            "columns": list(df.columns),
            "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
            "missing_values": {
                "counts": missing_counts,
                "percentages": missing_percentages,
                "total_missing": sum(missing_counts.values()),
                "columns_with_missing": [col for col, count in missing_counts.items() if count > 0]
            },
            "memory_usage_bytes": memory_usage,
            "memory_usage_mb": round(memory_usage / (1024 * 1024), 2),
            "numeric_columns": numeric_cols,
            "categorical_columns": df.select_dtypes(include=['object', 'category']).columns.tolist(),
            "date_columns": df.select_dtypes(include=['datetime64']).columns.tolist(),
            "preview": df.head(5).to_dict(orient="records")
        }
        
        # Add basic statistics for numeric columns
        if numeric_cols:
            summary["numeric_stats"] = df[numeric_cols].describe().to_dict()
        
        return summary
        
    except Exception as e:
        logger.error(f"Failed to get table summary: {e}")
        return {
            "success": False,
            "error": f"Failed to get table summary: {str(e)}",
            "session_id": session_id,
            "table_name": table_name
        }


def list_available_tables(session_id: str) -> List[str]:
    """
    List all available tables in a session.
    
    Args:
        session_id: Unique session identifier
    
    Returns:
        List of table names
    """
    try:
        session_tables = _get_session_state(session_id)
        return list(session_tables.keys())
    except Exception as e:
        logger.error(f"Failed to list tables: {e}")
        return []


def commit_dataframe(session_id: str, table_name: str, df: pd.DataFrame) -> bool:
    """
    Commit a modified DataFrame back to session state and sync via HTTP.
    
    Args:
        session_id: Unique session identifier
        table_name: Name of the table
        df: Modified DataFrame
    
    Returns:
        True if successful, False otherwise
    """
    try:
        session_tables = _get_session_state(session_id)
        session_tables[table_name] = df
        
        # Sync to HTTP API
        return _save_session_state(session_id, table_name)
        
    except Exception as e:
        logger.error(f"Failed to commit DataFrame: {e}")
        return False


def undo_last_operation(session_id: str, table_name: str = "current") -> Dict[str, Any]:
    """
    Undo the last operation performed on a table.
    
    Args:
        session_id: Unique session identifier
        table_name: Name of the table (default: "current")
    
    Returns:
        Dictionary with undo result and updated table state
    """
    try:
        if (session_id not in operation_history or 
            table_name not in operation_history[session_id] or
            not operation_history[session_id][table_name]):
            return {
                "success": False,
                "error": f"No operations to undo for table '{table_name}' in session {session_id}",
                "session_id": session_id,
                "table_name": table_name
            }
        
        # Get the last operation
        last_operation = operation_history[session_id][table_name].pop()
        
        # For now, just return info about the undone operation
        # In a full implementation, you'd restore the previous state
        return {
            "success": True,
            "message": f"Undid operation: {last_operation.get('type', 'unknown')}",
            "session_id": session_id,
            "table_name": table_name,
            "undone_operation": last_operation,
            "operations_remaining": len(operation_history[session_id][table_name])
        }
        
    except Exception as e:
        logger.error(f"Failed to undo operation: {e}")
        return {
            "success": False,
            "error": f"Failed to undo operation: {str(e)}",
            "session_id": session_id,
            "table_name": table_name
        }


def redo_operation(session_id: str, table_name: str = "current") -> Dict[str, Any]:
    """
    Redo the last undone operation on a table.
    
    Args:
        session_id: Unique session identifier
        table_name: Name of the table (default: "current")
    
    Returns:
        Dictionary with redo result and updated table state
    """
    # Placeholder for redo functionality
    # In a full implementation, you'd reapply the undone operation
    return {
        "success": False,
        "error": "Redo functionality not yet implemented",
        "session_id": session_id,
        "table_name": table_name
    }


def get_table_data(session_id: str, table_name: str = "current") -> Optional[pd.DataFrame]:
    """
    Get the DataFrame for a specific table in a session.
    
    Args:
        session_id: Unique session identifier
        table_name: Name of the table (default: "current")
    
    Returns:
        DataFrame if found, None otherwise
    """
    try:
        session_tables = _get_session_state(session_id)
        return session_tables.get(table_name)
    except Exception as e:
        logger.error(f"Failed to get table data: {e}")
        return None