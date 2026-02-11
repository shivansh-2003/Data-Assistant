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
  - OpenAI GPT-4o/GPT-5 (Intent classification, code generation, summarization)
  - LangChain Experimental (pandas dataframe agent)
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
        LLM[OpenAI GPT-4/5<br/>LangChain]
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
- **Zero-Latency Charts**: Instant chart generation using Plotly
- **8 Chart Types**: Bar, Line, Scatter, Area, Box, Histogram, Pie, Heatmap
- **Interactive Visualizations**: Zoom, pan, hover tooltips
- **Column Mapping**: Easy X/Y axis and color grouping selection
- **Aggregations**: Sum, mean, count, min, max for grouped data
- **One-Click Exports**: PNG, SVG, and interactive HTML formats
- **Theme-Aware**: Automatically adapts to light/dark mode

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

### 4. InsightBot - Intelligent Chatbot Tab
- **🤖 LangGraph-Powered Architecture**: State-of-the-art conversational AI with persistent memory
- **💬 Multi-Turn Conversations**: Maintains context across the entire conversation with memory checkpointing
- **🧠 Context-Aware Responses**: Uses schema, statistics, and operation history for accurate answers
- **📊 Automatic Visualization Detection**: Intelligently detects when charts are needed and generates appropriate visualizations
- **🔧 Function Calling**: Dynamic tool selection based on query intent (statistical, comparative, visualization)
- **🎯 Intent Classification**: Routes queries to appropriate processing nodes (analyzer, insight, visualization, responder)
- **⚡ Safe Code Execution**: Generates and executes pandas code in sandboxed environment with timeout protection
- **📈 Real-time Chart Generation**: Embeds interactive Plotly charts directly in chat responses
- **🔄 Session Integration**: Seamlessly loads DataFrames from Redis for instant analysis
- **📝 Query Types Supported**:
  - Statistical queries (averages, counts, sums, aggregations)
  - Comparative queries (compare X by Y, rankings, differences)
  - Filtering & sorting (list items matching criteria, top N)
  - Visualization requests (explicit and implicit chart generation)
  - Exploratory queries (patterns, correlations, distributions)
  - Debugging queries (operation history, schema inspection)

#### InsightBot LangGraph Architecture

