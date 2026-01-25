#!/usr/bin/env python3
"""
Finance MCP Server - FastAPI Implementation
FastAPI server that mounts the FastMCP server and provides HTTP endpoints.
This is the main entry point for Render deployment.
"""

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from data import mcp

# Create ASGI app from MCP server
# Use /mcp so the full endpoint is /data/mcp
mcp_app = mcp.http_app(path="/mcp")

# Create FastAPI app with lifespan
app = FastAPI(
    title="Data MCP Server",
    description="AI-driven data analysis service with MCP protocol",
    version="1.0.0",
    lifespan=mcp_app.lifespan
)

# Add CORS middleware to allow cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount MCP server at /data endpoint
app.mount("/data", mcp_app)
print("✅ Data MCP server mounted at /data")

# Add root endpoint for service information
@app.get("/")
async def root():
    """
    Root endpoint with service information and available endpoints.
    """
    return {
        "service": "Data MCP Server",
        "status": "online",
        "version": "1.0.0",
        "description": "AI-driven data analysis service using Model Context Protocol",
        "endpoints": {
            "mcp": "/data - MCP protocol endpoint for AI tools",
            "health": "/health - Health check endpoint",
            "docs": "/docs - API documentation (Swagger UI)",
            "redoc": "/redoc - API documentation (ReDoc)"
        },
        "available_tools": [
            "get_stock_quote - Get real-time stock quotes",
            "get_market_news - Get latest financial news with sentiment",
            "get_company_overview - Get company fundamentals and overview"
        ]
    }

@app.get("/health")
async def health_check():
    """
    Health check endpoint for monitoring service status.
    Used by Render and monitoring tools.
    """
    return {
        "status": "healthy",
        "service": "Data MCP Server",
        "version": "1.0.0"
    }

# Get port from environment variable (Render sets this automatically)
PORT = int(os.environ.get("PORT", 8000))

# Determine if running in production (Render) or local development
IS_PRODUCTION = os.environ.get("RENDER", False) or os.environ.get("ENVIRONMENT") == "production"
HOST = "0.0.0.0" if IS_PRODUCTION else "localhost"

if __name__ == "__main__":
    import uvicorn
    
    # Simplified startup logging for production
    env_type = 'Production (Render)' if IS_PRODUCTION else 'Local Development'
    print(f"🚀 Starting Data MCP Server - {env_type}")
    print(f"📊 Server: http://{HOST}:{PORT}")
    print(f"🏥 Health: http://{HOST}:{PORT}/health")
    print(f"📚 Docs: http://{HOST}:{PORT}/docs")
    
    if not IS_PRODUCTION:
        # Only show detailed tool list in local development
        print("\n🔧 Available MCP Tools:")
        print("  1. initialize_data_table(table_name)")
        print("  2. get_table_summary(table_name)")
        print("  3. list_tables()")
        print("  4. undo_operation(table_name)")
        print("  5. redo_operation(table_name)")
        print("  6. drop_rows_from_table(table_name)")
        print("  7. fill_missing_values(table_name)")
        print("  8. drop_missing_values(table_name)")
        print("  9. replace_table_values(table_name)")
        print("  10. clean_string_columns(table_name)")
        print("  11. remove_outliers_from_table(table_name)")
        print("  12. select_table_columns(table_name)")
        print("  13. filter_table_rows(table_name)")
        print("  14. sample_table_rows(table_name)")
        print("  15. rename_table_columns(table_name)")
        print("  16. reorder_table_columns(table_name)")
        print("  17. sort_table_data(table_name)")
        print("  18. apply_custom_function(table_name)")
    
    # Run the server
    uvicorn.run(
        app, 
        host=HOST, 
        port=PORT,
        log_level="info",
    )