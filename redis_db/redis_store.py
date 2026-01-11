"""Core Redis operations using Upstash Redis SDK (REST API)."""

import time
import json
import base64
import logging
from typing import Dict, Optional, List, Any
import pandas as pd

from .constants import (
    UPSTASH_REDIS_REST_URL, UPSTASH_REDIS_REST_TOKEN,
    SESSION_TTL, KEY_SESSION_TABLES, KEY_SESSION_META,
    KEY_VERSION_TABLES, KEY_SESSION_GRAPH
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
    
    def _sync_version_ttls(self, session_id: str) -> None:
        """
        Sync TTL for all version keys to match the main session TTL.
        This ensures all session-related keys expire together automatically.
        
        Args:
            session_id: Session identifier
        """
        try:
            versions = self.list_versions(session_id)
            for version_id in versions:
                key_version = KEY_VERSION_TABLES.format(sid=session_id, vid=version_id)
                self.redis.expire(key_version, self.session_ttl)
        except Exception as e:
            self.logger.warning(f"Failed to sync version TTLs for {session_id}: {e}")
    
    def save_session(
        self,
        session_id: str,
        tables: Dict[str, pd.DataFrame],
        metadata: Dict
    ) -> bool:
        """
        Save DataFrames and metadata to Upstash Redis with TTL.
        All keys are set with the same TTL for automatic expiration.
        
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
            key_graph = KEY_SESSION_GRAPH.format(sid=session_id)
            
            # Serialize tables using DataFrameSerializer
            tables_bytes = self.serializer.serialize(tables)
            tables_b64 = base64.b64encode(tables_bytes).decode('utf-8')
            
            # Store tables with TTL (automatic expiration)
            self.redis.setex(key_tables, self.session_ttl, tables_b64)
            
            # Store metadata with TTL (automatic expiration)
            self.redis.setex(key_meta, self.session_ttl, json.dumps(metadata))
            
            # Ensure graph exists with TTL (automatic expiration)
            if self.redis.exists(key_graph) == 0:
                # Initialize empty graph if it doesn't exist
                empty_graph = {"nodes": [], "edges": []}
                self.redis.setex(key_graph, self.session_ttl, json.dumps(empty_graph))
            else:
                # Update TTL on existing graph
                self.redis.expire(key_graph, self.session_ttl)
            
            # Sync TTL for all existing version keys to match session TTL
            self._sync_version_ttls(session_id)
            
            self.logger.info(f"Saved session {session_id} with {len(tables)} tables (TTL: {self.session_ttl}s)")
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
        Delete session and ALL its data from Redis.
        This includes: main tables, metadata, graph, and all version tables.
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if successful, False otherwise
        """
        if not self.is_connected():
            return False
        
        try:
            # Find and delete ALL keys for this session using pattern matching
            pattern = f"session:{session_id}:*"
            cursor = 0
            all_keys = []
            
            # Scan for all keys matching this session
            while True:
                result = self.redis.scan(cursor, match=pattern, count=100)
                cursor = result[0]
                keys = result[1]
                all_keys.extend(keys)
                
                if cursor == 0:
                    break
            
            if not all_keys:
                self.logger.warning(f"No keys found for session {session_id}")
                return False
            
            # Delete all keys at once
            deleted = self.redis.delete(*all_keys)
            
            self.logger.info(f"Deleted session {session_id} - removed {deleted} keys: {len(all_keys)} found")
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
        Extend session TTL for all session keys including versions and graph.
        
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
            key_graph = KEY_SESSION_GRAPH.format(sid=session_id)
            
            # Extend main session keys
            self.redis.expire(key_tables, self.session_ttl)
            self.redis.expire(key_meta, self.session_ttl)
            self.redis.expire(key_graph, self.session_ttl)
            
            # Extend all version keys
            versions = self.list_versions(session_id)
            for version_id in versions:
                key_version = KEY_VERSION_TABLES.format(sid=session_id, vid=version_id)
                self.redis.expire(key_version, self.session_ttl)
            
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
    
    # ============================================================================
    # Version Management Methods
    # ============================================================================
    
    def save_version(
        self,
        session_id: str,
        version_id: str,
        tables: Dict[str, pd.DataFrame]
    ) -> bool:
        """
        Save a version's tables to Redis.
        
        Args:
            session_id: Session identifier
            version_id: Version identifier (e.g., "v0", "v1")
            tables: Dictionary mapping table names to DataFrames
            
        Returns:
            True if successful, False otherwise
        """
        if not self.is_connected():
            self.logger.error("Upstash Redis not connected")
            return False
        
        try:
            key = KEY_VERSION_TABLES.format(sid=session_id, vid=version_id)
            
            # Serialize tables using DataFrameSerializer
            tables_bytes = self.serializer.serialize(tables)
            tables_b64 = base64.b64encode(tables_bytes).decode('utf-8')
            
            # Store version tables with TTL
            self.redis.setex(key, self.session_ttl, tables_b64)
            
            # Extend main session TTL
            self.extend_ttl(session_id)
            
            self.logger.info(f"Saved version {version_id} for session {session_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to save version {version_id} for {session_id}: {e}")
            return False
    
    def load_version(
        self,
        session_id: str,
        version_id: str
    ) -> Optional[Dict[str, pd.DataFrame]]:
        """
        Load a specific version's tables from Redis.
        
        Args:
            session_id: Session identifier
            version_id: Version identifier
            
        Returns:
            Dictionary mapping table names to DataFrames, or None if not found
        """
        if not self.is_connected():
            return None
        
        try:
            key = KEY_VERSION_TABLES.format(sid=session_id, vid=version_id)
            data = self.redis.get(key)
            
            if data is None:
                return None
            
            # Decode base64 and deserialize
            tables_bytes = base64.b64decode(data)
            tables = self.serializer.deserialize(tables_bytes)
            
            # Extend TTL on access
            self.extend_ttl(session_id)
            
            return tables
            
        except Exception as e:
            self.logger.error(f"Failed to load version {version_id} for {session_id}: {e}")
            return None
    
    def delete_version(self, session_id: str, version_id: str) -> bool:
        """
        Delete a version and its data from Redis.
        
        Args:
            session_id: Session identifier
            version_id: Version identifier
            
        Returns:
            True if successful, False otherwise
        """
        if not self.is_connected():
            return False
        
        try:
            key = KEY_VERSION_TABLES.format(sid=session_id, vid=version_id)
            deleted = self.redis.delete(key)
            self.logger.info(f"Deleted version {version_id} for session {session_id}")
            return deleted > 0
            
        except Exception as e:
            self.logger.error(f"Failed to delete version {version_id} for {session_id}: {e}")
            return False
    
    def list_versions(self, session_id: str) -> List[str]:
        """
        List all version IDs for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            List of version ID strings
        """
        if not self.is_connected():
            return []
        
        try:
            versions = []
            pattern = KEY_VERSION_TABLES.format(sid=session_id, vid="*")
            
            # Use SCAN to find all version keys
            cursor = 0
            while True:
                result = self.redis.scan(cursor, match=pattern, count=100)
                cursor = result[0]
                keys = result[1]
                
                for key in keys:
                    try:
                        # Extract version_id from key: session:{sid}:version:{vid}:tables
                        parts = key.split(':')
                        if len(parts) >= 5 and parts[2] == "version":
                            version_id = parts[3]
                            versions.append(version_id)
                    except Exception:
                        continue
                
                if cursor == 0:
                    break
            
            return versions
            
        except Exception as e:
            self.logger.error(f"Failed to list versions for {session_id}: {e}")
            return []
    
    # ============================================================================
    # Graph Management Methods
    # ============================================================================
    
    def get_graph(self, session_id: str) -> Dict[str, Any]:
        """
        Get the graph JSON structure (nodes and edges).
        
        Args:
            session_id: Session identifier
            
        Returns:
            Dictionary with "nodes" and "edges" keys, or empty structure if not found
        """
        if not self.is_connected():
            return {"nodes": [], "edges": []}
        
        try:
            key = KEY_SESSION_GRAPH.format(sid=session_id)
            data = self.redis.get(key)
            
            if data is None:
                return {"nodes": [], "edges": []}
            
            graph = json.loads(data)
            return graph
            
        except Exception as e:
            self.logger.error(f"Failed to get graph for {session_id}: {e}")
            return {"nodes": [], "edges": []}
    
    def update_graph(
        self,
        session_id: str,
        parent_vid: Optional[str],
        new_vid: str,
        operation: str,
        query: Optional[str] = None
    ) -> bool:
        """
        Add a new node and edge to the graph.
        
        Args:
            session_id: Session identifier
            parent_vid: Parent version ID (None for initial version)
            new_vid: New version ID
            operation: Operation description/label
            query: Optional query text that created this version
            
        Returns:
            True if successful, False otherwise
        """
        if not self.is_connected():
            return False
        
        try:
            graph = self.get_graph(session_id)
            
            # Add new node
            new_node = {
                "id": new_vid,
                "label": f"{new_vid}: {operation}" if operation else new_vid,
                "operation": operation,
                "query": query,
                "timestamp": time.time()
            }
            graph["nodes"].append(new_node)
            
            # Add edge if parent exists
            if parent_vid:
                new_edge = {
                    "from": parent_vid,
                    "to": new_vid,
                    "label": operation or "Operation"
                }
                graph["edges"].append(new_edge)
            
            # Save updated graph
            key = KEY_SESSION_GRAPH.format(sid=session_id)
            self.redis.setex(key, self.session_ttl, json.dumps(graph))
            
            # Extend TTL
            self.extend_ttl(session_id)
            
            self.logger.info(f"Updated graph for {session_id}: added {new_vid}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to update graph for {session_id}: {e}")
            return False
    
    def set_current_version(self, session_id: str, version_id: str) -> bool:
        """
        Update metadata to track current version.
        
        Args:
            session_id: Session identifier
            version_id: Version identifier to set as current
            
        Returns:
            True if successful, False otherwise
        """
        if not self.is_connected():
            return False
        
        try:
            metadata = self.get_metadata(session_id) or {}
            metadata["current_version"] = version_id
            
            key_meta = KEY_SESSION_META.format(sid=session_id)
            self.redis.setex(key_meta, self.session_ttl, json.dumps(metadata))
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to set current version for {session_id}: {e}")
            return False
    
    def get_current_version(self, session_id: str) -> Optional[str]:
        """
        Get the current version ID from metadata.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Current version ID string, or None if not found
        """
        metadata = self.get_metadata(session_id)
        if metadata:
            return metadata.get("current_version")
        return None
