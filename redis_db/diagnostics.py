"""Read-only Redis session inspection (CLI / ops)."""

from typing import Dict, List, Optional

from .constants import SESSION_TTL
from .session_store import get_session_store


def get_session_diagnostics(session_id: Optional[str] = None) -> Dict:
    """Summarize connectivity, key counts, and optionally one session's keys/TTL."""
    store = get_session_store()

    if not store.is_connected():
        return {"error": "Failed to connect to Redis"}

    diagnostics: Dict = {
        "connected": True,
        "sessions": [],
        "total_keys": 0,
        "version_keys": 0,
        "graph_keys": 0,
    }

    try:
        if session_id:
            pattern = f"session:{session_id}:*"
            # Both backends expose scan_keys/count_keys helpers.
            session_keys = store.scan_keys(pattern)  # type: ignore[attr-defined]
            key_info: List[Dict] = []
            for key in session_keys:
                try:
                    ttl = store.redis.ttl(key)
                    key_info.append(
                        {
                            "key": key,
                            "ttl_seconds": ttl,
                            "ttl_minutes": round(ttl / 60, 1) if ttl > 0 else ttl,
                        }
                    )
                except Exception:
                    key_info.append(
                        {"key": key, "ttl_seconds": -1, "ttl_minutes": -1}
                    )

            diagnostics["session_id"] = session_id
            diagnostics["keys"] = key_info
            diagnostics["total_keys"] = len(session_keys)
            diagnostics["exists"] = store.session_exists(session_id)
            diagnostics["versions"] = store.list_versions(session_id)
        else:
            diagnostics["sessions"] = store.list_sessions()  # type: ignore[attr-defined]
            patterns = {
                "all": "session:*",
                "tables": "session:*:tables",
                "meta": "session:*:meta",
                "graph": "session:*:graph",
                "versions": "session:*:version:*:tables",
            }
            for key_type, pattern in patterns.items():
                diagnostics[f"{key_type}_keys"] = store.count_keys(pattern)  # type: ignore[attr-defined]

        return diagnostics

    except Exception as e:
        diagnostics["error"] = str(e)
        return diagnostics


def print_diagnostics(session_id: Optional[str] = None) -> None:
    """Pretty-print `get_session_diagnostics` to stdout."""
    ttl_min = max(1, SESSION_TTL // 60)

    print("=" * 70)
    print("Redis Session Diagnostics")
    print("=" * 70)
    print()

    diag = get_session_diagnostics(session_id)

    if "error" in diag:
        print(f"Error: {diag['error']}")
        return

    if session_id:
        print(f"Session ID: {session_id}")
        print(f"Exists: {'Yes' if diag.get('exists') else 'No'}")
        print(f"Total Keys: {diag.get('total_keys', 0)}")
        print(f"Versions: {', '.join(diag.get('versions', [])) or 'None'}")
        print()
        if diag.get("keys"):
            print("Keys and TTL:")
            print("-" * 70)
            for key_info in diag["keys"]:
                key = key_info["key"]
                ttl_min_val = key_info["ttl_minutes"]
                if ttl_min_val == -2:
                    status = "EXPIRED"
                elif ttl_min_val == -1:
                    status = "NO TTL"
                elif ttl_min_val < 5:
                    status = f"{ttl_min_val} min (expiring soon)"
                else:
                    status = f"{ttl_min_val} min"
                short = key.replace(f"session:{session_id}:", "")
                print(f"  {short:<40} {status}")
    else:
        print("Connected to Redis")
        print(f"Active Sessions: {len(diag.get('sessions', []))}")
        print(f"Total Keys: {diag.get('all_keys', 0)}")
        print(f"   - Main tables: {diag.get('tables_keys', 0)}")
        print(f"   - Metadata: {diag.get('meta_keys', 0)}")
        print(f"   - Graphs: {diag.get('graph_keys', 0)}")
        print(f"   - Versions: {diag.get('versions_keys', 0)}")
        print()
        if diag.get("sessions"):
            print("Active Sessions:")
            print("-" * 70)
            for session in diag["sessions"][:10]:
                sid = session.get("session_id", "Unknown")
                metadata = session.get("metadata", {})
                file_name = metadata.get("file_name", "Unknown")
                table_count = metadata.get("table_count", 0)
                print(f"  {sid[:40]:<40} {file_name[:20]:<20} ({table_count} tables)")
            if len(diag["sessions"]) > 10:
                print(f"  ... and {len(diag['sessions']) - 10} more sessions")

    print()
    print("=" * 70)
    print(f"Note: keys use TTL from SESSION_TTL (~{ttl_min} min with defaults)")
    print("=" * 70)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        print_diagnostics(sys.argv[1])
    else:
        print_diagnostics()
