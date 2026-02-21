# Data Assistant Platform

A powerful, multi-modal data analysis platform that lets you upload messy real-world files, clean and transform data with natural language queries, and analyze data — all through an intuitive web interface powered by AI.

## 📋 Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Features](#features)
- [Installation](#installation)
- [Configuration](#configuration)
  - [Secrets Setup Guide](SECRETS_SETUP.md) 🔐
- [Usage](#usage)
- [API Documentation](#api-documentation)
- [Project Structure](#project-structure)
- [Components](#components)
- [Development](#development)
- [Troubleshooting](#troubleshooting)

## 🎯 Overview

The Data Assistant Platform is a comprehensive data analysis solution that combines:

- **Smart File Ingestion**: Automatically extracts tables from CSV, Excel, and images
- **Natural Language Data Manipulation**: Transform data using plain English queries powered by LLM
- **Session Management**: Persistent data storage with automatic TTL expiration
- **MCP Integration**: Model Context Protocol server for safe, tool-based data operations
- **Modern UI**: Streamlit-based interface with real-time feedback

### Key Technologies

- **Backend**: FastAPI (REST API)
- **Frontend**: Streamlit (Web UI)
- **Data Storage**: Upstash Redis (Cloud Redis with TTL management)
- **AI/ML**: 
  - LangChain (Agent framework, tool integration)
  - LangGraph (Stateful conversation flow, MemorySaver checkpointing)
  - OpenAI GPT-4o (schema reasoning, code generation) + GPT-4o-mini (intent classification, summarization, suggestions)
  - LLM singleton registry (`chatbot/llm_registry.py`) — eliminates ~1.4s per-query init overhead
- **Data Processing**: Pandas, NumPy
- **Visualization**: Plotly (interactive charts), Kaleido (PNG/SVG export)
- **MCP Server**: FastMCP for tool-based data operations

### 🌐 Production Deployment

**Live Services:**

| Service | URL | Platform | Status |
|---------|-----|----------|--------|
| **Streamlit UI** | https://data-assistant-mu6xtnwivdpi8umtp94wuh.streamlit.app/ | Streamlit Cloud | ✅ Live |
| **FastAPI Backend** | https://data-assistant-m4kl.onrender.com | Render | ✅ Live |
| **MCP Server** | https://data-analyst-mcp-server.onrender.com | Render | ✅ Live |


### **Quick Start - Use Live Deployment:**

🌐 **Access the live app instantly (no setup required):**

👉 **https://data-assistant-mu6xtnwivdpi8umtp94wuh.streamlit.app/**

All backend services are already running in production!

**For Local Development:**
```bash
# 1. Clone repo
git clone <repository-url>
cd Data-Assistant

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set up secrets (see Configuration section)
cp .streamlit/secrets.toml.template .streamlit/secrets.toml
# Edit secrets.toml with your OpenAI API key

# 4. Run Streamlit locally (connects to production backend automatically)
streamlit run app.py
```

**Benefits:**
- ✅ **Fully deployed UI** - Access from anywhere
- ✅ No need to run MCP server locally
- ✅ No need to run FastAPI backend locally  
- ✅ Always-on data processing services
- ✅ Faster setup for new users
- ✅ Consistent environment across team

## 🏗 Architecture

### System Architecture Overview

```mermaid
graph TB
    subgraph "Frontend Layer"
        UI[Streamlit UI<br/>app.py]
        UT[Upload Tab]
        MT[Data Manipulation Tab]
        VT[Visualization Tab]
        CT[Chatbot Tab]
        
        UI --> UT
        UI --> MT
        UI --> VT
        UI --> CT
    end
    
    subgraph "Backend Layer"
        API[FastAPI Server<br/>main.py]
        ING[Ingestion Module]
        REDIS[Redis Store<br/>Upstash Redis]
        
        API --> ING
        API --> REDIS
    end
    
    subgraph "Data Processing Layer"
        MCP[MCP Server<br/>data-mcp/]
        MCPC[MCP Client<br/>mcp_client.py]
        BOT[Chatbot Module<br/>chatbot/]
        
        MCP --> MCPC
        MCPC --> BOT
    end
    
    subgraph "AI Layer"
        LLM[OpenAI GPT-4o / GPT-4o-mini<br/>LangChain]
        TOOLS[18+ Data Tools]
        
        LLM --> TOOLS
    end
    
    UI -->|HTTP Requests| API
    MT -->|Natural Language Query| MCPC
    CT -->|Chat Query| BOT
    VT -->|Chart Request| REDIS
    ING -->|Store Data| REDIS
    MCPC -->|Tool Calls| MCP
    BOT -->|DataFrame Query| LLM
    MCP -->|CRUD Operations| REDIS
    
    style UI fill:#e1f5ff
    style API fill:#fff4e1
    style REDIS fill:#ffe1e1
    style MCP fill:#e1ffe1
    style LLM fill:#f0e1ff
```


### Component Interaction Map

```mermaid
graph LR
    subgraph "Ingestion Pipeline"
        F[File Upload] --> IH[Ingestion Handler]
        IH --> CSV[CSV Handler]
        IH --> XLS[Excel Handler]
        IH --> IMG[Image Handler<br/>OCR]
        
        CSV --> DF[DataFrames]
        XLS --> DF
        IMG --> DF
    end
    
    subgraph "Storage Layer"
        DF --> SER[Serializer]
        SER --> RED[(Redis<br/>Upstash)]
        RED --> KEYS[Key Structure]
        KEYS --> ST[session:tables]
        KEYS --> SM[session:metadata]
        KEYS --> SG[session:graph]
        KEYS --> SV[session:versions]
    end
    
    subgraph "Processing Layer"
        RED --> LOAD[Load Session]
        LOAD --> AGENT[LangChain Agent]
        AGENT --> TOOLS[MCP Tools]
        TOOLS --> OPS[Data Operations]
        OPS --> RED
    end
    
    style F fill:#4CAF50
    style RED fill:#FF5722
    style AGENT fill:#2196F3
    style TOOLS fill:#FFC107
```

## ✨ Features

### 1. Multi-Format File Upload
- **CSV/TSV**: Automatic delimiter detection
- **Excel**: Multi-sheet support (.xlsx, .xls, .xlsm)
- **Images**: OCR-based table extraction (PNG, JPEG, TIFF, BMP)

#### File Ingestion Pipeline

```mermaid
flowchart TD
    UPLOAD[File Upload] --> VALIDATE{Validate File}
    VALIDATE -->|Size OK| DETECT{Detect File Type}
    VALIDATE -->|Too Large| ERR_SIZE[Error: File Too Large]
    
    DETECT -->|.csv, .tsv| CSV[CSV Handler]
    DETECT -->|.xlsx, .xls| EXCEL[Excel Handler]
    DETECT -->|.png, .jpg| IMAGE[Image Handler]
    DETECT -->|Unknown| ERR_TYPE[Error: Unsupported Type]
    
    CSV --> CSV_PARSE[Parse CSV<br/>- Detect delimiter<br/>- Detect encoding<br/>- Handle quotes]
    EXCEL --> EXCEL_PARSE[Parse Excel<br/>- Read all sheets<br/>- Preserve names<br/>- Handle formulas]
    IMAGE --> IMG_PARSE[OCR Processing<br/>- Image preprocessing<br/>- Text extraction<br/>- Table detection]
    
    CSV_PARSE --> DF[DataFrames]
    EXCEL_PARSE --> DF
    IMG_PARSE --> DF
    
    DF --> VALIDATE_DATA{Validate Data}
    VALIDATE_DATA -->|Valid| SERIALIZE[Serialize<br/>Pickle + Base64]
    VALIDATE_DATA -->|Empty/Invalid| ERR_DATA[Error: No Data]
    
    SERIALIZE --> REDIS[(Store in Redis)]
    REDIS --> SESSION[Create Session<br/>session:tables<br/>session:metadata]
    SESSION --> VERSION[Create v0 Version]
    VERSION --> RESPONSE[Return Session ID]
    RESPONSE --> END([Success])
    
    ERR_SIZE --> END
    ERR_TYPE --> END
    ERR_DATA --> END
    
    style UPLOAD fill:#4CAF50
    style DF fill:#2196F3
    style REDIS fill:#FF5722
    style END fill:#4CAF50
    style ERR_SIZE fill:#F44336
    style ERR_TYPE fill:#F44336
    style ERR_DATA fill:#F44336
```


### 2. Data Manipulation Tab
- **Natural Language Queries**: Describe operations in plain English
- **Operation History**: Track all operations with timestamps
- **Real-time Preview**: See data changes immediately
- **Session Persistence**: Data persists across page reloads

### 3. Visualization Centre Tab
- **Cached Data Fetching**: Three-layer cache (session_state → `@st.cache_data` TTL → FastAPI) eliminates redundant HTTP calls on every rerender
- **Figure Memoization**: Chart config hashed to MD5 key; same config = instant re-render from cache, no spinner
- **Lazy Exports**: Kaleido (PNG/SVG/PDF) only invoked on an explicit "Generate" button click — results cached by hash; previously blocked every render for ~5s
- **8 Chart Types**: Bar, Line, Scatter, Area, Box, Histogram, Pie, Heatmap
- **Interactive Visualizations**: Zoom, pan, hover tooltips
- **Column Mapping**: Easy X/Y axis and color grouping selection
- **Aggregations**: Sum, mean, count, min, max for grouped data
- **Theme-Aware**: Automatically adapts to light/dark mode
- **Cache Invalidation**: `on_data_changed()` busts all visualization caches when data is manipulated

#### Visualization Generation Pipeline

```mermaid
flowchart TD
    START([User Selects Chart Options]) --> SESSION[Load Session Data]
    SESSION --> TABLE{Select Table}
    
    TABLE --> CONFIG[Chart Configuration<br/>- Chart Type<br/>- X Column<br/>- Y Column<br/>- Color Column<br/>- Aggregation]
    
    CONFIG --> VALIDATE{Validate Columns}
    VALIDATE -->|Invalid| ERROR[Show Error]
    VALIDATE -->|Valid| AGG{Aggregation Needed?}
    
    AGG -->|Yes| GROUP[Group By X Column]
    AGG -->|No| DIRECT[Use Raw Data]
    
    GROUP --> APPLY[Apply Aggregation<br/>sum, mean, count, min, max]
    APPLY --> BUILD
    DIRECT --> BUILD
    
    BUILD[Build Plotly Figure] --> TYPE{Chart Type}
    
    TYPE -->|Bar| BAR[px.bar]
    TYPE -->|Line| LINE[px.line]
    TYPE -->|Scatter| SCATTER[px.scatter]
    TYPE -->|Area| AREA[px.area]
    TYPE -->|Box| BOX[px.box]
    TYPE -->|Histogram| HIST[px.histogram]
    TYPE -->|Pie| PIE[px.pie]
    TYPE -->|Heatmap| HEAT[px.heatmap]
    
    BAR --> THEME[Apply Theme]
    LINE --> THEME
    SCATTER --> THEME
    AREA --> THEME
    BOX --> THEME
    HIST --> THEME
    PIE --> THEME
    HEAT --> THEME
    
    THEME --> RENDER[Render with Plotly]
    RENDER --> DISPLAY[Display in Streamlit]
    
    DISPLAY --> EXPORT{Export?}
    EXPORT -->|PNG| KALEIDO[Kaleido Export]
    EXPORT -->|SVG| KALEIDO
    EXPORT -->|HTML| HTML_EXPORT[HTML Export]
    EXPORT -->|No| END
    
    KALEIDO --> END([Chart Ready])
    HTML_EXPORT --> END
    ERROR --> END
    
    style START fill:#4CAF50
    style BUILD fill:#2196F3
    style RENDER fill:#FF9800
    style END fill:#4CAF50
```

### 4. InsightBot — Intelligent Chatbot Tab
- **🤖 LangGraph architecture**: State graph with router, analyzer, planner, insight, viz, responder, clarification, and suggestion nodes; persistent memory via MemorySaver.
- **⚡ Streaming UI**: `graph.stream(stream_mode='values')` renders the response as soon as the responder node completes — ~1–2s perceived vs 15s all-or-nothing. Progressive status captions shown while nodes run.
- **🔋 LLM singleton registry** (`chatbot/llm_registry.py`): One `ChatOpenAI` instance per `(model, temperature, max_tokens)` config, reused process-wide. Eliminates ~1.4s of repeated init overhead per query.
- **🎯 Smart model assignment**: gpt-4o-mini for routing, context resolution, summarization, and suggestions (~5.5s saved); gpt-4o kept only for analyzer, planner, and code generator where schema reasoning is required.
- **⏭️ Planner skip**: ~80% of queries bypass the planner node entirely (saving ~2s) via a keyword + sub-intent complexity gate. Complex queries (YoY, cohort, rolling average, trend) still use the full planner path.
- **💬 Multi-turn conversations**: Context-aware follow-ups (e.g. "What about the maximum?" resolved into full questions); conversation context tracks last columns, aggregation, and filters.
- **🔍 Column clarification**: When multiple columns match a term (e.g. "sales"), asks "Did you mean X or Y?" and resolves on the next turn.
- **💡 Suggestion engine**: After each response, three contextual follow-up questions as clickable chips. Intent-aware pre-defined fallbacks ensure chips always appear even on LLM failure.
- **📊 Per-turn visualizations**: Each AI message keeps its own chart/table/code; previous visualizations stay visible (response_snapshots).
- **📋 Report & summarize**: "Give me a report on X" and "summarize that" / "what does that show?" using the last result.
- **🔧 Function calling**: Analyzer selects tools (insight_tool, bar_chart, line_chart, scatter_chart, histogram, heatmap_chart, correlation_matrix, etc.) via LLM.
- **🎯 Intent classification**: Routes to data_query, visualization_request, small_talk, report, summarize_last; triggers clarification when needed.
- **⚡ Safe code execution**: LLM-generated pandas code runs in a sandbox with timeout and guardrails; rule-based executor handles simple queries (mean, sum, count, min, max) with zero LLM calls.
- **📈 Charts in chat**: Plotly charts and tables per response; heatmap for correlation queries; fallback to table when chart fails (e.g. too many categories).
- **📝 Query types**: Statistical, comparative, filtering, visualization, correlation, report, summarize_last, and follow-ups.

**InsightBot latency targets after optimizations:**

| Query type | Wall clock | Perceived (streaming) |
|---|---|---|
| Simple stat (avg/sum/count) | ~4s | ~1s |
| Comparison / groupby | ~6s | ~2s |
| Visualization request | ~5s | ~1.5s |
| Follow-up | ~7s | ~2s |
| Complex (YoY, cohort) | ~10s | ~3s |
| Small talk | ~1s | ~0.5s |



#### InsightBot LangGraph Architecture

```mermaid
flowchart TD
    START([User Query]) --> ROUTER[Router Node<br/>gpt-4o-mini · Intent + Context]
    
    ROUTER --> ROUTE{Route}
    ROUTE -->|needs_clarification| CLARIFY[Clarification Node<br/>"Did you mean X or Y?"]
    ROUTE -->|small_talk| RESPONDER[Responder Node]
    ROUTE -->|summarize_last| INSIGHT[Insight Node]
    ROUTE -->|data_query / viz / report| ANALYZER[Analyzer Node<br/>gpt-4o · Tool Selection]
    
    CLARIFY --> END1([END])
    
    ANALYZER --> PLANNER_GATE{Complex query?}
    PLANNER_GATE -->|~20% complex| PLANNER[Planner Node<br/>gpt-4o]
    PLANNER_GATE -->|~80% simple| INSIGHT
    PLANNER --> INSIGHT
    ANALYZER --> VIZ[Viz Node]
    ANALYZER --> RESPONDER
    
    INSIGHT --> GEN[Rule-based OR Code Gen gpt-4o<br/>Summarize gpt-4o-mini]
    GEN --> VIZ_OR_RESP{Viz in tools?}
    VIZ_OR_RESP -->|Yes| VIZ
    VIZ_OR_RESP -->|No| RESPONDER
    
    VIZ --> LOAD[Load Data from Redis<br/>Validate Config]
    LOAD --> CHART[Plotly Chart or Fallback]
    CHART --> RESPONDER
    
    RESPONDER --> FORMAT[Format Response<br/>Append Snapshot]
    FORMAT --> SUGGEST[Suggestion Node<br/>gpt-4o-mini · 3 Follow-up Chips]
    SUGGEST --> MEMORY[MemorySaver Checkpoint]
    MEMORY --> END2([Stream to User ~1-2s perceived])
    
    style START fill:#4CAF50
    style ROUTER fill:#9C27B0
    style CLARIFY fill:#E91E63
    style ANALYZER fill:#FF9800
    style PLANNER fill:#FF5722
    style INSIGHT fill:#2196F3
    style VIZ fill:#00BCD4
    style RESPONDER fill:#4CAF50
    style SUGGEST fill:#8BC34A
    style END2 fill:#4CAF50
```


### 5. Session Management & Version Control
- **Automatic TTL**: Sessions expire after 30 minutes of inactivity
- **TTL Extension**: Sessions auto-extend on access
- **Metadata Tracking**: File names, table counts, timestamps
- **Multi-table Support**: Handle multiple tables per session
- **Version History**: Git-like version control for data transformations
- **Branching**: Try multiple analysis paths without losing work
- **Graph Visualization**: Visual representation of transformation lineage

#### Data Git History - Version Graph

```mermaid
gitGraph
    commit id: "v0: Initial Upload" tag: "1300 rows"
    commit id: "v1: Filter Price > 5000" tag: "1150 rows"
    commit id: "v2: Fill Missing RAM" tag: "1150 rows"
    branch outlier-removal
    commit id: "v3a: Remove Outliers (IQR)" tag: "1050 rows"
    checkout main
    branch outlier-capping
    commit id: "v3b: Cap Outliers (95th %ile)" tag: "1150 rows"
    commit id: "v4: Sort by Company" tag: "1150 rows"
```

### 6. MCP Integration
- **18+ Data Tools**: Filter, sort, clean, transform operations
- **Safe Execution**: Tool-based approach prevents code injection
- **Tool Tracking**: See which tools are used for each operation
- **Error Handling**: Graceful error recovery

#### MCP Tool Execution Flow

```mermaid
flowchart TD
    START([User Query]) --> PARSE[LLM Parses Query]
    PARSE --> SELECT{Select Tools}
    
    SELECT -->|Core| INIT[initialize_data_table]
    SELECT -->|Cleaning| CLEAN[drop_rows, fill_missing, etc.]
    SELECT -->|Selection| SEL[select_columns, filter_rows]
    SELECT -->|Transform| TRANS[rename_columns, sort_data]
    
    INIT --> LOAD[Load from Redis]
    CLEAN --> LOAD
    SEL --> LOAD
    TRANS --> LOAD
    
    LOAD --> EXECUTE[Execute Operation]
    EXECUTE --> VALIDATE{Validation}
    
    VALIDATE -->|Success| SAVE[Save to Redis]
    VALIDATE -->|Error| ERROR[Error Handler]
    
    SAVE --> VERSION[Create Version Snapshot]
    VERSION --> GRAPH[Update Version Graph]
    GRAPH --> RESPONSE[Return Success]
    
    ERROR --> ROLLBACK[Rollback Changes]
    ROLLBACK --> RESPONSE
    
    RESPONSE --> END([Response to User])
    
    style START fill:#4CAF50
    style END fill:#4CAF50
    style VALIDATE fill:#FFC107
    style ERROR fill:#F44336
    style VERSION fill:#2196F3
```

#### Available MCP Tools Categories

```mermaid
mindmap
  root((MCP Tools))
    Core Operations
      initialize_data_table
      get_table_summary
      list_tables
      undo_operation
      redo_operation
    Data Cleaning
      drop_rows_from_table
      fill_missing_values
      drop_missing_values
      replace_table_values
      clean_string_columns
      remove_outliers_from_table
    Selection
      select_table_columns
      filter_table_rows
      sample_table_rows
    Transformation
      rename_table_columns
      reorder_table_columns
      sort_table_data
      apply_custom_function
    Aggregation
      group_and_aggregate
      pivot_table
      crosstab_analysis
    Feature Engineering
      create_derived_column
      bin_numeric_column
      encode_categorical
```

## 🌐 Deployment Architecture

```mermaid
flowchart LR
    subgraph "User Device"
        BROWSER[Web Browser<br/>Any Device]
    end
    
    subgraph "Streamlit Cloud"
        UI[Streamlit UI<br/>data-assistant-*.streamlit.app<br/>✅ Deployed]
    end
    
    subgraph "Render Cloud Platform"
        MCP_PROD[MCP Server<br/>data-analyst-mcp-server.onrender.com<br/>✅ Python Environment]
        API_PROD[FastAPI Backend<br/>data-assistant-m4kl.onrender.com<br/>✅ Python Environment]
    end
    
    subgraph "Cloud Services"
        REDIS[(Upstash Redis<br/>Serverless Storage)]
        OPENAI[OpenAI API<br/>GPT-4/5]
    end
    
    BROWSER -->|HTTPS| UI
    UI -->|HTTP Requests| API_PROD
    UI -->|MCP Protocol| MCP_PROD
    
    API_PROD <-->|REST API| REDIS
    MCP_PROD <-->|REST API| REDIS
    MCP_PROD <-->|LLM Calls| OPENAI
    
    style UI fill:#FF9800
    style MCP_PROD fill:#4CAF50
    style API_PROD fill:#2196F3
    style REDIS fill:#FF5722
    style OPENAI fill:#9C27B0
```

## 🚀 Installation

### Option 1: Use Live Deployment (Recommended) ⚡

**No installation needed!** Access the fully deployed platform:

🌐 **https://data-assistant-mu6xtnwivdpi8umtp94wuh.streamlit.app/**

**Features:**
- ✅ Instant access from any device
- ✅ All backend services running
- ✅ No setup or configuration required
- ✅ Always up-to-date with latest features

**Just bring your data and start analyzing!**

---

### Option 2: Local Development Setup

For customization or local development:

#### Prerequisites

- Python 3.8+
- OpenAI API key (for data manipulation)
- Git

### Step 1: Clone Repository

```bash
git clone <repository-url>
cd Data-Assistant
```

### Step 2: Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 4: Set Up Secrets Configuration

**Option A: Using Streamlit Secrets (Recommended)**

Create `.streamlit/secrets.toml` in the project root:

```bash
# Create the .streamlit directory if it doesn't exist
mkdir -p .streamlit

# Copy the template and edit with your values
cp .streamlit/secrets.toml.template .streamlit/secrets.toml
```

Edit `.streamlit/secrets.toml`:

```toml
# OpenAI Configuration
[openai]
api_key = "sk-your-openai-api-key-here"
model = "gpt-4o"

# Production Deployment URLs (Render)
[api]
fastapi_url = "https://data-assistant-m4kl.onrender.com"
mcp_server_url = "https://data-analyst-mcp-server.onrender.com/data/mcp"

# For Local Development: Uncomment and use these
# [api.local]
# fastapi_url = "http://127.0.0.1:8001"
# mcp_server_url = "http://127.0.0.1:8000/data/mcp"

# Optional: Redis Configuration (if running backend locally)
[redis]
rest_url = "https://your-redis-url.upstash.io"
rest_token = "your-redis-token-here"
session_ttl_minutes = 30
```

**Option B: Using Environment Variables (Legacy)**

Alternatively, create a `.env` file in the project root:

```bash
# Upstash Redis Configuration
UPSTASH_REDIS_REST_URL=https://your-redis-url.upstash.io
UPSTASH_REDIS_REST_TOKEN=your-redis-token
SESSION_TTL_MINUTES=30

# OpenAI Configuration
OPENAI_API_KEY=your-openai-api-key
OPENAI_MODEL=gpt-4o

# Langfuse Observability (Optional)
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_BASE_URL=https://cloud.langfuse.com

# Production Deployment URLs
MCP_SERVER_URL=https://data-analyst-mcp-server.onrender.com/data/mcp
FASTAPI_URL=https://data-assistant-m4kl.onrender.com
```

**Note**: The app will try `secrets.toml` first, then fall back to environment variables.

### Step 5: Start Services

#### Option A: Use Production Deployment (Recommended)

**🌐 Production Services (Already Deployed)**:
- **MCP Server**: https://data-analyst-mcp-server.onrender.com
- **FastAPI Backend**: https://data-assistant-m4kl.onrender.com
- **Status**: Both services are live on Render!

**Only Start Streamlit Locally:**
```bash
streamlit run app.py
# UI runs on http://localhost:8501
# Connects to production MCP & FastAPI automatically
```

#### Option B: Full Local Development

**Terminal 1 - MCP Server:**
```bash
cd data-mcp
python server.py
# Server runs on http://127.0.0.1:8000
```

**Terminal 2 - FastAPI Backend:**
```bash
python main.py
# API runs on http://127.0.0.1:8001
```

**Terminal 3 - Streamlit Frontend:**
```bash
streamlit run app.py
# UI runs on http://localhost:8501
```

**Note**: For local development, update `.env` to use local URLs.

## ⚙️ Configuration

### Configuration Methods

The platform supports two configuration methods:

1. **Streamlit Secrets** (`.streamlit/secrets.toml`) - **Recommended** ✅
2. **Environment Variables** (`.env` file) - Legacy fallback

The app checks for secrets in this order:
1. Streamlit secrets (`.streamlit/secrets.toml`)
2. Environment variables (`.env` or system environment)
3. Hardcoded defaults

### Streamlit Secrets Configuration

Based on [Streamlit's official secrets management](https://docs.streamlit.io/develop/api-reference/connections/secrets.toml).

**File**: `.streamlit/secrets.toml`

| Section | Key | Description | Default | Required |
|---------|-----|-------------|---------|----------|
| `[openai]` | `api_key` | OpenAI API key for LLM | - | Yes |
| `[openai]` | `model` | OpenAI model to use | gpt-4o | No |
| `[api]` | `fastapi_url` | FastAPI backend URL | https://data-assistant-m4kl.onrender.com | No |
| `[api]` | `mcp_server_url` | MCP server endpoint | https://data-analyst-mcp-server.onrender.com/data/mcp | No |
| `[redis]` | `rest_url` | Upstash Redis REST API URL | - | Yes* |
| `[redis]` | `rest_token` | Upstash Redis REST API Token | - | Yes* |
| `[redis]` | `session_ttl_minutes` | Session expiration time (minutes) | 30 | No |

*Required only if running backend services locally

### Environment Variables (Legacy)

| Variable | Description | Production Default | Local Default | Required |
|----------|-------------|-------------------|---------------|----------|
| `UPSTASH_REDIS_REST_URL` | Upstash Redis REST API URL | - | None | Yes* |
| `UPSTASH_REDIS_REST_TOKEN` | Upstash Redis REST API Token | - | None | Yes* |
| `SESSION_TTL_MINUTES` | Session expiration time (minutes) | 30 | 30 | No |
| `OPENAI_API_KEY` | OpenAI API key for LLM | - | None | Yes |
| `OPENAI_MODEL` | OpenAI model to use | gpt-4o | gpt-4o | No |
| `LANGFUSE_PUBLIC_KEY` | Langfuse public key | - | None | No |
| `LANGFUSE_SECRET_KEY` | Langfuse secret key | - | None | No |
| `LANGFUSE_BASE_URL` | Langfuse base URL | https://cloud.langfuse.com | https://cloud.langfuse.com | No |
| `MCP_SERVER_URL` | MCP server endpoint | https://data-analyst-mcp-server.onrender.com/data/mcp | http://127.0.0.1:8000/data/mcp | No |
| `FASTAPI_URL` | FastAPI backend URL | https://data-assistant-m4kl.onrender.com | http://127.0.0.1:8001 | No |
| `PORT` | FastAPI server port | 8001 | 8001 | No |

*Required only if running backend services locally

### File Size Limits

Configured in `ingestion/config.py`:
- **Max File Size**: 100 MB (default)
- **Max Tables per File**: 10 (default)

## 📖 Usage

### Web Interface

1. **Upload File**:
   - Navigate to Upload tab
   - Select file (CSV, Excel, or Image)
   - Click "Upload & Process"
   - View extracted tables and metadata

2. **Manipulate Data**:
   - Switch to Data Manipulation tab
   - Enter natural language query (e.g., "Remove rows with missing email")
   - Click "Execute Query"
   - View results and operation history

3. **Visualize Data**:
   - Switch to Visualization Centre tab
   - Select chart type (Bar, Line, Scatter, etc.)
   - Choose X and Y axis columns
   - Optionally select color/grouping column
   - Chart renders instantly
   - Export as PNG, SVG, or HTML

4. **Chat with Your Data**:
   - Switch to Chatbot tab (InsightBot)
   - Ask questions (e.g., "What's the average salary by department?", "Show correlation", "Compare sales by region")
   - Get context-aware answers; follow-ups like "What about the maximum?" are resolved automatically
   - If a term matches multiple columns, choose from "Did you mean X or Y?"; use suggestion chips for one-click follow-ups
   - Charts and tables are embedded per message; previous visualizations stay visible when you send new queries
   - Clear chat from the sidebar when needed


## 📁 Project Structure

```
Data-Assistant/
├── app.py                      # Streamlit frontend application
├── main.py                     # FastAPI backend server
├── mcp_client.py              # MCP client with LangChain integration
├── test_visualization_evaluation.py  # Visualization test suite
├── requirements.txt           # Python dependencies
├── README.md                  # This file
│
├── chatbot/                   # InsightBot — LangGraph-powered chatbot
│   ├── __init__.py
│   ├── state.py              # LangGraph state schema (TypedDict), Node type
│   ├── graph.py              # StateGraph, planner-skip complexity gate
│   ├── llm_registry.py       # Singleton LLM cache — one ChatOpenAI per config tuple
│   ├── streamlit_ui.py       # Streamlit UI entry (history, snapshots, chips)
│   ├── README.md             # Chatbot architecture, model assignments, latency targets
│   ├── DEVELOPER.md          # How to extend: add node, add chart, avoid redundancy
│   ├── nodes/                # LangGraph nodes
│   │   ├── router.py         # Intent (gpt-4o-mini), context resolution, clarification
│   │   ├── clarification.py  # "Did you mean X or Y?" column disambiguation
│   │   ├── analyzer.py       # Tool selection (gpt-4o), correlation→heatmap
│   │   ├── planner.py        # Multi-step breakdown (gpt-4o, ~20% complex queries only)
│   │   ├── insight.py        # Rule-based → code gen (gpt-4o) → summarize (gpt-4o-mini)
│   │   ├── viz.py            # Chart config validation, state only (Plotly in UI)
│   │   ├── responder.py      # Response formatting, response_snapshots
│   │   └── suggestion_engine.py  # gpt-4o-mini + intent-aware fallbacks
│   ├── tools/                # LangChain @tool definitions (configs only)
│   │   ├── data_tools.py     # insight_tool
│   │   ├── simple_charts.py  # Bar, line, scatter, histogram, heatmap, correlation_matrix
│   │   └── complex_charts.py # Combo and dashboard tools
│   ├── execution/            # Code generation and safe execution
│   │   ├── code_generator.py # LLM pandas code (gpt-4o via registry)
│   │   ├── code_validator.py # Forbidden ops, result variable
│   │   ├── safe_executor.py  # Sandboxed execution, timeout, row limit
│   │   └── rule_based_executor.py  # Zero-LLM fast path (mean, sum, count, min, max)
│   ├── utils/
│   │   ├── session_loader.py # Load DataFrames and metadata from Redis
│   │   ├── state_helpers.py  # get_current_query(state) — shared query resolution
│   │   ├── profile_formatter.py  # Data profile for prompts and chart validation
│   │   └── chart_selector.py # Rule-based chart suggestion (not in main graph)
│   ├── prompts/              # Modular prompts (one per file)
│   │   ├── base.py           # PromptTemplate, truncate_schema
│   │   ├── router_prompt.py
│   │   ├── analyzer_prompt.py
│   │   ├── planner_prompt.py
│   │   ├── code_generator_prompt.py
│   │   ├── summarizer_prompt.py
│   │   ├── responder_prompt.py
│   │   └── ...               # suggestion, small_talk, context_resolver
│   └── ui/                   # Streamlit UI components
│       ├── message_history.py
│       ├── chat_input.py     # graph.stream() with progressive status labels
│       └── chart_ui.py       # generate_chart_from_config_ui (Plotly from viz_config)
│
├── redis_db/                  # Redis session management
│   ├── __init__.py
│   ├── constants.py          # Redis configuration constants
│   ├── redis_store.py        # Core Redis operations
│   └── serializer.py         # DataFrame serialization
│
├── ingestion/                 # File processing module
│   ├── __init__.py
│   ├── ingestion_handler.py  # Main ingestion orchestrator
│   ├── config.py             # Ingestion configuration
│   ├── csv_handler.py        # CSV file processor
│   ├── excel_handler.py      # Excel file processor
│   └── image_handler.py      # Image file processor (OCR)
│
├── data_visualization/        # Visualization module (multi-layer caching, lazy exports)
│   ├── __init__.py
│   ├── visualization.py       # Visualization Centre tab, figure memoization
│   ├── cache_invalidation.py  # on_data_changed() — cross-tab cache coordination
│   ├── dashboard_builder.py   # Dashboard state and multi-chart rendering
│   ├── utils.py               # Shared helpers
│   ├── core/
│   │   ├── data_fetcher.py    # Three-layer cached data fetching from FastAPI
│   │   ├── chart_generator.py # Plotly figure construction
│   │   └── validators.py      # Column and config validation
│   ├── charts/
│   │   ├── basic.py           # Bar, line, scatter, area, box, histogram, pie
│   │   ├── heatmap.py         # Heatmap and correlation matrix
│   │   └── combo.py           # Dual-axis combo charts
│   ├── ui/
│   │   ├── controls.py        # Chart control widgets
│   │   ├── export.py          # Lazy two-stage export (Generate → cache → Download)
│   │   ├── dashboard.py       # Dashboard UI rendering
│   │   └── recommendations.py # AI recommendation display
│   └── intelligence/
│       └── recommender.py     # LLM + rule-based chart recommendations
│
├── data-mcp/                  # MCP server for data operations
│   ├── server.py             # FastMCP server
│   ├── data_functions/       # Data manipulation tools
│   │   ├── core.py           # Core data operations
│   │   ├── cleaning.py       # Data cleaning tools
│   │   ├── transformation.py # Data transformation tools
│   │   ├── selection.py      # Column/row selection
│   │   ├── aggregation.py    # Aggregation operations
│   │   ├── feature_engineering.py
│   │   ├── multi_table.py    # Multi-table operations
│   │   ├── http_client.py    # HTTP client for Redis
│   │   └── config.py         # MCP configuration
│   └── requirements.txt
│
└── test_files/                # Sample test files
    ├── test.csv
    ├── test.xlsx
    └── test_image.png
```

## 🔧 Components

### 1. Redis Database Module (`redis_db/`)

**Purpose**: Manages session storage and data persistence using Upstash Redis.

**Key Functions**:
- `save_session()`: Store DataFrames and metadata with TTL
- `load_session()`: Retrieve DataFrames from Redis
- `delete_session()`: Remove session data
- `get_metadata()`: Get session metadata
- `extend_ttl()`: Extend session expiration time
- `list_sessions()`: List all active sessions

**Storage Format**:
- Tables: Base64-encoded pickled DataFrames
- Metadata: JSON format
- Keys: `session:{session_id}:tables` and `session:{session_id}:meta`

### 2. Ingestion Module (`ingestion/`)

**Purpose**: Processes various file formats and extracts tabular data.

**Supported Formats**:
- **CSV**: Automatic delimiter detection, encoding detection
- **Excel**: Multi-sheet support, preserves sheet names
- **Images**: Uses Gemini Vision API for OCR-based table extraction

**Key Functions**:
- `process_file()`: Main entry point for file processing
- `process_csv()`: CSV-specific handler
- `process_excel()`: Excel-specific handler
- `process_image()`: Image-specific handler

### 3. MCP Client (`mcp_client.py`)

**Purpose**: Connects to MCP server and provides LangChain agent for natural language queries.

**Key Functions**:
- `create_mcp_agent()`: Initialize LangChain agent with MCP tools
- `analyze_data()`: Execute natural language query on data
- `get_available_sessions()`: Fetch all active sessions
- `get_session_metadata()`: Get session metadata

**Features**:
- Tool usage tracking and display
- Async/await support
- Error handling and cleanup

### 4. FastAPI Backend (`main.py`)

**Purpose**: REST API for file upload, session management, and data operations.

**Endpoints**:
- File upload and processing
- Session CRUD operations
- Table retrieval and updates
- Health checks and configuration

**Features**:
- CORS support
- Automatic TTL management
- Error handling and logging
- Base64 serialization for MCP integration

### 5. Visualization Module (`data_visualization/`)

**Purpose**: Cached chart generation using Plotly with multi-layer session data caching, figure memoization, and lazy export generation.

**Key Components**:
- `visualization.py`: Visualization Centre tab, figure memoization by config hash
- `cache_invalidation.py`: `on_data_changed()` — busts all visualization caches when data changes
- `core/data_fetcher.py`: Three-layer cache (session_state → `@st.cache_data` TTL → FastAPI)
- `ui/export.py`: Lazy two-stage exports — Kaleido only on explicit click, bytes cached
- `dashboard_builder.py`: Multi-chart layouts and dashboard creation
- `intelligence/recommender.py`: LLM + rule-based chart type recommendations

**Key Functions**:
- `render_visualization_tab()`: Main function to render the visualization tab
- `get_dataframe_from_session(session_id, table_name)`: Cached DataFrame fetch
- `get_tables_from_session(session_id)`: Cached tables list fetch
- `on_data_changed()`: Full cache invalidation after data manipulation

**Performance**:
- Tables/DataFrame fetch: ~500ms–2s per rerender → ~0ms (session_state hot cache)
- Chart generation (same config): ~200ms per rerender → ~0ms (figure cache hit)
- PNG/SVG export (was blocking every render ~5s): now lazy, ~1–2s one time only

**Features**:
- 8 chart types: Bar, Line, Scatter, Area, Box, Histogram, Pie, Heatmap
- Smart column selection with automatic defaults
- Aggregation support (sum, mean, count, min, max)
- Interactive Plotly charts with zoom/pan/hover
- Lazy export: PNG, SVG, PDF (Kaleido on-demand), HTML, Python, Notebook, PPTX
- Theme-aware (light/dark mode support)
- Multi-table support with table selection
- Dashboard builder with grid layouts and chart pinning

### 6. InsightBot Module (`chatbot/`)

**Purpose**: LangGraph-powered conversational AI for data analysis with context resolution, clarification, tool selection, safe code execution, and per-turn visualizations. Optimized for low latency via LLM singleton registry, model downgrade on classification tasks, planner skip, and streaming UI.

**Architecture**: `router → (clarification | analyzer → [planner?] → insight → viz | responder) → suggestion → END`. MemorySaver for persistence; response_snapshots so each AI message keeps its chart/table/code. Invoked via `graph.stream()` for progressive rendering.

**LLM Registry** (`llm_registry.py`): Singleton cache keyed by `(model_key, temperature, max_tokens)`. Getters: `get_router_llm()`, `get_analyzer_llm()`, `get_planner_llm()`, `get_code_gen_llm()`, `get_summarizer_llm()`, `get_suggestion_llm()`, `get_resolver_llm()`, `get_small_talk_llm()`. Saves ~1.4s/query.

**Nodes**:
- `nodes/router.py`: Intent (gpt-4o-mini, max_tokens=256), context resolution (gpt-4o-mini, max_tokens=128), clarification detection
- `nodes/analyzer.py`: Tool selection (gpt-4o); correlation→heatmap coercion
- `nodes/planner.py`: Multi-step breakdown (gpt-4o) — ~20% of complex queries only
- `nodes/insight.py`: Rule-based fast path → code gen (gpt-4o) → summarize (gpt-4o-mini, max_tokens=256)
- `nodes/suggestion_engine.py`: 3 follow-up questions (gpt-4o-mini, max_tokens=128) + intent-aware fallbacks

**Execution**: Rule-based executor called first (zero LLM, ~2.5s saved on ~30% of queries); gpt-4o code generator for remaining queries; sandboxed execution with timeout.

**Key Features**:
- Streaming UI: `graph.stream()` → ~1–2s perceived latency
- Singleton registry + model downgrade: ~7s wall-clock saved per query
- Planner skip (~80% of queries): ~2s saved
- Rule-based fast path (~30% of queries): ~2.5s saved
- Context-aware memory, column clarification, per-turn snapshots, reliable suggestion chips

See `chatbot/README.md` for full schema, flow, model assignment table, and latency breakdown.
### 7. Streamlit Frontend (`app.py`)

**Purpose**: Web-based user interface for file upload, data manipulation, visualization, and chatbot.

**Tabs**:
1. **Upload Tab**: File upload, processing, and preview
2. **Data Manipulation Tab**: Natural language queries, operation history, data preview
3. **Visualization Centre Tab**: Interactive chart generation with Plotly, export options
4. **Chatbot Tab**: Conversational interface for data queries with automatic visualizations

**Features**:
- Real-time data preview
- Operation history tracking
- Session management UI
- Error display and recovery
- Interactive visualizations with Plotly
- Chart export functionality
- Conversational chatbot interface
- Automatic visualization detection in chat


## 🛠 Development

### Running in Development Mode

```bash
# FastAPI with auto-reload
uvicorn main:app --reload --port 8001

# Streamlit with auto-reload (default)
streamlit run app.py
```

### Testing

```bash
# Test file upload
curl -X POST http://localhost:8001/api/ingestion/file-upload \
  -F "file=@test_files/test.csv"

# Test session retrieval
curl http://localhost:8001/api/session/{session_id}/tables

# Test MCP client
python mcp_client.py {session_id} "show me the first 5 rows"
```

### Adding New File Handlers

1. Create handler in `ingestion/` (e.g., `json_handler.py`)
2. Add to `_HANDLERS` dict in `ingestion_handler.py`
3. Update `IngestionConfig.FILE_TYPES` in `config.py`
4. Add file type to Streamlit uploader in `app.py`

### Adding New MCP Tools

1. Add tool function in `data-mcp/data_functions/`
2. Register in `data-mcp/server.py`
3. Tool automatically available to LangChain agent

**Built with ❤️ for data analysts**
