"""Core Redis operations using Upstash Redis SDK (REST API)."""

import time
import json
import base64
import logging
from typing import Dict, Optional, List, Any
import pandas as pd

from .constants import (
    UPSTASH_REDIS_REST_URL, UPSTASH_REDIS_REST_TOKEN,
    SESSION_TTL, KEY_SESSION_TABLES, KEY_SESSION_META
)
from .serializer import DataFrameSerializer

logger = logging.getLogger(__name__)


class RedisStore:
    """Redis store for session data and metadata management."""
    
    def __init__(
        self,
        redis_url: Optional[str] = None,
        redis_token: Optional[str] = None,
        session_ttl: Optional[int] = None,
        serializer: Optional[DataFrameSerializer] = None
    ):
        """
        Initialize Redis store.
        
        Args:
            redis_url: Upstash Redis REST API URL (defaults to env var)
            redis_token: Upstash Redis REST API token (defaults to env var)
            session_ttl: Session TTL in seconds (defaults to SESSION_TTL constant)
            serializer: DataFrameSerializer instance (creates default if None)
        """
        self.logger = logging.getLogger(__name__)
        self.redis_url = redis_url or UPSTASH_REDIS_REST_URL
        self.redis_token = redis_token or UPSTASH_REDIS_REST_TOKEN
        self.session_ttl = session_ttl or SESSION_TTL
        self.serializer = serializer or DataFrameSerializer()
        self.redis = None
        
        self._initialize_redis()
    
    def _initialize_redis(self) -> None:
        """Initialize Upstash Redis client."""
        try:
            from upstash_redis import Redis
            
            if self.redis_url and self.redis_token:
                self.redis = Redis(url=self.redis_url, token=self.redis_token)
            else:
                self.redis = Redis.from_env()
            
            self.redis.ping()
            self.logger.info("Connected to Upstash Redis")
            
        except ImportError:
            self.logger.error("upstash-redis not installed. Run: pip install upstash-redis")
            self.redis = None
        except Exception as e:
            self.logger.error(f"Upstash Redis init error: {e}")
            self.redis = None
    
    def is_connected(self) -> bool:
        """Check if Redis is connected."""
        if self.redis is None:
            return False
        try:
            self.redis.ping()
            return True
        except Exception:
            return False
    
    def save_session(
        self,
        session_id: str,
        tables: Dict[str, pd.DataFrame],
        metadata: Dict
    ) -> bool:
        """
        Save DataFrames and metadata to Upstash Redis with TTL.
        
        Args:
            session_id: Session identifier
            tables: Dictionary mapping table names to DataFrames
            metadata: Metadata dictionary to store
            
        Returns:
            True if successful, False otherwise
        """
        if not self.is_connected():
            self.logger.error("Upstash Redis not connected")
            return False
        
        try:
            key_tables = KEY_SESSION_TABLES.format(sid=session_id)
            key_meta = KEY_SESSION_META.format(sid=session_id)
            
            # Serialize tables using DataFrameSerializer
            tables_bytes = self.serializer.serialize(tables)
            tables_b64 = base64.b64encode(tables_bytes).decode('utf-8')
            
            # Store tables with TTL
            self.redis.setex(key_tables, self.session_ttl, tables_b64)
            
            # Store metadata with TTL
            self.redis.setex(key_meta, self.session_ttl, json.dumps(metadata))
            
            self.logger.info(f"Saved session {session_id} with {len(tables)} tables")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to save session {session_id}: {e}")
            return False
    
    def load_session(self, session_id: str) -> Optional[Dict[str, pd.DataFrame]]:
        """
        Load DataFrames from Upstash Redis.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Dictionary mapping table names to DataFrames, or None if not found
        """
        if not self.is_connected():
            return None
        
        try:
            key = KEY_SESSION_TABLES.format(sid=session_id)
            data = self.redis.get(key)
            
            if data is None:
                return None
            
            # Decode base64 and deserialize using DataFrameSerializer
            tables_bytes = base64.b64decode(data)
            return self.serializer.deserialize(tables_bytes)
            
        except Exception as e:
            self.logger.error(f"Failed to load session {session_id}: {e}")
            return None
    
    def get_metadata(self, session_id: str) -> Optional[Dict]:
        """
        Get session metadata.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Metadata dictionary, or None if not found
        """
        if not self.is_connected():
            return None
        
        try:
            key = KEY_SESSION_META.format(sid=session_id)
            data = self.redis.get(key)
            
            if data is None:
                return None
            
            return json.loads(data)
            
        except Exception as e:
            self.logger.error(f"Failed to get metadata for {session_id}: {e}")
            return None
    
    def delete_session(self, session_id: str) -> bool:
        """
        Delete session and all its data from Redis.
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if successful, False otherwise
        """
        if not self.is_connected():
            return False
        
        try:
            key_tables = KEY_SESSION_TABLES.format(sid=session_id)
            key_meta = KEY_SESSION_META.format(sid=session_id)
            
            deleted = self.redis.delete(key_tables, key_meta)
            self.logger.info(f"Deleted session {session_id} ({deleted} keys)")
            return deleted > 0
            
        except Exception as e:
            self.logger.error(f"Failed to delete session {session_id}: {e}")
            return False
    
    def session_exists(self, session_id: str) -> bool:
        """
        Check if session exists.
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if session exists, False otherwise
        """
        if not self.is_connected():
            return False
        
        try:
            key = KEY_SESSION_TABLES.format(sid=session_id)
            return self.redis.exists(key) > 0
        except Exception as e:
            self.logger.error(f"Failed to check session {session_id}: {e}")
            return False
    
    def extend_ttl(self, session_id: str) -> bool:
        """
        Extend session TTL.
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if successful, False otherwise
        """
        if not self.is_connected():
            return False
        
        try:
            key_tables = KEY_SESSION_TABLES.format(sid=session_id)
            key_meta = KEY_SESSION_META.format(sid=session_id)
            
            self.redis.expire(key_tables, self.session_ttl)
            self.redis.expire(key_meta, self.session_ttl)
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to extend TTL for {session_id}: {e}")
            return False
    
    def list_sessions(self) -> List[Dict]:
        """
        List all active sessions.
        
        Returns:
            List of session dictionaries with session_id and metadata
        """
        if not self.is_connected():
            return []
        
        try:
            sessions = []
            pattern = KEY_SESSION_TABLES.replace("{sid}", "*")
            
            # Use SCAN to find all session keys
            cursor = 0
            while True:
                result = self.redis.scan(cursor, match=pattern, count=100)
                cursor = result[0]
                keys = result[1]
                
                for key in keys:
                    try:
                        session_id = key.split(':')[1]
                        metadata = self.get_metadata(session_id)
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
            self.logger.error(f"Failed to list sessions: {e}")
            return []
