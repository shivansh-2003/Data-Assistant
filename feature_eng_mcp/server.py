#!/usr/bin/env python3
"""
Feature Engineering MCP — FastAPI entry (mount MCP at /feature-eng).
"""

import os
import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from feature_eng_mcp.feature_eng import mcp

mcp_app = mcp.http_app(path="/mcp")

app = FastAPI(
    title="Feature Engineering MCP Server",
    description="MCP tools for feature engineering (ML preprocessing)",
    version="0.1.0",
    lifespan=mcp_app.lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/feature-eng", mcp_app)


@app.get("/")
async def root():
    return {
        "service": "Feature Engineering MCP Server",
        "status": "online",
        "version": "0.1.0",
        "mcp_mount": "/feature-eng",
        "endpoints": {
            "mcp": "/feature-eng/mcp",
            "health": "/health",
            "docs": "/docs",
        },
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "Feature Engineering MCP Server", "version": "0.1.0"}


PORT = int(os.environ.get("PORT", 8010))
IS_PRODUCTION = os.environ.get("RENDER", False) or os.environ.get("ENVIRONMENT") == "production"
HOST = "0.0.0.0" if IS_PRODUCTION else "localhost"

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=HOST, port=PORT, log_level="info")
