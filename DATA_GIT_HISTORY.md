# Data Git History - Version Control for Data Transformations

## Overview

The Data Git History feature is a version control system built into the Data Assistant platform that tracks every transformation and manipulation performed on your datasets. Like Git tracks code changes, this feature tracks data changes, allowing you to visualize your data's evolution, branch from any point in history, and understand the lineage of your analysis.

---

## Why This Feature Exists

### The Problem
When working with data, especially in exploratory analysis or complex data cleaning workflows, users often:
- **Lose track of changes**: "What operations did I perform to get here?"
- **Fear experimentation**: "If I try this transformation, can I undo it?"
- **Cannot reproduce results**: "How did I create this cleaned dataset last week?"
- **Struggle with branching scenarios**: "I want to try two different approaches without losing my work"

### The Solution
Data Git History provides a safety net and navigation system for data work. Every operation creates a snapshot, building a graph that shows:
- **What** was done (operation description)
- **When** it was done (timestamp)
- **From where** (parent version)
- **With what query** (natural language or code)

This enables fearless experimentation, complete reproducibility, and visual understanding of complex data pipelines.

---

## Core Concepts

### 1. Sessions
A **session** is an isolated workspace for a dataset. When you upload a file:
- A unique session ID is generated (UUID format)
- All data and operations exist within this session
- Sessions are temporary (TTL-based) but can be extended
- Multiple users can have separate concurrent sessions

**Example**: Uploading `sales_data.csv` creates session `5c7067b8-f5c9-4378-850a-d895d43afd88`

### 2. Versions
A **version** is a snapshot of your data at a specific point in time. Each version includes:
- **Version ID**: Unique identifier (e.g., `v0`, `v1`, `v2`)
- **Complete data state**: Full copy of all tables/DataFrames
- **Metadata**: Operation description, query, timestamp, parent version
- **Graph position**: Where it sits in the history tree

**Initial Version (`v0`)**: Created automatically when you upload a file. This is your baseline.

**Subsequent Versions**: Created after each successful data manipulation operation.

### 3. The Version Graph
The version graph is a **Directed Acyclic Graph (DAG)** that visualizes your data's evolution:

```
      v0 (Initial Upload)
       |
       | "Filter Price > 100"
       v
      v1 (1000 rows → 750 rows)
       |
       | "Fill missing values with mean"
       v
      v2 (750 rows, no nulls)
      / \
     /   \
    |     | "Remove outliers"
    |     v
    |    v3 (750 rows → 720 rows)
    |
    | "Sort by date"
    v
   v4 (750 rows, sorted)
```

**Nodes**: Represent data versions
**Edges**: Represent operations/transformations
**Branches**: Multiple paths from one version (trying different approaches)

### 4. Time-To-Live (TTL) and Automatic Cleanup
Every session and its versions have a **TTL (Time-To-Live)** - currently 30 minutes of inactivity:
- **Auto-extension**: TTL refreshes when you access or modify the session
- **Unified expiration**: All components (main session, versions, graph) expire together
- **No orphaned data**: When a session expires, everything (all versions, metadata, graph) is automatically deleted
- **Redis-managed**: Cleanup happens automatically in Redis, no manual intervention needed

This ensures efficient resource usage while keeping active work safe.

---

## Architecture (High-Level)

### Storage Model
All data is stored in **Upstash Redis** (cloud-hosted, serverless Redis):

```
session:{session_id}:tables          → Current working data
session:{session_id}:metadata        → Session info (file name, creation time, current version)
session:{session_id}:graph           → Version graph (JSON with nodes/edges)
session:{session_id}:version:{v0}    → Version 0 data snapshot
session:{session_id}:version:{v1}    → Version 1 data snapshot
session:{session_id}:version:{v2}    → Version 2 data snapshot
...
```

### Key Components

**1. RedisStore (Backend Storage Layer)**
- Manages session creation, versioning, graph updates
- Handles DataFrame serialization/deserialization
- Enforces TTL consistency across all keys
- Provides atomic operations for data integrity

**2. FastAPI Ingestion Server (HTTP API)**
- Exposes endpoints for session and version management
- Handles file uploads and initial version creation
- Provides graph retrieval and branch operations
- Coordinates between Streamlit UI and Redis storage

**3. MCP Server (Data Manipulation Engine)**
- Executes actual data transformations
- Operates on the "current" session state
- Unaware of versioning (versioning is transparent)
- Returns success/failure status for each operation

