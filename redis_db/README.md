# Redis session store (`redis_db`)

Sessions: DataFrames, JSON metadata, version snapshots, and a small lineage graph. Keys expire via **TTL** (`SESSION_TTL`, from `SESSION_TTL_MINUTES`).

## Backends (auto-selected)

- **Standard Redis** (`redis-py`): used when **`REDIS_URL`** is set, or **`REDIS_HOST` + `REDIS_PASSWORD`** are set (Redis Cloud, Redis Labs, local).
- **Upstash REST (legacy)**: used when neither of the above is set; configure **`UPSTASH_REDIS_REST_URL`** + **`UPSTASH_REDIS_REST_TOKEN`**.

### Minimal Redis Cloud / Redis Labs

**Option A — URL:** `REDIS_URL=rediss://user:pass@host:port/0` (`rediss` = TLS; `redis` = no TLS)

**Option B — host + password:** `REDIS_HOST`, `REDIS_PASSWORD`, optional `REDIS_PORT` (default `6379`). Username defaults to `default` if omitted.

**TLS:** Host/port mode defaults to **plain TCP** (matches simple `redis.Redis(host=..., ssl=False)` examples). Set **`REDIS_TLS=true`** if your endpoint requires TLS.

## Layout

| Key pattern | Content |
|-------------|---------|
| `session:{sid}:tables` | Base64 pickle of `{table_name: DataFrame}` |
| `session:{sid}:meta` | JSON metadata |
| `session:{sid}:graph` | JSON `{nodes, edges}` |
| `session:{sid}:version:{vid}:tables` | Version snapshot (same encoding as tables) |

## Files

- **`constants.py`** — Loads `.env` from repo root; `UPSTASH_*`, `SESSION_TTL`, key format strings.
- **`session_store.py`** — `BaseSessionStore` + `get_session_store()` factory.
- **`store_common.py`** — Shared JSON/lineage helpers and `current_version` mixin.
- **`serializer.py`** — Pickle encode/decode for DataFrame dicts.
- **`redis_store.py`** — `RedisStore` (Upstash REST).
- **`redis_cloud_store.py`** — `RedisCloudStore` (`redis-py`).
- **`diagnostics.py`** — Optional CLI: `python -m redis_db.diagnostics` or `python diagnostics.py [session_id]`.

## Flow

```mermaid
flowchart LR
    A[Write path] --> B[Serialize tables]
    B --> C["SET (ex=TTL) tables + meta + graph"]
    C --> D[Versions / graph updates]
    D --> E[TTL aligned]
    F[Read path] --> G[GET + deserialize]
```

Version snapshots use `session:{sid}:version:{vid}:tables`; the lineage graph is JSON on `session:{sid}:graph` (`nodes` / `edges`).