```mermaid
flowchart TD
    START([User Query]) --> ENTRY[Entry Point]
    ENTRY --> ROUTER[Router Node<br/>Intent Classification]
    
    ROUTER --> CLASSIFY{Classify Intent}
    CLASSIFY -->|data_query| ANALYZER[Analyzer Node<br/>Tool Selection]
    CLASSIFY -->|visualization_request| ANALYZER
    CLASSIFY -->|small_talk| RESPONDER[Responder Node]
    
    ANALYZER --> SELECT{Select Tools}
    SELECT -->|insight_tool| INSIGHT[Insight Node]
    SELECT -->|chart_tool| VIZ[Visualization Node]
    SELECT -->|both| BOTH[Both Nodes]
    
    INSIGHT --> GENERATE[Generate Pandas Code<br/>LLM Code Generator]
    GENERATE --> EXECUTE[Safe Code Execution<br/>ThreadPoolExecutor]
    EXECUTE --> SUCCESS{Success?}
    
    SUCCESS -->|Yes| SUMMARIZE[Summarize Results<br/>LLM Summarizer]
    SUCCESS -->|No| ERROR[Error Handler]
    
    SUMMARIZE --> CHECK_VIZ{Visualization Needed?}
    CHECK_VIZ -->|Yes| VIZ
    CHECK_VIZ -->|No| RESPONDER
    
    VIZ --> LOAD[Load DataFrames<br/>from Redis]
    LOAD --> CONFIG[Validate Chart Config<br/>Check Parameters]
    CONFIG --> VALID{Valid?}
    
    VALID -->|Yes| CHART[Generate Plotly Chart]
    VALID -->|No| SKIP[Skip Visualization]
    
    CHART --> RESPONDER
    SKIP --> RESPONDER
    ERROR --> RESPONDER
    
    RESPONDER --> FORMAT[Format Final Response<br/>Combine Insights + Charts]
    FORMAT --> MEMORY[Save to Memory<br/>LangGraph Checkpointer]
    MEMORY --> END([Display to User])
    
    style START fill:#4CAF50
    style ROUTER fill:#9C27B0
    style ANALYZER fill:#FF9800
    style INSIGHT fill:#2196F3
    style VIZ fill:#00BCD4
    style RESPONDER fill:#4CAF50
    style END fill:#4CAF50
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
   - Switch to Chatbot tab
   - Ask questions about your data (e.g., "What's the average salary by department?")
   - Get context-aware answers with automatic visualizations when needed
   - View conversation history and clear chat when needed
   - Charts are automatically embedded in responses when relevant


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
├── chatbot/                   # InsightBot - LangGraph-powered chatbot
│   ├── __init__.py
│   ├── state.py              # LangGraph state schema (TypedDict)
│   ├── graph.py              # StateGraph definition and compilation
│   ├── streamlit_ui.py       # Streamlit UI components
│   ├── nodes/                # LangGraph nodes
│   │   ├── router.py         # Intent classification node
│   │   ├── analyzer.py       # Tool selection node (function calling)
│   │   ├── insight.py        # Pandas code generation and execution
│   │   ├── viz.py            # Visualization configuration and validation
│   │   └── responder.py      # Response formatting and memory
│   ├── tools/                # LangChain tools
│   │   ├── simple_charts.py  # Bar, line, scatter, histogram tools
│   │   └── complex_charts.py # Combo charts and dashboard tools
│   ├── execution/            # Safe code execution
│   │   ├── code_generator.py # LLM-based pandas code generation
│   │   └── safe_executor.py  # Sandboxed execution with timeout
│   ├── utils/                # Utility modules
│   │   └── session_loader.py # Load DataFrames from Redis
│   ├── prompts/              # LLM prompts
│   │   └── system_prompts.py # Centralized prompts for all nodes
│   └── INSIGHTBOT_IMPLEMENTATION.md  # Architecture documentation
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
├── data_visualization/        # Visualization module
│   ├── __init__.py
│   ├── visualization.py      # Main visualization tab
│   ├── chart_compositions.py  # Advanced chart types
│   ├── dashboard_builder.py   # Multi-chart layouts
│   ├── smart_recommendations.py  # LLM-based chart recommendations
│   └── utils.py              # Utility functions
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

**Purpose**: Provides zero-latency chart generation using Plotly with session data integration.

**Key Components**:
- `visualization.py`: Main visualization tab rendering
- `dashboard_builder.py`: Multi-chart layouts and dashboard creation
- `chart_compositions.py`: Advanced chart types (combo charts)
- `smart_recommendations.py`: LLM-based chart type recommendations

**Key Functions**:
- `render_visualization_tab()`: Main function to render the visualization tab
- `get_dataframe_from_session()`: Fetches session data and converts to DataFrame
- `generate_chart()`: Generate Plotly figure based on user selections

**Features**:
- 8 chart types: Bar, Line, Scatter, Area, Box, Histogram, Pie, Heatmap
- Smart column selection with automatic defaults
- Aggregation support (sum, mean, count, min, max)
- Interactive Plotly charts with zoom/pan/hover
- Export to PNG, SVG, and HTML formats
- Theme-aware (light/dark mode support)
- Multi-table support with table selection
- Dashboard builder with grid layouts and chart pinning

### 6. InsightBot Module (`chatbot/`)

**Purpose**: Advanced LangGraph-powered conversational AI for data analysis with intelligent tool selection and visualization.

**Architecture**: Multi-node state graph with persistent memory and dynamic tool routing.

**Key Components**:

**Nodes**:
- `nodes/router.py`: Intent classification using structured LLM output
- `nodes/analyzer.py`: Tool selection via function calling (insight_tool, chart_tools)
- `nodes/insight.py`: Pandas code generation and safe execution
- `nodes/viz.py`: Visualization configuration and validation
- `nodes/responder.py`: Response formatting and memory persistence

**Tools**:
- `tools/simple_charts.py`: Bar, line, scatter, histogram chart tools
- `tools/complex_charts.py`: Combo charts and dashboard tools
- `tools/insight_tool.py`: Statistical analysis and data querying

**Execution**:
- `execution/code_generator.py`: LLM-based pandas code generation
- `execution/safe_executor.py`: Sandboxed code execution with timeout

**Utilities**:
- `utils/session_loader.py`: Loads DataFrames and metadata from Redis
- `prompts/system_prompts.py`: Centralized LLM prompts for all nodes
- `state.py`: TypedDict schema for LangGraph state management
- `graph.py`: StateGraph definition and compilation with MemorySaver

**Key Features**:
- ✅ **Stateful Conversations**: LangGraph MemorySaver for persistent multi-turn memory
- ✅ **Intent Classification**: Automatic routing between data queries, visualizations, and small talk
- ✅ **Function Calling**: LLM dynamically selects appropriate tools based on query
- ✅ **Safe Code Execution**: ThreadPoolExecutor-based timeout (10s) for pandas code
- ✅ **Parameter Extraction**: Intelligent extraction of x_col, y_col, agg_func from queries
- ✅ **Column Validation**: Verifies columns exist before chart generation
- ✅ **Error Handling**: Graceful fallback when visualizations or insights fail
- ✅ **Session Integration**: Seamless loading of DataFrames from Redis store
- ✅ **Serialization**: Handles non-serializable objects (DataFrames, Plotly figures)

**Supported Query Patterns**:
- 📊 Statistical: "What's the average Price by Company?"
- 📈 Comparative: "Compare average Weight by Cpu_brand"
- 🔍 Filtering: "List all laptops with Price > 11.0 and Ram=16"
- 📉 Distribution: "Show the distribution of Weight"
- 🎯 Visualization: "Plot average Price by Company (bar chart)"
- 🔗 Relationship: "Visualize Ram vs. Price relationship"
- 📦 Breakdown: "Show breakdown of Os types as percentages"

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
