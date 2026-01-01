"""Constants for Upstash Redis configuration."""

import os
from dotenv import load_dotenv

load_dotenv()

# Upstash Redis REST API credentials
# Get these from: https://console.upstash.com/ → Your Database → REST API section
UPSTASH_REDIS_REST_URL = os.getenv("UPSTASH_REDIS_REST_URL", None)
UPSTASH_REDIS_REST_TOKEN = os.getenv("UPSTASH_REDIS_REST_TOKEN", None)

# Session TTL in seconds (default: 30 minutes)
SESSION_TTL = int(os.getenv("SESSION_TTL_MINUTES", 30)) * 60

# Redis key patterns
KEY_SESSION_TABLES = "session:{sid}:tables"
KEY_SESSION_META = "session:{sid}:meta"
