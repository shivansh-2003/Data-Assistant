"""Background worker for cleaning up expired sessions (optional)."""

import time
import logging
import redis
from typing import List

from .constants import REDIS_HOST, REDIS_PORT, REDIS_DB, REDIS_PASSWORD
from .redis_store import r

logger = logging.getLogger(__name__)


def cleanup_expired_sessions(scan_pattern: str = "session:*:ttl", batch_size: int = 100) -> int:
    """
    Clean up expired sessions by scanning for TTL keys and checking expiration.
    
    Args:
        scan_pattern: Redis key pattern to scan for
        batch_size: Number of keys to process per batch
        
    Returns:
        Number of sessions cleaned up
    """
    if r is None:
        logger.warning("Redis connection not available for cleanup")
        return 0
    
    try:
        cleaned = 0
        cursor = 0
        
        while True:
            # Scan for TTL keys
            cursor, keys = r.scan(cursor, match=scan_pattern, count=batch_size)
            
            if not keys:
                break
            
            # Check each key's TTL
            for key in keys:
                ttl_value = r.get(key)
                if ttl_value:
                    try:
                        expire_timestamp = int(ttl_value.decode('utf-8'))
                        current_time = int(time.time())
                        
                        if current_time >= expire_timestamp:
                            # Extract session_id from key (format: session:{sid}:ttl)
                            session_id = key.decode('utf-8').split(':')[1]
                            from .redis_store import delete_session
                            if delete_session(session_id):
                                cleaned += 1
                    except (ValueError, IndexError) as e:
                        logger.warning(f"Invalid TTL key format: {key}, {e}")
            
            if cursor == 0:
                break
        
        if cleaned > 0:
            logger.info(f"Cleaned up {cleaned} expired sessions")
        
        return cleaned
        
    except Exception as e:
        logger.error(f"Cleanup error: {e}")
        return 0


def run_cleanup_worker(interval_seconds: int = 1800):  # 30 minutes default
    """
    Run cleanup worker in a loop (for background thread/process).
    
    Args:
        interval_seconds: How often to run cleanup (default: 30 minutes)
    """
    logger.info(f"Starting cleanup worker (interval: {interval_seconds}s)")
    
    while True:
        try:
            cleanup_expired_sessions()
            time.sleep(interval_seconds)
        except KeyboardInterrupt:
            logger.info("Cleanup worker stopped")
            break
        except Exception as e:
            logger.error(f"Cleanup worker error: {e}")
            time.sleep(interval_seconds)


if __name__ == "__main__":
    # Run cleanup once if called directly
    cleanup_expired_sessions()

