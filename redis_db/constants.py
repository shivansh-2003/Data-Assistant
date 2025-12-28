"""Constants for Redis backend configuration."""

import os
from datetime import timedelta

# Redis Connection Settings
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)

# Session TTL (Time To Live) in seconds
SESSION_TTL = int(os.getenv("SESSION_TTL_MINUTES", 30)) * 60  # Default: 30 minutes

# Redis Key Patterns
KEY_SESSION_TABLES = "session:{sid}:tables"
KEY_SESSION_META = "session:{sid}:meta"
KEY_SESSION_TTL = "session:{sid}:ttl"

