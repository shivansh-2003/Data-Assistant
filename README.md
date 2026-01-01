# Data Assistant Platform

A powerful, multi-modal data analysis platform that lets you upload messy real-world files, clean and transform data with natural language queries, and analyze data — all through an intuitive web interface powered by AI.

## 📋 Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Features](#features)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [API Documentation](#api-documentation)
- [Project Structure](#project-structure)
- [Components](#components)
- [Development](#development)
- [Troubleshooting](#troubleshooting)

## 🎯 Overview

The Data Assistant Platform is a comprehensive data analysis solution that combines:

- **Smart File Ingestion**: Automatically extracts tables from CSV, Excel, PDFs, and images
- **Natural Language Data Manipulation**: Transform data using plain English queries powered by LLM
- **Session Management**: Persistent data storage with automatic TTL expiration
- **MCP Integration**: Model Context Protocol server for safe, tool-based data operations
- **Modern UI**: Streamlit-based interface with real-time feedback

### Key Technologies

- **Backend**: FastAPI (REST API)
- **Frontend**: Streamlit (Web UI)
- **Data Storage**: Upstash Redis (Cloud Redis)
- **AI/ML**: LangChain, OpenAI GPT models
- **Data Processing**: Pandas, Docling
- **Visualization**: Plotly, Kaleido (for static exports)
- **MCP Server**: FastMCP for tool-based operations

## 🏗 Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Streamlit Frontend (app.py)              │
│  ┌──────────────┐  ┌──────────────────┐  ┌──────────────┐ │
│  │ Upload Tab   │  │ Data Manipulation│  │ Visualization│ │
│  │ - File UI    │  │ - NL Query Input │  │ - Chart Types │ │
│  │ - Preview    │  │ - Operation Hist │  │ - Interactive │ │
│  └──────────────┘  │ - Data Preview   │  │ - Export      │ │
│                    └──────────────────┘  └──────────────┘ │
└───────────────────────────┬───────────────────────────────┘
                            │ HTTP Requests
┌───────────────────────────▼───────────────────────────────┐
│              FastAPI Backend (main.py)                    │
│  ┌──────────────────┐  ┌──────────────────────────────┐ │
│  │ Ingestion API    │  │ Session Management API        │ │
│  │ - File Upload    │  │ - Get/Update Sessions         │ │
│  │ - Processing     │  │ - Metadata                    │ │
│  └──────────────────┘  └──────────────────────────────┘ │
└───────────┬──────────────────────┬───────────────────────┘
            │                       │
    ┌───────▼────────┐      ┌───────▼────────┐
    │ Ingestion      │      │ Redis Store   │
    │ Module        │      │ (redis_db)    │
    │ - CSV/Excel   │      │ - Sessions    │
    │ - PDF/Images  │      │ - TTL Mgmt    │
    └───────┬────────┘      └───────────────┘
            │                       │
            └───────────┬───────────┘
                        │
            ┌───────────▼───────────┐
            │   MCP Server          │
            │   (data-mcp/)         │
            │   - Pandas Tools      │
            │   - Data Operations   │
            └───────────┬───────────┘
                        │
            ┌───────────▼───────────┐
            │   MCP Client          │
            │   (mcp_client.py)     │
            │   - LangChain Agent   │
            │   - OpenAI LLM        │
            └───────────────────────┘
```

## ✨ Features

### 1. Multi-Format File Upload
- **CSV/TSV**: Automatic delimiter detection
- **Excel**: Multi-sheet support (.xlsx, .xls, .xlsm)
- **PDF**: Table extraction with layout preservation (Docling)
- **Images**: OCR-based table extraction (PNG, JPEG, TIFF, BMP)

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

### 4. Session Management
- **Automatic TTL**: Sessions expire after 30 minutes of inactivity
- **TTL Extension**: Sessions auto-extend on access
- **Metadata Tracking**: File names, table counts, timestamps
- **Multi-table Support**: Handle multiple tables per session

### 5. MCP Integration
- **18+ Data Tools**: Filter, sort, clean, transform operations
- **Safe Execution**: Tool-based approach prevents code injection
- **Tool Tracking**: See which tools are used for each operation
- **Error Handling**: Graceful error recovery

## 🚀 Installation

### Prerequisites

- Python 3.8+
- Upstash Redis account (free tier available)
- OpenAI API key (for data manipulation)

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

### Step 4: Set Up Environment Variables

Create a `.env` file in the project root:

```bash
# Upstash Redis Configuration
UPSTASH_REDIS_REST_URL=https://your-redis-url.upstash.io
UPSTASH_REDIS_REST_TOKEN=your-redis-token
SESSION_TTL_MINUTES=30

# OpenAI Configuration
OPENAI_API_KEY=your-openai-api-key
OPENAI_MODEL=gpt-4o  # or gpt-5.1 if available

# MCP Server Configuration (optional)
MCP_SERVER_URL=http://127.0.0.1:8000/mcp
INGESTION_API_URL=http://127.0.0.1:8001
```

### Step 5: Start Services

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

## ⚙️ Configuration

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `UPSTASH_REDIS_REST_URL` | Upstash Redis REST API URL | None | Yes |
| `UPSTASH_REDIS_REST_TOKEN` | Upstash Redis REST API Token | None | Yes |
| `SESSION_TTL_MINUTES` | Session expiration time (minutes) | 30 | No |
| `OPENAI_API_KEY` | OpenAI API key for LLM | None | Yes |
| `OPENAI_MODEL` | OpenAI model to use | gpt-4o | No |
| `MCP_SERVER_URL` | MCP server endpoint | http://127.0.0.1:8000/mcp | No |
| `INGESTION_API_URL` | FastAPI backend URL | http://127.0.0.1:8001 | No |
| `PORT` | FastAPI server port | 8001 | No |

### File Size Limits

Configured in `ingestion/config.py`:
- **Max File Size**: 100 MB (default)
- **Max Tables per File**: 10 (default)

## 📖 Usage

### Web Interface

1. **Upload File**:
   - Navigate to Upload tab
   - Select file (CSV, Excel, PDF, or Image)
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

### Example Queries

```
"Remove rows where price is greater than 1000"
"Sort the data by revenue in descending order"
"Fill missing values in the age column with the median"
"Filter rows where status equals 'Active'"
"Drop columns 'temp1' and 'temp2'"
"Group by department and calculate average salary"
"Create a new column 'full_name' by combining 'first_name' and 'last_name'"
```

### Visualization Examples

**Bar Chart**: Select categorical column for X, numeric column for Y
**Line Chart**: Perfect for time series data (date on X, value on Y)
**Scatter Plot**: Explore correlations between two numeric variables
**Histogram**: Distribution analysis of a single numeric column
**Box Plot**: Outlier detection and quartile visualization
**Pie Chart**: Proportional breakdown of categorical data
**Heatmap**: Correlation matrix or pivot table visualization

### Command Line (MCP Client)

```bash
# Interactive mode
python mcp_client.py

# Direct query
python mcp_client.py <session_id> "your query here"
```

## 📚 API Documentation

### FastAPI Endpoints

#### File Upload
```http
POST /api/ingestion/file-upload
Content-Type: multipart/form-data

Parameters:
- file: File (required)
- file_type: string (optional) - csv, excel, pdf, image
- session_id: string (optional) - Custom session ID

Response:
{
  "success": true,
  "session_id": "uuid",
  "metadata": {
    "file_type": "csv",
    "table_count": 1,
    "processing_time": 0.5
  },
  "tables": [...]
}
```

#### Get Session Tables
```http
GET /api/session/{session_id}/tables?format=summary

Response:
{
  "session_id": "uuid",
  "table_count": 1,
  "tables": {
    "current": {
      "row_count": 100,
      "column_count": 5,
      "columns": [...],
      "preview": [...]
    }
  }
}
```

#### Get Session Metadata
```http
GET /api/session/{session_id}/metadata

Response:
{
  "session_id": "uuid",
  "metadata": {
    "file_name": "data.csv",
    "file_type": "csv",
    "table_count": 1,
    "created_at": 1234567890
  }
}
```

#### Update Session Tables
```http
PUT /api/session/{session_id}/tables

Body:
{
  "tables": {
    "table_name": {
      "data": "base64_encoded_pickle",
      "row_count": 100,
      "column_count": 5,
      "columns": [...],
      "dtypes": {...}
    }
  },
  "metadata": {...}
}
```

#### List All Sessions
```http
GET /api/sessions

Response:
{
  "success": true,
  "count": 5,
  "sessions": [...]
}
```

#### Delete Session
```http
DELETE /api/session/{session_id}

Response:
{
  "success": true,
  "message": "Session deleted successfully"
}
```

#### Extend Session TTL
```http
POST /api/session/{session_id}/extend

Response:
{
  "success": true,
  "message": "Session TTL extended"
}
```

### Health Check
```http
GET /health

Response:
{
  "status": "healthy",
  "service": "ingestion-api",
  "redis_connected": true,
  "version": "1.1.0"
}
```

## 📁 Project Structure

```
Data-Assistant/
├── app.py                      # Streamlit frontend application
├── main.py                     # FastAPI backend server
├── mcp_client.py              # MCP client with LangChain integration
├── data_visualization.py      # Visualization Centre module
├── requirements.txt           # Python dependencies
├── README.md                  # This file
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
│   ├── pdf_handler.py        # PDF file processor (Docling)
│   └── image_handler.py      # Image file processor (OCR)
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
- **PDF**: Uses Docling for table extraction with OCR
- **Images**: Uses Gemini Vision API for OCR-based table extraction

**Key Functions**:
- `process_file()`: Main entry point for file processing
- `process_csv()`: CSV-specific handler
- `process_excel()`: Excel-specific handler
- `process_pdf()`: PDF-specific handler
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

### 5. Visualization Module (`data_visualization.py`)

**Purpose**: Provides zero-latency chart generation using Plotly with session data integration.

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

### 6. Streamlit Frontend (`app.py`)

**Purpose**: Web-based user interface for file upload, data manipulation, and visualization.

**Tabs**:
1. **Upload Tab**: File upload, processing, and preview
2. **Data Manipulation Tab**: Natural language queries, operation history, data preview
3. **Visualization Centre Tab**: Interactive chart generation with Plotly, export options

**Features**:
- Real-time data preview
- Operation history tracking
- Session management UI
- Error display and recovery
- Interactive visualizations with Plotly
- Chart export functionality

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

## 🐛 Troubleshooting

### Common Issues

**1. Redis Connection Failed**
```
Error: Upstash Redis not connected
```
**Solution**: Check `UPSTASH_REDIS_REST_URL` and `UPSTASH_REDIS_REST_TOKEN` in `.env`

**2. OpenAI API Key Missing**
```
Error: OPENAI_API_KEY environment variable is required
```
**Solution**: Set `OPENAI_API_KEY` in `.env` file

**3. MCP Server Not Running**
```
Error: Connection refused
```
**Solution**: Start MCP server: `cd data-mcp && python server.py`

**4. File Upload Fails**
```
Error: File size exceeds maximum
```
**Solution**: Check file size limit in `ingestion/config.py` or increase `MAX_FILE_SIZE`

**5. Session Expired**
```
Error: Session not found
```
**Solution**: Sessions expire after 30 minutes. Upload file again or extend TTL before expiration

**6. PDF/Image Processing Fails**
```
Error: Required library not installed
```
**Solution**: Install Docling: `pip install docling` (for PDF) or ensure Gemini API key is set (for images)

**7. Chart Export Fails**
```
Error: PNG/SVG export failed
```
**Solution**: Install Kaleido for static image exports: `pip install kaleido`

### Debug Mode

Enable debug logging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Checking Redis Connection

```python
from redis_db import is_connected
print(f"Redis connected: {is_connected()}")
```

## 📝 License

[Add your license here]

## 🤝 Contributing

[Add contribution guidelines here]

## 📧 Support

[Add support contact information here]

---

**Built with ❤️ for data analysts**