**4. Streamlit UI (User Interface)**
- Displays version history graph visually
- Triggers version snapshots around operations
- Allows users to branch from any version
- Shows data previews and operation history

---

## How It Works (User Perspective)

### 1. Initial Upload
**User Action**: Upload `laptop_prices.csv` via the Upload tab

**System Response**:
- Creates new session with unique ID
- Stores data in Redis
- Creates version `v0` labeled "Initial Upload"
- Initializes graph with single root node
- All keys get 30-minute TTL

**Result**: You have a baseline version to always return to.

---

### 2. First Transformation
**User Action**: Query "Remove rows where Price > 1000"

**System Response**:
1. **Before execution**:
   - Identifies current version (from metadata): `v0`
   - Prepares to create new version

2. **During execution**:
   - MCP Server processes query
   - Filters rows (1000 rows → 850 rows)
   - Updates current session data in Redis

3. **After execution**:
   - Creates version `v1` with filtered data
   - Updates graph: adds node `v1`, edge `v0 → v1` labeled "Filter Price > 1000"
   - Updates metadata: current_version = `v1`
   - Extends TTL for all keys

**Result**: You now have two versions in history. The graph shows the lineage.

---

### 3. Continued Operations
**User Actions**: 
- "Fill missing RAM values with median" → creates `v2`
- "Remove duplicates based on Company column" → creates `v3`

**Graph Evolution**:
```
v0 → v1 → v2 → v3
```

Each operation extends the linear history. Your graph grows with each transformation.

---

### 4. Branching (Trying Alternative Approaches)
**Scenario**: You're at `v3` (cleaned data). You want to try two different analysis paths:
- Path A: Sort by Price (for price analysis)
- Path B: Sort by Company then Model (for inventory analysis)

**User Action**:
1. From the version graph, **click on `v3`** to select it
2. System branches to `v3` (copies `v3` data to current session)
3. Execute "Sort by Price ascending" → creates `v4a`
4. **Click on `v3` again** to branch again
5. Execute "Sort by Company, then by Model" → creates `v4b`

**Resulting Graph**:
```
      v0 → v1 → v2 → v3
                      / \
                     /   \
       "Sort Price" v     v "Sort Company, Model"
                   v4a   v4b
```

You now have two parallel versions from the same parent. You can continue from either branch independently.

---

### 5. Reverting to a Previous Version
**Scenario**: You made several operations (`v5`, `v6`, `v7`) but want to go back to `v4` and try a different approach.

**User Action**:
1. In the version graph, **click on node `v4`**
2. System switches to `v4` (overwrites current session with `v4` data)
3. Metadata updates: current_version = `v4`
4. Future operations create new branches from `v4`

**Result**: You haven't lost `v5-v7` (they still exist in the graph), but your current working state is now `v4`. You can continue from here or jump to any other version.

---

### 6. Automatic Cleanup (Session Expiration)
**Scenario**: You finish your analysis and close Streamlit. 30 minutes pass with no activity.

**System Response**:
- Redis TTL expires on all session keys
- **Comprehensive deletion**: 
  - Main session data (`session:{sid}:tables`)
  - All versions (`session:{sid}:version:v0`, `v1`, `v2`, etc.)
  - Graph structure (`session:{sid}:graph`)
  - Session metadata (`session:{sid}:metadata`)
- No manual cleanup needed
- No orphaned keys left behind

**Result**: Clean slate. System resources are freed automatically.

---

## Key Features in Detail

### 1. Complete Data Snapshots
Each version stores the **entire state** of your data:
- All DataFrames/tables
- Column types and schemas
- Index information
- DataFrame attributes

**Why not diffs?** Full snapshots simplify branching and ensure each version is self-contained and instantly accessible.

### 2. Operation Metadata
Each version records rich context:
- **Operation type**: "Filter", "Sort", "Fill Missing", "Custom"
- **Natural language query**: The exact query you typed
- **Timestamp**: When the operation occurred
- **Row count**: Before and after (for size tracking)
- **Column changes**: Added/removed columns

**Benefit**: You can audit and understand every step of your data pipeline.

### 3. Graph Visualization
The version graph is visualized interactively (using libraries like streamlit-agraph or Graphviz):
- **Nodes**: Color-coded by operation type or status
- **Edges**: Labeled with operation summaries
- **Interactive**: Click nodes to branch, hover for details
- **Layouts**: Hierarchical (timeline) or force-directed (network)

