"""Core Redis operations for session storage."""

import redis
import time
import json
import logging
from typing import Dict, Optional, List
import pandas as pd

from .constants import (
    REDIS_HOST,
    REDIS_PORT,
    REDIS_DB,
    REDIS_PASSWORD,
    SESSION_TTL,
    KEY_SESSION_TABLES,
    KEY_SESSION_META,
    KEY_SESSION_TTL
)
from .serializer import serialize_dfs, deserialize_dfs

logger = logging.getLogger(__name__)

# Initialize Redis connection
try:
    r = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        db=REDIS_DB,
        password=REDIS_PASSWORD,
        decode_responses=False,  # We need bytes for pickle
        socket_connect_timeout=5,
        socket_timeout=5
    )
    # Test connection
    r.ping()
    logger.info(f"Connected to Redis at {REDIS_HOST}:{REDIS_PORT}")
except redis.ConnectionError as e:
    logger.error(f"Failed to connect to Redis: {e}")
    r = None
except Exception as e:
    logger.error(f"Redis initialization error: {e}")
    r = None


def save_session_tables(session_id: str, tables: Dict[str, pd.DataFrame], metadata: Dict) -> bool:
    """
    Save tables and metadata to Redis with TTL.
    
    Args:
        session_id: Unique session identifier
        tables: Dictionary mapping table names to DataFrames
        metadata: Dictionary containing session metadata
        
    Returns:
        True if successful, False otherwise
    """
    if r is None:
        logger.error("Redis connection not available")
        return False
    
    try:
        pipe = r.pipeline()
        key_tables = KEY_SESSION_TABLES.format(sid=session_id)
        key_meta = KEY_SESSION_META.format(sid=session_id)
        key_ttl = KEY_SESSION_TTL.format(sid=session_id)
        
        # Serialize tables
        tables_blob = serialize_dfs(tables)
        
        # Store tables
        pipe.set(key_tables, tables_blob)
        
        # Store metadata as JSON string
        pipe.set(key_meta, json.dumps(metadata))
        
        # Store TTL timestamp
        expire_time = int(time.time()) + SESSION_TTL
        pipe.set(key_ttl, str(expire_time))
        
        # Set TTL on all keys
        pipe.expire(key_tables, SESSION_TTL)
        pipe.expire(key_meta, SESSION_TTL)
        pipe.expire(key_ttl, SESSION_TTL)
        
        pipe.execute()
        
        logger.info(f"Saved session {session_id} with {len(tables)} tables")
        return True
        
    except Exception as e:
        logger.error(f"Failed to save session {session_id}: {e}")
        return False


def load_session_tables(session_id: str) -> Optional[Dict[str, pd.DataFrame]]:
    """
    Load tables from Redis for a session.
    
    Args:
        session_id: Unique session identifier
        
    Returns:
        Dictionary mapping table names to DataFrames, or None if not found
    """
    if r is None:
        logger.error("Redis connection not available")
        return None
    
    try:
        key = KEY_SESSION_TABLES.format(sid=session_id)
        blob = r.get(key)
        
        if blob is None:
            logger.debug(f"Session {session_id} not found in Redis")
            return None
        
        tables = deserialize_dfs(blob)
        logger.info(f"Loaded session {session_id} with {len(tables)} tables")
        return tables
        
    except Exception as e:
        logger.error(f"Failed to load session {session_id}: {e}")
        return None


def get_session_metadata(session_id: str) -> Optional[Dict]:
    """
    Get metadata for a session.
    
    Args:
        session_id: Unique session identifier
        
    Returns:
        Dictionary containing session metadata, or None if not found
    """
    if r is None:
        return None
    
    try:
        key = KEY_SESSION_META.format(sid=session_id)
        meta_str = r.get(key)
        
        if meta_str is None:
            return None
        
        return json.loads(meta_str.decode('utf-8'))
        
    except Exception as e:
        logger.error(f"Failed to load metadata for session {session_id}: {e}")
        return None


def delete_session(session_id: str) -> bool:
    """
    Manually delete a session and all its data.
    
    Args:
        session_id: Unique session identifier
        
    Returns:
        True if successful, False otherwise
    """
    if r is None:
        logger.error("Redis connection not available")
        return False
    
    try:
        keys = [
            KEY_SESSION_TABLES.format(sid=session_id),
            KEY_SESSION_META.format(sid=session_id),
            KEY_SESSION_TTL.format(sid=session_id),
        ]
        deleted = r.delete(*keys)
        logger.info(f"Deleted session {session_id} ({deleted} keys removed)")
        return deleted > 0
        
    except Exception as e:
        logger.error(f"Failed to delete session {session_id}: {e}")
        return False


