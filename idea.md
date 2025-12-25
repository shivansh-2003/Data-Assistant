# Data Analyst Agentic Platform

**A powerful, multi-modal data analysis platform that lets you upload messy real-world files, clean and transform data with natural language, create interactive visualizations instantly, and ask questions about your data — all in one intuitive three-tab interface.**

---

## 🎯 Why This Platform?

Most data analysis tools force you to:
- Manually clean PDFs or scanned tables
- Write code for every transformation
- Switch between tools for visualization and insights

This platform solves that by combining:
- **Smart ingestion** of CSV, Excel, PDFs, and images with tables
- **Natural language data manipulation** (no coding required)
- **Lightning-fast interactive charts** (drag-and-drop, no waiting)
- **AI-powered insights** via a contextual chatbot
- **Seamless state sharing** across all features

Perfect for analysts, researchers, business users, and anyone dealing with real-world data reports.

---

## ✨ Key Features

### Multi-Format Data Upload
- Upload **CSV**, **Excel**, **PDFs** (even multi-page reports), and **images** containing tables
- Powered by **Docling** — state-of-the-art table extraction with layout preservation and OCR
- Automatic schema inference and data profiling on upload

### Three Dedicated Tabs (Shared State)

#### 📊 **Data Manipulation Tab**
- Describe changes in plain English:  
  _"Remove outliers where sales > 1,000,000 and fill missing ages with the median"_
- Powered by LLM → tool selection → safe pandas execution
- Real-time preview with change summary (e.g., "Removed 15 rows, filled 82 values")
- Full operation history with **undo/redo**
- Supports multi-table joins and cross-table operations
- Batch pipeline execution

#### 📈 **Visualization Centre**
- **Zero-latency** chart generation (no LLM involved)
- Drag-and-drop column mapping
- Supports: Bar, Line, Scatter, Area, Heatmap, Box, Histogram, Pie, and more
- Full interactivity via Plotly (zoom, filter, hover)
- One-click export: PNG, SVG, or interactive HTML
- Direct aggregation (sum, mean, count, etc.)

#### 💬 **Chatbot Tab**
- Ask anything about your current data:  
  _"What’s the average salary by department?"_  
  _"Why did the row count drop after my last change?"_
- Context-aware answers using schema, stats, and manipulation history
- Explains patterns, trends, and anomalies in natural language
- Helps debug transformations with root-cause explanations

### Session Persistence
- All tabs share the **same live data state**
- Operation history, chat context, and charts persist across tabs and page refreshes
- Automatic cleanup after 7 days of inactivity

---

## 🔄 How It Works

```mermaid
graph TD
    A[Upload Files<br>(CSV, Excel, PDF, Images)] --> B[Docling Ingestion<br>Table Extraction + OCR]
    B --> C[Schema Inference<br>& Initial Profiling]
    C --> D[Session Created<br>DuckDB Shared State]

    D --> E[Data Manipulation Tab]
    D --> F[Visualization Centre]
    D --> G[Chatbot Tab]

    E --> H[Natural Language → LangChain Agent]
    H --> I[FastMCP Server → Pandas Tools]
    I --> J[Update DuckDB State + History]

    J --> F
    J --> G

    F --> K[Direct DuckDB Query → Plotly Chart]
    G --> L[Context + Stats → LLM Response]
```

---

## 🛠 Tech Stack

| Layer              | Technology                                                                 |
|---------------------|----------------------------------------------------------------------------|
| **Frontend**        | Streamlit (fast, session-aware UI)                                         |
| **AI & Agents**     | LangChain, Gemini (primary), OpenAI (fallback), FastMCP (safe tool calling) |
| **Data Processing** | Docling (ingestion), Pandas (transformations), DuckDB (shared state)       |
| **Visualization**   | Plotly (interactive), Matplotlib (static fallback)                         |
| **Backend**         | FastAPI (APIs for viz, state, ingestion)                                   |
| **Deployment**      | Render (multi-service: Streamlit, FastAPI, MCP server, background workers) |

---

## 🚀 Quick Start (Local Development)

```bash
# Clone the repo
git clone https://github.com/your-org/data-analyst-platform.git
cd data-analyst-platform

# Set up virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set API keys
export GEMINI_API_KEY="your-gemini-key"      # Primary LLM
export OPENAI_API_KEY="your-openai-key"      # Optional fallback

# Run services in separate terminals

# Terminal 1: MCP Server (pandas tools)
python mcp_server.py --port 8001

# Terminal 2: FastAPI Backend
uvicorn fastapi_app:app --reload --port 8000

# Terminal 3: Streamlit App
streamlit run app.py
```

Open **http://localhost:8501** to start analyzing!

---

## 📦 Requirements

Key packages (see `requirements.txt` for full list):

```
streamlit==1.28.0
fastapi==0.104.1
langchain==0.0.350
langchain-google-genai
fastmcp==0.3.1
docling==1.2.0
pandas==2.1.3
duckdb==0.9.2
plotly==5.17.0
```

---

## ☁️ Deployment on Render

Deploy as three services:

1. **Private Service** – MCP Server (sandboxed pandas execution)
2. **Web Service** – FastAPI Backend (APIs + state management)
3. **Web Service** – Streamlit App (main UI)

Full `render.yaml` examples included in repo.

---

## 💡 Usage Examples

### Manipulation Tab
**You type:**  
"Drop rows with missing email, convert 'date' column to datetime, and sort by revenue descending"

**Platform does:**
- Previews changes
- Shows: "Dropped 45 rows, converted date column, sorted data"
- Adds to history (undo available)

### Visualization Centre
- Drag **Department** → X-axis
- Drag **Revenue** → Y-axis
- Select **Bar Chart** + **Sum** aggregation
→ Instant interactive chart appears

### Chatbot Tab
**You ask:**  
"Show me the top 3 departments by average salary and explain any surprises"

**Chatbot replies:**  
"Top 3: Engineering ($142k), Sales ($118k), Executive ($105k).  
Surprisingly, Marketing ranks 5th despite high headcount — likely due to more junior roles."

**You ask:**  
"Why is the total row count now 1,248 instead of 1,500?"

**Chatbot:**  
"You previously filtered out rows where 'status' != 'Active' (removed 187) and then dropped duplicates on 'employee_id' (removed 65 more)."

