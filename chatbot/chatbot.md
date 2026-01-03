# Chatbot Tab - Theory & Flow Plan

## 🎯 Overview

Intelligent conversational interface that answers data queries, detects when visualizations are needed, and manages session history. Provides context-aware answers using schema, statistics, and manipulation history.

---

## 🏗️ Core Capabilities

1. **Any User Query Related to Data** - Handles statistical, comparative, exploratory, debugging, and operational queries
2. **Smart Visualization Detection** - Automatically detects when charts are needed and selects appropriate chart types
3. **Context-Aware Responses** - Uses current schema, stats, and operation history for accurate answers
4. **Session History Management** - Maintains conversation context within session boundaries

---

## 🔄 System Flow

```
┌─────────────────┐
│  User Query     │
└────────┬────────┘
         │
         ▼
┌─────────────────────────┐
│  Query Intent Analyzer  │ ◄─── Detects: data query, visualization need, debug query
└────────┬────────────────┘
         │
         ├──────────────────┬──────────────────┐
         │                  │                  │
         ▼                  ▼                  ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ Context      │  │ Visualization│  │ Operation    │
│ Builder      │  │ Detector     │  │ History      │
└──────┬───────┘  └──────┬───────┘  └──────┬───────┘
       │                 │                  │
       │                 │                  │
       ├─────────────────┴──────────────────┤
       │                                     │
       ▼                                     ▼
┌──────────────────────────────────────────────────┐
│         Context Aggregation                      │
│  • Session schema & stats                        │
│  • Operation history (last 10 ops)               │
│  • Conversation history (last 10 messages)       │
│  • Visualization recommendation (if needed)      │
└──────────────┬───────────────────────────────────┘
               │
               ▼
┌──────────────────────────────┐
│   LLM Agent Processing       │
│  • Generate answer            │
│  • Execute data tools (if req)│
│  • Trigger chart generation   │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│   Response Formatter         │
│  • Text answer                │
│  • Chart (if applicable)      │
│  • Data snippets/tables       │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│   Display & Save             │
│  • Show response + chart      │
│  • Save to conversation history│
│  • Update session state       │
└──────────────────────────────┘
```

---

## 🧠 Visualization Detection Logic

### Explicit Visualization Requests
- **Keywords**: "show", "plot", "graph", "chart", "visualize", "display", "draw"
- **Action**: Always generate visualization

### Implicit Visualization Needs

| Query Pattern | Detection Signal | Recommended Chart Type |
|---------------|------------------|------------------------|
| Comparative queries | "compare", "which", "top N", "better", "difference" | Bar Chart |
| Trend queries | "over time", "change", "growth", "trend", "how has X changed" | Line Chart |
| Distribution queries | "distribution", "spread", "frequency", "how are X distributed" | Histogram (numeric) / Bar (categorical) |
| Relationship queries | "relationship", "correlation", "X vs Y", "related to" | Scatter Plot |
| Aggregation queries | "group by", "per X", "by category", "aggregate" | Bar Chart / Heatmap |
| Part-to-whole | "percentage", "proportion", "breakdown" | Pie Chart |
| Multiple metrics | "compare multiple", "side by side" | Combo Chart / Small Multiples |

### Decision Flow
```
Query Analysis
    │
    ├─► Has explicit viz keywords? ──YES──► Generate Chart
    │
    └─► NO
        │
        ├─► Is comparative/trend/distribution/relationship query? ──YES──► Generate Chart
        │
        └─► NO ──► Text-only response (can suggest visualization)
```

---

## 📝 Session History Management

### Storage Structure
```
Session History = {
    conversation_history: [
        {
            message_id: uuid,
            timestamp: timestamp,
            user_query: string,
            assistant_response: {
                text: string,
                visualization: ChartObject | null,
                tools_used: [string],
                data_accessed: [string]
            },
            context_snapshot: {
                session_state: {...},
                referenced_columns: [string]
            }
        }
    ],
    operation_history_link: [operation_ids],
    current_context: {
        active_tables: [string],
        recent_operations: [last_10_ops]
    }
}
```

### History Usage
- **Context Window**: Last 10 messages included in LLM context
- **Reference Resolution**: "the previous chart" → last visualization
- **Follow-up Questions**: Uses previous query context automatically
- **Operation Linking**: "Why did that happen?" → references last operation
- **Persistence**: Stored in Redis with session_id for cross-tab access

---

## 📊 Query Categories & Examples

### 1. Statistical Queries
**Examples:**
- "What's the average salary by department?"
- "Show me the median age"
- "What's the standard deviation of revenue?"
- "Calculate the 95th percentile of sales"

**Handling:** Calculate stats → Text response (no visualization unless requested)

---

### 2. Comparative Queries
**Examples:**
- "Which department has the highest average salary?"
- "Compare sales between Q1 and Q2"
- "Show me the top 10 customers by revenue"
- "Which region performs better: North or South?"

