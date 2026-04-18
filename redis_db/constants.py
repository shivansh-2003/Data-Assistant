"""Redis session store configuration.

Historically this project used Upstash Redis via the Upstash REST SDK.
For Redis Cloud (official) we prefer standard Redis connectivity via `redis-py`.
"""

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# Load repo-root .env regardless of cwd (uvicorn, IDE, subprocess may use another cwd)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env", override=False)

# Upstash Redis REST API credentials
# Get these from: https://console.upstash.com/ → Your Database → REST API section
UPSTASH_REDIS_REST_URL = os.getenv("UPSTASH_REDIS_REST_URL")
UPSTASH_REDIS_REST_TOKEN = os.getenv("UPSTASH_REDIS_REST_TOKEN")

# Standard Redis (Redis Cloud, Redis Labs, local redis-py)
# If REDIS_URL is set, or both REDIS_HOST and REDIS_PASSWORD are set, the app uses
# redis_db.redis_cloud_store.RedisCloudStore. Otherwise it uses Upstash REST (legacy).
REDIS_URL = os.getenv("REDIS_URL")  # e.g. rediss://user:pass@host:port/0
REDIS_HOST = os.getenv("REDIS_HOST")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_USERNAME = os.getenv("REDIS_USERNAME")
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD")
# If unset: host/port mode defaults to plain TCP (matches minimal redis-py examples).
# Set REDIS_TLS=true when your provider requires TLS. URLs use rediss:// vs redis://.
_redis_tls_raw = os.getenv("REDIS_TLS")
REDIS_TLS: Optional[bool] = (
    None
    if _redis_tls_raw is None
    else _redis_tls_raw.strip().lower() in ("1", "true", "yes")
)


def use_redis_cloud_kv() -> bool:
    """True when env points at a standard Redis connection (not Upstash REST)."""
    if (REDIS_URL or "").strip():
        return True
    if (REDIS_HOST or "").strip() and (REDIS_PASSWORD or "").strip():
        return True
    return False

# Session TTL in seconds (default: 30 minutes)
SESSION_TTL = int(os.getenv("SESSION_TTL_MINUTES", 30)) * 60

# Redis key patterns
KEY_SESSION_TABLES = "session:{sid}:tables"
KEY_SESSION_META = "session:{sid}:meta"
KEY_VERSION_TABLES = "session:{sid}:version:{vid}:tables"
KEY_SESSION_GRAPH = "session:{sid}:graph"
