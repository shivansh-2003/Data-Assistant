#!/usr/bin/env python3
"""
Redis diagnostics utility for monitoring session health.
This is a read-only tool to inspect Redis state, not for cleanup.
Cleanup is handled automatically by Redis TTL expiration.
"""

from typing import Dict, List
from .redis_store import RedisStore


def get_session_diagnostics(session_id: str = None) -> Dict:
    """
    Get diagnostic information about Redis sessions.
    
    Args:
        session_id: Optional specific session to inspect
        
    Returns:
        Dictionary with diagnostic information
    """
    store = RedisStore()
    
    if not store.is_connected():
        return {"error": "Failed to connect to Redis"}
    
    diagnostics = {
        "connected": True,
        "sessions": [],
        "total_keys": 0,
        "version_keys": 0,
        "graph_keys": 0
    }
    
    try:
        if session_id:
            # Inspect specific session
            pattern = f"session:{session_id}:*"
            cursor = 0
            session_keys = []
            
            while True:
                result = store.redis.scan(cursor, match=pattern, count=100)
                cursor = result[0]
                keys = result[1]
                session_keys.extend(keys)
                
                if cursor == 0:
                    break
            
            # Get TTL for each key
            key_info = []
            for key in session_keys:
                try:
                    ttl = store.redis.ttl(key)
                    key_info.append({
                        "key": key,
                        "ttl_seconds": ttl,
                        "ttl_minutes": round(ttl / 60, 1) if ttl > 0 else ttl
                    })
                except Exception:
                    key_info.append({"key": key, "ttl_seconds": -1, "ttl_minutes": -1})
            
            diagnostics["session_id"] = session_id
            diagnostics["keys"] = key_info
            diagnostics["total_keys"] = len(session_keys)
            diagnostics["exists"] = store.session_exists(session_id)
            diagnostics["versions"] = store.list_versions(session_id)
            
        else:
            # Inspect all sessions
            sessions = store.list_sessions()
            diagnostics["sessions"] = sessions
            
            # Count all keys by type
            patterns = {
                "all": "session:*",
                "tables": "session:*:tables",
                "meta": "session:*:meta",
                "graph": "session:*:graph",
                "versions": "session:*:version:*:tables"
            }
            
            for key_type, pattern in patterns.items():
                cursor = 0
                count = 0
                
                while True:
                    result = store.redis.scan(cursor, match=pattern, count=100)
                    cursor = result[0]
                    keys = result[1]
                    count += len(keys)
                    
                    if cursor == 0:
                        break
                
                diagnostics[f"{key_type}_keys"] = count
        
        return diagnostics
        
    except Exception as e:
        diagnostics["error"] = str(e)
        return diagnostics


def print_diagnostics(session_id: str = None):
    """Print diagnostic information in a readable format."""
    print("=" * 70)
    print("🔍 Redis Session Diagnostics")
    print("=" * 70)
    print()
    
    diag = get_session_diagnostics(session_id)
    
    if "error" in diag:
        print(f"❌ Error: {diag['error']}")
        return
    
    if session_id:
        # Specific session diagnostics
        print(f"Session ID: {session_id}")
        print(f"Exists: {'✅ Yes' if diag.get('exists') else '❌ No'}")
        print(f"Total Keys: {diag.get('total_keys', 0)}")
        print(f"Versions: {', '.join(diag.get('versions', [])) or 'None'}")
        print()
        
        if diag.get('keys'):
            print("Keys and TTL:")
            print("-" * 70)
            for key_info in diag['keys']:
                key = key_info['key']
                ttl_min = key_info['ttl_minutes']
                
                # Color code based on TTL
                if ttl_min == -2:
                    status = "❌ EXPIRED"
                elif ttl_min == -1:
                    status = "⚠️  NO TTL"
                elif ttl_min < 5:
                    status = f"⏰ {ttl_min} min (expiring soon)"
                else:
                    status = f"✅ {ttl_min} min"
                
                # Shorten key for display
                key_short = key.replace(f"session:{session_id}:", "")
                print(f"  {key_short:<40} {status}")
        
    else:
        # Overall diagnostics
        print(f"✅ Connected to Redis")
        print(f"📊 Active Sessions: {len(diag.get('sessions', []))}")
        print(f"🔑 Total Keys: {diag.get('all_keys', 0)}")
        print(f"   - Main tables: {diag.get('tables_keys', 0)}")
        print(f"   - Metadata: {diag.get('meta_keys', 0)}")
        print(f"   - Graphs: {diag.get('graph_keys', 0)}")
        print(f"   - Versions: {diag.get('versions_keys', 0)}")
        print()
        
        if diag.get('sessions'):
            print("Active Sessions:")
            print("-" * 70)
            for session in diag['sessions'][:10]:
                sid = session.get('session_id', 'Unknown')
                metadata = session.get('metadata', {})
                file_name = metadata.get('file_name', 'Unknown')
                table_count = metadata.get('table_count', 0)
                print(f"  {sid[:40]:<40} {file_name[:20]:<20} ({table_count} tables)")
            
            if len(diag['sessions']) > 10:
                print(f"  ... and {len(diag['sessions']) - 10} more sessions")
    
    print()
    print("=" * 70)
    print("ℹ️  Note: All keys automatically expire after 30 minutes of inactivity")
    print("=" * 70)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        # Inspect specific session
        session_id = sys.argv[1]
        print_diagnostics(session_id)
    else:
        # Inspect all sessions
        print_diagnostics()