**Benefit**: Visual understanding of complex workflows with multiple branches.

### 4. Unified TTL Management
All session-related keys share the same TTL:
- **Synchronization**: When you extend TTL (by accessing the session), ALL keys refresh
- **Atomic cleanup**: When TTL expires, everything goes together
- **No orphans**: Fixed issues where version keys would persist after main session deletion

**Implementation**: Custom logic ensures version keys get TTL updates alongside main session keys.

### 5. No MCP Server Changes
The MCP Server (data manipulation engine) is **unaware of versioning**:
- Tools operate on the "current" session data
- No changes to tool signatures or logic
- Versioning happens at the **wrapper level** (in Streamlit/FastAPI)

**Benefit**: Clean separation of concerns. Versioning is infrastructure, not business logic.

---

## Workflows Enabled

### Exploratory Data Analysis
1. Upload raw data → `v0`
2. Try various cleaning approaches:
   - Branch A: Aggressive outlier removal
   - Branch B: Conservative outlier capping
   - Branch C: Keep all data, flag outliers
3. Compare results visually
4. Pick the best approach and continue from that branch

### Reproducible Pipelines
1. Perform analysis with full version history
2. Export graph as JSON or image
3. Document shows exact sequence: `v0 → v1 (filter) → v2 (fill) → v3 (aggregate)`
4. Anyone can replicate by following the graph

### Collaborative Scenarios (Future)
- User A creates `v0-v5`
- User B branches from `v3`, creates `v6a-v8a`
- User C branches from `v3`, creates `v6b-v9b`
- Teams compare approaches before merging insights

### Error Recovery
- Accidentally delete critical column at `v10`
- Immediately branch back to `v9`
- Continue from there, no data loss

---

## Comparison to Git

### Similarities
| Feature | Git | Data Git History |
|---------|-----|------------------|
| **Commits** | Code snapshots | Data version snapshots |
| **Branches** | Code branches | Data version branches |
| **Graph** | DAG of commits | DAG of versions |
| **Checkout** | Switch branches | Switch to version |
| **History** | Commit log | Version graph |
| **Metadata** | Commit message, author, date | Operation, query, timestamp |

### Differences
| Aspect | Git | Data Git History |
|--------|-----|------------------|
| **Storage** | Diffs (delta encoding) | Full snapshots |
| **Persistence** | Permanent (until deleted) | Temporary (TTL-based) |
| **Merge** | Automatic/manual conflict resolution | Not implemented (future feature) |
| **Scale** | Gigabytes of code history | Limited by Redis/session size (~100MB) |
| **Collaboration** | Multi-user via remotes | Single-session (for now) |
| **Push/Pull** | Sync across repos | N/A (cloud storage only) |

---

## Benefits

### For Data Scientists
- **Fearless experimentation**: Try risky transformations without fear
- **Undo superpowers**: Go back to any point, not just one step
- **Visual debugging**: See where your pipeline went wrong
- **Pipeline documentation**: Auto-generated transformation lineage

### For Data Engineers
- **Audit trails**: Complete history of data changes
- **Reproducibility**: Exact operation sequence preserved
- **Testing**: Create branches for testing transformations before applying to main flow
- **Resource management**: Automatic cleanup prevents storage bloat

### For Analysts
- **Compare scenarios**: Try multiple "what-if" analyses side-by-side
- **Rollback easily**: Made a mistake? Click to revert
- **Show your work**: Share version graph as proof of methodology
- **Collaboration-ready**: (Future) Multiple analysts can fork and merge insights

---

## Limitations and Considerations

### 1. Storage Overhead
- **Full snapshots**: Each version stores complete data, not diffs
- **Memory usage**: 10 versions of 50MB data = 500MB in Redis
- **Mitigation**: TTL-based cleanup, version pruning (keep last N versions)

### 2. Temporary Nature
- **Not persistent**: Sessions expire after inactivity
- **Not a database**: Not designed for long-term storage
- **Mitigation**: Export data/versions before session expires, or extend TTL programmatically

### 3. Single-Session Isolation
- **No collaboration**: Can't merge versions from different users
- **No remote**: Can't push/pull to shared repository
- **Future enhancement**: Add session export/import, merge strategies

### 4. Graph Complexity
- **Large graphs**: 100+ versions may become hard to visualize
- **Branch explosion**: Many branches can clutter the UI
- **Mitigation**: Filter by date/operation, collapse subtrees, prune old branches