**Handling:** Aggregation → **Bar Chart** (automatic visualization)

---

### 3. Trend & Time Series Queries
**Examples:**
- "Show me sales over time"
- "How has revenue changed in the last quarter?"
- "Display monthly trends for user signups"
- "What's the growth rate of subscriptions?"

**Handling:** Time-based aggregation → **Line Chart** (automatic visualization)

---

### 4. Distribution Queries
**Examples:**
- "What is the distribution of ages?"
- "Show me how salaries are distributed"
- "Display the frequency of each category"
- "What is the shape of the revenue distribution?"

**Handling:** Distribution analysis → **Histogram** (numeric) or **Bar Chart** (categorical)

---

### 5. Relationship & Correlation Queries
**Examples:**
- "Is there a relationship between price and sales?"
- "Show correlation between age and salary"
- "What's the relationship between marketing spend and revenue?"
- "Plot X vs Y to see if they're related"

**Handling:** Correlation analysis → **Scatter Plot** (automatic visualization)

---

### 6. Aggregation & Grouping Queries
**Examples:**
- "Group by department and show average salary"
- "What is the total revenue per region?"
- "Count the number of orders by product category"
- "Aggregate sales by month and region"

**Handling:** Group aggregation → **Bar Chart** (single group) or **Heatmap** (multi-group)

---

### 7. Debug & Explanation Queries
**Examples:**
- "Why did the row count drop after my last change?"
- "What operations were performed on this data?"
- "Explain what happened in the last transformation"
- "What filter was applied that removed these rows?"

**Handling:** Query operation history → Text explanation + optional visualization (row count over operations)

---

### 8. Exploratory & Insight Queries
**Examples:**
- "What insights can you find in this data?"
- "Tell me something interesting about the sales data"
- "What anomalies or outliers exist?"
- "What are the key patterns I should know about?"
- "Give me a data summary with highlights"

**Handling:** Multiple analyses → Synthesize insights → **Multiple Charts** (small multiples or faceted views)

---

### 9. Filtering & Subset Queries
**Examples:**
- "What is the average salary for active employees only?"
- "Show me data where revenue > 100000"
- "What are the statistics for the last 6 months?"
- "Filter by department='Engineering' and show results"

**Handling:** Apply filters → Analyze filtered data → Text response (visualization if comparative)

---

### 10. Data Quality Queries
**Examples:**
- "How many missing values are in each column?"
- "Are there any duplicate rows?"
- "What data quality issues exist?"
- "What percentage of records are complete?"

**Handling:** Data quality analysis → Text report + **Bar Chart** (missing values per column)

---

### 11. Multi-Table Queries
**Examples:**
- "Join the customers and orders tables and show revenue by customer"
- "Compare data between table1 and table2"
- "What's the difference between these two tables?"

**Handling:** Multi-table operations → Joined result → Visualization based on query type

---

### 12. Operational Queries (Perform Actions)
**Examples:**
- "Filter the data to show only active records"
- "Sort by revenue in descending order"
- "Remove rows with missing email addresses"
- "Create a new column for full name"

**Handling:** Execute via MCP tools → Update session → Show result + confirmation

---

## 🔗 Integration Points

### 1. Session Data Access
- Uses same `session_id` as other tabs
- Accesses schema, stats, preview via Session API
- Shares state with Data Manipulation and Visualization tabs

### 2. Operation History Integration
- Reads from operation history (last 10 operations)
- Can reference specific operations in explanations
- Can trigger operations via MCP if user requests from chat

### 3. Visualization Module Integration
- Uses existing `data_visualization` module for chart generation
- Leverages `smart_recommendations` for chart type selection
- Supports all chart types: bar, line, scatter, area, box, histogram, pie, heatmap

### 4. MCP Server Integration
- Can execute data manipulations from chat
- Uses same MCP client as Data Manipulation tab
- Maintains operation consistency

---

## 🎯 Key Design Principles

1. **Context-Aware**: Always uses current schema, stats, and operation history
2. **Proactive Visualization**: Detects when charts would help, not just when explicitly requested
3. **Conversational Memory**: Maintains context across messages in session
4. **Unified State**: Shares session state with other tabs seamlessly
5. **Intelligent Responses**: Combines data access, analysis, and visualization automatically

---

## 📈 Success Criteria

- **Answer Accuracy**: Correctly answers data-related queries using session context
- **Visualization Relevance**: Auto-detected charts are useful and appropriate
- **Context Retention**: Maintains conversation flow with proper references
- **Performance**: Fast response times (< 5 seconds for text, < 10 seconds with chart)
- **User Satisfaction**: Users find answers helpful and visualizations insightful

---

*This chatbot integrates seamlessly with the existing Data Assistant Platform, providing intelligent, context-aware data analysis through natural language conversation.*

