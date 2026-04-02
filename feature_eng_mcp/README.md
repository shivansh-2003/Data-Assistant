# Feature Engineering MCP Server

FastMCP + FastAPI server for advanced feature engineering (aligned with *Feature Engineering for Machine Learning*). Complements [`data_mcp`](../data_mcp) with scaling, transforms, encoding, text features, PCA, k-means featurization, selection, and pipelines.

## Run locally

From the **repository root** (so `data_mcp` session imports resolve):

```bash
cd /path/to/Data-Assistant
pip install -r feature_eng_mcp/requirements.txt
uvicorn feature_eng_mcp.server:app --host 0.0.0.0 --port 8010 --reload
```

Default `PORT` in `server.py` is **8010** (Data MCP often uses 8000). Override with `PORT=8011` when invoking `python -m uvicorn ...`.

- Health: `http://localhost:8010/health`
- MCP HTTP app: mounted at **`/feature-eng`** (e.g. SSE/streamable MCP clients use `/feature-eng/mcp` per FastMCP routing)

## Environment

| Variable | Purpose |
|----------|---------|
| `INGESTION_API_URL` / `FASTAPI_URL` | Backend base URL for session table load/save (default production URL in `http_client.py`, override for local API) |
| `PORT` | Listen port (Render) |
| `ENABLE_HTTP_SYNC` | Passed through to shared `data_mcp` core when set |

## Session tools

Call `initialize_data_table` first (loads session from the same FastAPI/Redis pipeline as Data MCP). Feature tools take `session_id` and `table_name`.

## Deploy note

Run with **repo root** on `PYTHONPATH` or use `uvicorn feature_eng_mcp.server:app` from repo root so `data_mcp.data_functions.core` imports succeed.
