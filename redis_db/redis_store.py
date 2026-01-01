"""Core Redis operations using Upstash Redis SDK (REST API)."""

import time
import json
import base64
import logging
from typing import Dict, Optional, List
import pandas as pd

from .constants import (
    UPSTASH_REDIS_REST_URL, UPSTASH_REDIS_REST_TOKEN,
    SESSION_TTL, KEY_SESSION_TABLES, KEY_SESSION_META
)
from .serializer import serialize_dataframes, deserialize_dataframes

logger = logging.getLogger(__name__)

# Initialize Upstash Redis client
redis = None
try:
    from upstash_redis import Redis
    
    if UPSTASH_REDIS_REST_URL and UPSTASH_REDIS_REST_TOKEN:
        redis = Redis(url=UPSTASH_REDIS_REST_URL, token=UPSTASH_REDIS_REST_TOKEN)
    else:
        redis = Redis.from_env()
    
    redis.ping()
    logger.info("Connected to Upstash Redis")
    
except ImportError:
    logger.error("upstash-redis not installed. Run: pip install upstash-redis")
    redis = None
except Exception as e:
    logger.error(f"Upstash Redis init error: {e}")
    redis = None


def save_session(session_id: str, tables: Dict[str, pd.DataFrame], metadata: Dict) -> bool:
    """Save DataFrames and metadata to Upstash Redis with TTL."""
    if redis is None:
        logger.error("Upstash Redis not connected")
        return False
    
    try:
        key_tables = KEY_SESSION_TABLES.format(sid=session_id)
        key_meta = KEY_SESSION_META.format(sid=session_id)
        
        # Serialize tables to bytes, then base64 encode for REST API
        tables_bytes = serialize_dataframes(tables)
        tables_b64 = base64.b64encode(tables_bytes).decode('utf-8')
        
        # Store tables with TTL
        redis.setex(key_tables, SESSION_TTL, tables_b64)
        
        # Store metadata with TTL
        redis.setex(key_meta, SESSION_TTL, json.dumps(metadata))
        
        logger.info(f"Saved session {session_id} with {len(tables)} tables")
        return True
        
    except Exception as e:
        logger.error(f"Failed to save session {session_id}: {e}")
        return False


def load_session(session_id: str) -> Optional[Dict[str, pd.DataFrame]]:
    """Load DataFrames from Upstash Redis."""
    if redis is None:
        return None
    
    try:
        key = KEY_SESSION_TABLES.format(sid=session_id)
        data = redis.get(key)
        
        if data is None:
            return None
        
        # Decode base64 and deserialize
        tables_bytes = base64.b64decode(data)
        return deserialize_dataframes(tables_bytes)
        
    except Exception as e:
        logger.error(f"Failed to load session {session_id}: {e}")
        return None


def get_metadata(session_id: str) -> Optional[Dict]:
    """Get session metadata."""
    if redis is None:
        return None
    
    try:
        key = KEY_SESSION_META.format(sid=session_id)
        data = redis.get(key)
        
        if data is None:
            return None
        
        return json.loads(data)
        
    except Exception as e:
        logger.error(f"Failed to get metadata for {session_id}: {e}")
        return None


def delete_session(session_id: str) -> bool:
    """Delete session and all its data from Redis."""
    if redis is None:
        return False
    
    try:
        key_tables = KEY_SESSION_TABLES.format(sid=session_id)
        key_meta = KEY_SESSION_META.format(sid=session_id)
        
        deleted = redis.delete(key_tables, key_meta)
        logger.info(f"Deleted session {session_id} ({deleted} keys)")
        return deleted > 0
        
    except Exception as e:
        logger.error(f"Failed to delete session {session_id}: {e}")
        return False


def session_exists(session_id: str) -> bool:
    """Check if session exists."""
    if redis is None:
        return False
    
    try:
        key = KEY_SESSION_TABLES.format(sid=session_id)
        return redis.exists(key) > 0
    except Exception as e:
        logger.error(f"Failed to check session {session_id}: {e}")
        return False


def extend_ttl(session_id: str) -> bool:
    """Extend session TTL."""
    if redis is None:
        return False
    
    try:
        key_tables = KEY_SESSION_TABLES.format(sid=session_id)
        key_meta = KEY_SESSION_META.format(sid=session_id)
        
        redis.expire(key_tables, SESSION_TTL)
        redis.expire(key_meta, SESSION_TTL)
        return True
        
    except Exception as e:
        logger.error(f"Failed to extend TTL for {session_id}: {e}")
        return False


def list_sessions() -> List[Dict]:
    """List all active sessions."""
    if redis is None:
        return []
    
    try:
        sessions = []
        pattern = KEY_SESSION_TABLES.replace("{sid}", "*")
        
        # Use SCAN to find all session keys
        cursor = 0
        while True:
            result = redis.scan(cursor, match=pattern, count=100)
            cursor = result[0]
            keys = result[1]
            
            for key in keys:
                try:
                    session_id = key.split(':')[1]
                    metadata = get_metadata(session_id)
                    if metadata:
                        sessions.append({
                            "session_id": session_id,
                            "metadata": metadata
                        })
                except Exception:
                    continue
            
            if cursor == 0:
                break
        
        return sessions
        
    except Exception as e:
        logger.error(f"Failed to list sessions: {e}")
        return []


def is_connected() -> bool:
    """Check if Upstash Redis is connected."""
    if redis is None:
        return False
    try:
        redis.ping()
        return True
    except Exception:
        return False