### 5. Network Latency
- **Cloud Redis**: Every operation involves network round-trip to Upstash
- **Serialization cost**: Large DataFrames take time to pickle/unpickle
- **Mitigation**: In-memory caching (future), compression

---

## Future Enhancements

### Planned Features
1. **Diff Visualization**: Show data changes between versions (added/removed rows, value changes)
2. **Version Tagging**: Label important versions (e.g., "Clean Dataset", "Pre-Analysis")
3. **Export/Import**: Save entire session (all versions + graph) to disk, reload later
4. **Merge Operations**: Combine transformations from different branches
5. **Collaborative Sessions**: Multiple users working on same session with conflict resolution
6. **Compression**: Store versions as diffs (like Git) to reduce storage
7. **Provenance Tracking**: Track which version was used for each visualization/report
8. **Automated Pruning**: Smart cleanup (e.g., keep only branch points and heads)
9. **Search and Filter**: Find versions by operation type, date, or row count
10. **Time-Travel Queries**: "Show me the data as it was 2 hours ago"

---

## Technical Highlights (Non-Code)

### Architecture Patterns
- **Event-driven versioning**: Versions created reactively after successful operations
- **Separation of concerns**: Versioning layer is independent of transformation logic
- **Idempotency**: Branching to same version multiple times is safe
- **Atomic updates**: Graph updates use Redis transactions

### Data Flow
```
User Query 
  → Streamlit UI 
  → MCP Agent (via HTTP) 
  → Data Transformation 
  → Update Current Session (Redis) 
  → Create New Version (Redis) 
  → Update Graph (Redis) 
  → Extend TTL (Redis) 
  → Return Success 
  → UI Shows Updated Graph
```

### Key Design Decisions
1. **Why Redis?** Fast, TTL-native, serverless (Upstash), handles binary data
2. **Why full snapshots?** Simpler implementation, instant access to any version, no reconstruction
3. **Why DAG?** Supports branching, prevents cycles, models causality
4. **Why TTL?** Automatic cleanup, no manual maintenance, resource-efficient for temporary work

---

## Use Case Example: Laptop Price Dataset

### Scenario
Analyze `laptop_prices.csv` (1300 rows, 12 columns) with multiple cleaning approaches.

### Timeline

**10:00 AM** - Upload dataset
- Creates `v0` (1300 rows)
- Graph: `[v0]`

**10:05 AM** - Remove rows where Price > 5000
- Creates `v1` (1150 rows)
- Graph: `v0 → v1`

**10:10 AM** - Fill missing RAM values with median
- Creates `v2` (1150 rows, no nulls in RAM)
- Graph: `v0 → v1 → v2`

**10:15 AM** - Want to try two approaches for outliers

**Branch A: Remove outliers**
- Branch from `v2`
- Execute "Remove outliers in Price column using IQR method"
- Creates `v3a` (1050 rows)
- Graph: `v0 → v1 → v2 → v3a`

**Branch B: Cap outliers**
- Branch from `v2` again
- Execute "Cap Price outliers at 95th percentile"
- Creates `v3b` (1150 rows, Price capped)
- Graph: `v0 → v1 → v2 → [v3a, v3b]`

**10:30 AM** - Decide Branch B is better
- Continue from `v3b`
- Execute "Sort by Company, then Price"
- Creates `v4` (1150 rows, sorted)
- Final graph: `v0 → v1 → v2 → [v3a, v3b] → v4` (from v3b)

**11:00 AM** - Session still active (TTL extended with each operation)

**12:00 PM** - Export final dataset, close Streamlit

**12:30 PM** - 30 minutes of inactivity, TTL expires
- All versions (`v0` through `v4`) deleted
- Graph deleted
- Session metadata deleted
- No orphaned data

---

## Conclusion

The Data Git History feature transforms the Data Assistant from a simple data manipulation tool into a **time-traveling, branching data workbench**. It addresses the core challenges of modern data work: reproducibility, experimentation, and understanding. 

By combining Git's proven version control concepts with data-centric workflows and cloud-native infrastructure (Redis TTL, serverless), this feature enables analysts to work fearlessly, knowing every step is tracked and reversible.

Whether you're cleaning messy data, exploring multiple analytical paths, or documenting your methodology for reproducibility, the Data Git History has your back—automatically, transparently, and efficiently.

---

**Last Updated**: January 11, 2026  
**Version**: 1.0  
**Status**: Production-ready with automatic cleanup

