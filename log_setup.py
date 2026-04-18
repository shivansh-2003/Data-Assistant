"""
Centralized logging configuration for Data Assistant.

Call ``setup_logging()`` once at startup — both ``app.py`` (Streamlit) and
``main.py`` (FastAPI/uvicorn) call it.  Subsequent calls are no-ops.

Logs go to **stderr** so they appear in the terminal where you ran:
    streamlit run app.py
    # or
    python main.py

Environment variables
---------------------
LOG_LEVEL   DEBUG / INFO / WARNING / ERROR  (default: INFO)
LOG_FILE    path to write a rotating file log alongside the console log
"""

import logging
import os
import sys


def setup_logging(level: str | None = None) -> None:
    """Configure root logger.  Idempotent — safe to call multiple times."""
    root = logging.getLogger()

    # Guard: already configured by us
    if getattr(root, "_data_assistant_configured", False):
        return

    log_level = getattr(
        logging,
        (level or os.getenv("LOG_LEVEL", "INFO")).upper(),
        logging.INFO,
    )
    root.setLevel(log_level)

    fmt = "%(asctime)s | %(levelname)-8s | %(name)-35s | %(message)s"
    datefmt = "%H:%M:%S"
    formatter = logging.Formatter(fmt, datefmt=datefmt)

    # ── stderr console handler (shows in Streamlit terminal) ─────────────────
    console = logging.StreamHandler(sys.stderr)
    console.setLevel(log_level)
    console.setFormatter(formatter)
    root.addHandler(console)

    # ── optional file handler ─────────────────────────────────────────────────
    log_file = os.getenv("LOG_FILE", "")
    if log_file:
        try:
            from logging.handlers import RotatingFileHandler
            fh = RotatingFileHandler(log_file, maxBytes=10 * 1024 * 1024, backupCount=3)
            fh.setLevel(log_level)
            fh.setFormatter(formatter)
            root.addHandler(fh)
        except OSError as exc:
            root.warning("Could not open log file %s: %s", log_file, exc)

    # ── silence noisy third-party loggers ────────────────────────────────────
    _noisy = (
        "httpx", "httpcore", "urllib3", "asyncio",
        "langchain", "openai", "anthropic",
        "watchdog", "botocore", "boto3",
        "multipart", "uvicorn.access",
    )
    for name in _noisy:
        logging.getLogger(name).setLevel(logging.WARNING)

    root._data_assistant_configured = True  # type: ignore[attr-defined]
    root.info("Logging initialised  level=%s", logging.getLevelName(log_level))
