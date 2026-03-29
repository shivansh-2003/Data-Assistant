"""Constants for Upstash Redis configuration."""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load repo-root .env regardless of cwd (uvicorn, IDE, subprocess may use another cwd)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env", override=False)

# Upstash Redis REST API credentials
# Get these from: https://console.upstash.com/ → Your Database → REST API section
UPSTASH_REDIS_REST_URL = os.getenv("UPSTASH_REDIS_REST_URL")
UPSTASH_REDIS_REST_TOKEN = os.getenv("UPSTASH_REDIS_REST_TOKEN")

# Session TTL in seconds (default: 30 minutes)
SESSION_TTL = int(os.getenv("SESSION_TTL_MINUTES", 30)) * 60

# Redis key patterns
KEY_SESSION_TABLES = "session:{sid}:tables"
KEY_SESSION_META = "session:{sid}:meta"
KEY_VERSION_TABLES = "session:{sid}:version:{vid}:tables"
KEY_SESSION_GRAPH = "session:{sid}:graph"