def session_exists(session_id: str) -> bool:
    """
    Check if a session exists in Redis.
    
    Args:
        session_id: Unique session identifier
        
    Returns:
        True if session exists, False otherwise
    """
    if r is None:
        return False
    
    try:
        key = KEY_SESSION_TABLES.format(sid=session_id)
        return r.exists(key) > 0
    except Exception as e:
        logger.error(f"Failed to check session {session_id}: {e}")
        return False


def create_empty_session(session_id: str, metadata: Optional[Dict] = None) -> bool:
    """
    Create an empty session in Redis with TTL.
    
    Args:
        session_id: Unique session identifier
        metadata: Optional metadata dictionary
        
    Returns:
        True if successful, False otherwise
    """
    if r is None:
        logger.error("Redis connection not available")
        return False
    
    try:
        pipe = r.pipeline()
        key_tables = KEY_SESSION_TABLES.format(sid=session_id)
        key_meta = KEY_SESSION_META.format(sid=session_id)
        key_ttl = KEY_SESSION_TTL.format(sid=session_id)
        
        # Create empty tables dictionary
        empty_tables = {}
        tables_blob = serialize_dfs(empty_tables)
        
        # Store empty tables
        pipe.set(key_tables, tables_blob)
        
        # Store metadata
        if metadata is None:
            metadata = {
                "created_at": time.time(),
                "table_count": 0,
                "table_names": []
            }
        else:
            metadata.setdefault("created_at", time.time())
            metadata.setdefault("table_count", 0)
            metadata.setdefault("table_names", [])
        
        pipe.set(key_meta, json.dumps(metadata))
        
        # Store TTL timestamp
        expire_time = int(time.time()) + SESSION_TTL
        pipe.set(key_ttl, str(expire_time))
        
        # Set TTL on all keys
        pipe.expire(key_tables, SESSION_TTL)
        pipe.expire(key_meta, SESSION_TTL)
        pipe.expire(key_ttl, SESSION_TTL)
        
        pipe.execute()
        
        logger.info(f"Created empty session {session_id}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to create session {session_id}: {e}")
        return False


def extend_session_ttl(session_id: str) -> bool:
    """
    Extend session TTL (sliding window - resets expiration time).
    
    Args:
        session_id: Unique session identifier
        
    Returns:
        True if successful, False otherwise
    """
    if r is None:
        logger.error("Redis connection not available")
        return False
    
    try:
        # Check if session exists
        if not session_exists(session_id):
            logger.warning(f"Session {session_id} does not exist, cannot extend TTL")
            return False
        
        pipe = r.pipeline()
        key_tables = KEY_SESSION_TABLES.format(sid=session_id)
        key_meta = KEY_SESSION_META.format(sid=session_id)
        key_ttl = KEY_SESSION_TTL.format(sid=session_id)
        
        # Update TTL timestamp
        expire_time = int(time.time()) + SESSION_TTL
        pipe.set(key_ttl, str(expire_time))
        
        # Extend TTL on all keys
        pipe.expire(key_tables, SESSION_TTL)
        pipe.expire(key_meta, SESSION_TTL)
        pipe.expire(key_ttl, SESSION_TTL)
        
        pipe.execute()
        
        logger.debug(f"Extended TTL for session {session_id}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to extend TTL for session {session_id}: {e}")
        return False


def list_active_sessions() -> List[Dict]:
    """
    List all active sessions with their metadata.
    
    Returns:
        List of dictionaries containing session_id and metadata
    """
    if r is None:
        logger.error("Redis connection not available")
        return []
    
    try:
        sessions = []
        cursor = 0
        pattern = KEY_SESSION_TABLES.replace("{sid}", "*")
        
        while True:
            cursor, keys = r.scan(cursor, match=pattern, count=100)
            
            for key in keys:
                # Extract session_id from key (format: session:{sid}:tables)
                try:
                    session_id = key.decode('utf-8').split(':')[1]
                    metadata = get_session_metadata(session_id)
                    
                    if metadata:
                        sessions.append({
                            "session_id": session_id,
                            "metadata": metadata
                        })
                except (IndexError, Exception) as e:
                    logger.warning(f"Error parsing session key {key}: {e}")
                    continue
            
            if cursor == 0:
                break
        
        logger.info(f"Found {len(sessions)} active sessions")
        return sessions
        
    except Exception as e:
        logger.error(f"Failed to list active sessions: {e}")
        return []

