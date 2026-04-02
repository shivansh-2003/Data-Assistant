# InsightBot (Chatbot)

LangGraph-powered conversational analytics for the Data Assistant platform. InsightBot classifies intent, resolves context and clarification, generates and safely executes pandas code, configures visualizations, and returns natural-language insights with optional charts. Conversation memory and per-turn response snapshots keep history and visualizations intact across turns.

---

## Table of Contents

- [Responsibilities](#responsibilities)
- [Architecture Overview](#architecture-overview)
- [LLM Model Assignments](#llm-model-assignments)
- [State Schema](#state-schema)
- [Graph and Flow](#graph-and-flow)
- [Nodes (Logical Implementation)](#nodes-logical-implementation)
- [Tools](#tools)
- [Execution (Code Generation & Safe Run)](#execution-code-generation--safe-run)
- [Prompts](#prompts)
- [UI and Session Loading](#ui-and-session-loading)
- [File Structure](#file-structure)
- [How to Run and Test](#how-to-run-and-test)
- [Limitations and Troubleshooting](#limitations-and-troubleshooting)

---

## Responsibilities

- **Intent & routing:** Classify user intent (data query, visualization, small talk, report, summarize_last) and route to the right path; handle follow-ups and clarification.
- **Context resolution:** Resolve short follow-ups (e.g. "What about the maximum?") into full questions using conversation context.
- **Column disambiguation:** When the user mentions a term that matches multiple columns, ask for clarification ("Did you mean X or Y?") and resolve on the next turn.
- **Code generation & execution:** Generate pandas code from the query and run it in a sandboxed environment with timeout and error handling.
- **Visualization:** Validate chart parameters, build Plotly figures via the shared `data_visualization` module, and handle viz failures (e.g. too many categories) with fallback to tables.
- **Response formatting:** Combine insight text, chart/table, and optional "see code" expander; support report and summarize_last formats.
- **Memory & snapshots:** Persist conversation with LangGraph checkpointer; keep per-turn `response_snapshots` so the UI can show each message's chart/table/code (previous visualizations do not disappear on new queries).
- **Suggestions:** Generate three contextual follow-up question chips after each response.

---

## Architecture Overview

- **Framework:** LangGraph `StateGraph` with typed state.
- **Memory:** `MemorySaver` (thread/session-based checkpoints).
- **LLM:** OpenAI gpt-4o (complex reasoning) and gpt-4o-mini (classification, summarization, suggestions). See [LLM Model Assignments](#llm-model-assignments).
- **LLM Initialisation:** Singleton registry (`llm_registry.py`) — one `ChatOpenAI` instance per `(model, temperature, max_tokens)` tuple, reused for the process lifetime. Eliminates ~200ms/node of per-call object-creation overhead (~1.4s/query saved).
- **Tools:** LangChain tools (insight_tool, bar_chart, line_chart, scatter_chart, histogram, etc.) with function calling from the analyzer.
- **Execution:** Safe pandas execution with timeout and controlled namespace; correlation and analysis rules enforced via prompts (e.g. numeric-only correlation).
- **Streaming:** Graph is invoked with `graph.stream(stream_mode='values')` so the response is rendered as soon as the responder node finishes, before the suggestion node completes (~1–2s perceived vs 15s all-or-nothing).

---

## LLM Model Assignments

Managed centrally in `chatbot/llm_registry.py`. Override any assignment via environment variables without code changes.

| Node / Task | Model | Temp | max_tokens | Rationale |
|---|---|---|---|---|
| Router (intent classification) | gpt-4o-mini | 0.0 | 256 | Binary routing; no schema reasoning needed |
| Context Resolver (follow-up) | gpt-4o-mini | 0.0 | 128 | One-sentence output |
| Analyzer (tool selection) | gpt-4o | 0.1 | — | Schema-aware reasoning |
| Planner (multi-step breakdown) | gpt-4o | 0.1 | — | Complex multi-step output |
| Code Generator (pandas) | gpt-4o | 0.1 | — | Accuracy on data operations |
| Summarizer (`summarize_insight`) | gpt-4o-mini | 0.2 | 256 | Simple paraphrase of results |
| Suggestion Engine | gpt-4o-mini | 0.4 | 128 | 3 short questions |
| Small Talk / Fallback Responder | gpt-4o-mini | 0.7 / 0.3 | 150 / 512 | Conversational replies |

**Environment variable overrides:**
```bash
MAIN_MODEL=gpt-4o          # Analyzer, Planner, Code Gen
MINI_MODEL=gpt-4o-mini     # Summarizer, Suggestions, Small Talk
ROUTER_MODEL=gpt-4o-mini   # Router specifically
CONTEXT_RESOLVER_MODEL=gpt-4o-mini
SUGGESTION_MODEL=gpt-4o-mini
```

**Latency impact of model assignments:**

| Source | Saving per query |
|---|---|
| Singleton registry (no repeated init) | ~1.4s |
| Router: gpt-4o → mini | ~1.7s |
| Context Resolver: gpt-4o → mini | ~1.4s |
| Summarizer: gpt-4o → mini | ~1.0s |
| Suggestion Engine: gpt-4o → mini | ~1.4s |
| Planner skip for simple queries | ~2.0s (~80% of queries) |
| Streaming UI (perceived latency) | 15s → ~1–2s first token |

---

## State Schema

Defined in `state.py` as a `TypedDict`. DataFrames are not stored in state; they are loaded from Redis by `session_id` when needed.

| Field | Purpose |
|-------|---------|
| `session_id` | Identifies the user session and Redis data. |
| `messages` | Conversation history (annotated with `add_messages` for append/reduce). |
| `schema`, `operation_history`, `table_names` | Data context (metadata only). |
| `intent` | Router output: data_query, visualization_request, small_talk, report, summarize_last. |
| `entities` | Extracted columns, operations, aggregations. |
| `tool_calls` | Selected tools and parameters from the analyzer. |
| `plan` | Multi-step plan: list of dicts with step, description, code, output_var. |
| `needs_planning` | True if query requires multi-step reasoning. |
| `effective_query` | Resolved full question (e.g. after context resolution or clarify). |
| `conversation_context` | last_columns, last_aggregation, last_group_by, active_filters, current_topic, last_query. |
| `needs_clarification` | True when multiple columns match one user mention. |
| `clarification_*` | Options, type, resolved choice, original query. |
| `last_insight`, `insight_data` | Text insight and optional DataFrame-as-dict for tables. |
| `viz_config`, `viz_type`, `chart_reason` | Chart configuration and one-line reason. |
| `one_line_insight`, `generated_code` | Single-sentence takeaway and code for "see how this was computed". |
| `error`, `error_suggestion`, `viz_error` | Errors and "did you mean" suggestions. |
| `sources`, `suggestions` | Tools used and three follow-up question strings. |
| `response_snapshots` | List of dicts per AI turn: viz_config, insight_data, generated_code, viz_error (so UI can render each turn's chart/table/code). |

---

## Graph and Flow

- **Entry:** `router`.
- **Router →** `clarification` (if needs_clarification), `responder` (small_talk), `insight` (summarize_last), or `analyzer`.
- **Clarification →** `END` (no tools this turn).
- **Analyzer →** `planner` (complex queries only — YoY, cohort, rolling avg, trend/correlate sub-intent, or query >25 words), `insight` (simple queries, ~80%), `viz`, or `responder`.
- **Planner →** `insight` (creates multi-step plan).
- **Insight →** `viz` (if viz tools in tool_calls) or `responder`.
- **Viz →** `responder`.
- **Responder →** `suggestion` → `END`.

```mermaid
flowchart TD
    %% ─────────────────────────────────────────
    %%  ENTRY
    %% ─────────────────────────────────────────
    USER(["👤 User Query\n(Streamlit UI)"])
    SESSION["SessionLoader\nLoad schema + df_dict\nfrom Redis by session_id"]
    USER --> SESSION --> ROUTER

    %% ─────────────────────────────────────────
    %%  ROUTER NODE
    %% ─────────────────────────────────────────
    subgraph ROUTER_NODE ["🟣 ROUTER NODE  ·  gpt-4o-mini  (temp=0.0, max_tokens=256)"]
        ROUTER["Intent Classification\ndata_query / visualization_request\nsmall_talk / report / summarize_last"]
        FOLLOWUP{"is_follow_up?"}
        RESOLVER["Context Resolver\ngpt-4o-mini (max_tokens=128)\nResolve short follow-up\n→ effective_query"]
        AMBIGUITY{"Column\nAmbiguity?"}
        ROUTER --> FOLLOWUP
        FOLLOWUP -->|"Yes"| RESOLVER --> AMBIGUITY
        FOLLOWUP -->|"No"| AMBIGUITY
    end

    %% ─────────────────────────────────────────
    %%  ROUTING DECISION FROM ROUTER
    %% ─────────────────────────────────────────
    AMBIGUITY -->|"Multiple columns\nmatch term"| CLARIFY
    AMBIGUITY -->|"small_talk"| RESPONDER
    AMBIGUITY -->|"summarize_last"| INSIGHT
    AMBIGUITY -->|"data_query /\nviz / report"| ANALYZER

    %% ─────────────────────────────────────────
    %%  CLARIFICATION NODE
    %% ─────────────────────────────────────────
    subgraph CLARIFY_NODE ["🔴 CLARIFICATION NODE"]
        CLARIFY["Emit: 'Did you mean X or Y?'\nStore clarification_options\nclarification_original_query"]
    end
    CLARIFY --> END1(["END\n(wait for next turn)"])

    %% ─────────────────────────────────────────
    %%  ANALYZER NODE
    %% ─────────────────────────────────────────
    subgraph ANALYZER_NODE ["🟠 ANALYZER NODE  ·  gpt-4o  (temp=0.1)"]
        ANALYZER["LLM Function Calling\nllm.bind_tools(all_tools)\nSelect tools + params\nbased on schema + intent"]
        COERCE["Post-process:\nCorrelation query?\nCoerce bar/scatter → heatmap_chart"]
        ANALYZER --> COERCE
    end

    COERCE --> ANALYZER_ROUTE{"route_after_\nanalyzer()"}
    ANALYZER_ROUTE -->|"insight_tool\nselected"| PLANNER_GATE
    ANALYZER_ROUTE -->|"viz tools only\n(no insight_tool)"| VIZ
    ANALYZER_ROUTE -->|"no tools /\nsmall_talk"| RESPONDER

    %% ─────────────────────────────────────────
    %%  PLANNER GATE  (complexity check in graph.py)
    %% ─────────────────────────────────────────
    subgraph PLANNER_GATE_BOX ["⚡ PLANNER SKIP GATE  (graph.py)"]
        PLANNER_GATE{"Complex query?\nKeywords: yoy · rolling avg\ncohort · percentile · trend\nSub-intent: trend/correlate/report\nor query > 25 words"}
    end

    PLANNER_GATE -->|"~20% complex"| PLANNER
    PLANNER_GATE -->|"~80% simple\n(skip saves ~2s)"| INSIGHT

    %% ─────────────────────────────────────────
    %%  PLANNER NODE
    %% ─────────────────────────────────────────
    subgraph PLANNER_NODE ["🔥 PLANNER NODE  ·  gpt-4o  (temp=0.1)"]
        PLANNER["Break query into\nmulti-step plan\n[{step, description, code, output_var}]"]
    end
    PLANNER --> INSIGHT

    %% ─────────────────────────────────────────
    %%  INSIGHT NODE
    %% ─────────────────────────────────────────
    subgraph INSIGHT_NODE ["🔵 INSIGHT NODE"]
        INSIGHT["Load DataFrames\nfrom Redis"]
        SUMMARIZE_CHECK{"intent ==\nsummarize_last?"}
        SUMMARIZE_LAST["Re-summarize\nlast_insight\ngpt-4o-mini"]
        RULE_CHECK{"Rule-based\nexecutor match?\nmean/sum/count/min/max"}
        RULE_EXEC["rule_based_executor.py\nDirect pandas ops\n0 LLM calls · ~2.5s saved"]
        PLAN_CHECK{"plan\nexists?"}
        PLAN_EXEC["Execute plan steps\nsequentially\n_execute_plan()"]
        CODE_GEN["code_generator.py\ngpt-4o generates\npandas code"]
        SAFE_EXEC["safe_executor.py\nRestricted namespace\nTimeout + guardrails\nRow limit 100k"]
        SUMMARIZER["Summarize result\ngpt-4o-mini\n(max_tokens=256)\n→ last_insight"]

        INSIGHT --> SUMMARIZE_CHECK
        SUMMARIZE_CHECK -->|"Yes"| SUMMARIZE_LAST --> RESP_ROUTE2
        SUMMARIZE_CHECK -->|"No"| RULE_CHECK
        RULE_CHECK -->|"Yes · ~30% of queries"| RULE_EXEC --> SUMMARIZER
        RULE_CHECK -->|"No"| PLAN_CHECK
        PLAN_CHECK -->|"Yes (complex)"| PLAN_EXEC --> SUMMARIZER
        PLAN_CHECK -->|"No (simple)"| CODE_GEN --> SAFE_EXEC --> SUMMARIZER
    end

    SUMMARIZER --> VIZ_CHECK{"viz tool\nin tool_calls?"}
    VIZ_CHECK -->|"Yes"| VIZ
    VIZ_CHECK -->|"No"| RESPONDER

    %% ─────────────────────────────────────────
    %%  VIZ NODE
    %% ─────────────────────────────────────────
    subgraph VIZ_NODE ["🩵 VIZ NODE"]
        VIZ["Read chart tool_calls\nValidate config"]
        REDIS_LOAD["Load DataFrame\nfrom Redis"]
        PLOTLY["data_visualization module\nBuild Plotly figure"]
        FALLBACK{"Chart OK?"}
        CHART_OK["Set viz_config\nviz_type · chart_reason"]
        CHART_FAIL["Set viz_error\nFallback → table"]

        VIZ --> REDIS_LOAD --> PLOTLY --> FALLBACK
        FALLBACK -->|"Yes"| CHART_OK
        FALLBACK -->|"Too many categories\nor other failure"| CHART_FAIL
    end

    CHART_OK --> RESPONDER
    CHART_FAIL --> RESPONDER

    %% ─────────────────────────────────────────
    %%  RESPONDER NODE
    %% ─────────────────────────────────────────
    subgraph RESPONDER_NODE ["🟢 RESPONDER NODE"]
        RESPONDER["Format AIMessage\nInsight text + chart/table\n+ optional 'see code' expander"]
        SMALL_TALK_RESP{"small_talk?"}
        ST_LLM["gpt-4o-mini\nFriendly reply"]
        SNAPSHOT["Append response_snapshot\n(viz_config · insight_data\ngenerated_code · viz_error)\n→ per-turn visualization preserved"]

        RESPONDER --> SMALL_TALK_RESP
        SMALL_TALK_RESP -->|"Yes"| ST_LLM --> SNAPSHOT
        SMALL_TALK_RESP -->|"No"| SNAPSHOT
    end

    RESP_ROUTE2 --> RESPONDER

    %% ─────────────────────────────────────────
    %%  SUGGESTION NODE
    %% ─────────────────────────────────────────
    subgraph SUGGESTION_NODE ["🟡 SUGGESTION NODE  ·  gpt-4o-mini  (temp=0.4, max_tokens=128)"]
        SUGGEST["Generate 3 follow-up\nquestion chips"]
        FALLBACK_CHIPS["Intent-aware pre-defined\nfallbacks if LLM fails\n(chips always appear)"]
        SUGGEST -->|"LLM success"| CHIPS["Return 3 chips"]
        SUGGEST -->|"LLM failure"| FALLBACK_CHIPS --> CHIPS
    end

    SNAPSHOT --> SUGGEST

    %% ─────────────────────────────────────────
    %%  MEMORY + STREAM
    %% ─────────────────────────────────────────
    CHIPS --> MEMORY["MemorySaver\nCheckpoint\n(thread/session-based)"]
    MEMORY --> STREAM(["graph.stream(stream_mode='values')\n~1–2s perceived latency\nProgressive status captions\nUI renders on responder completion"])

    %% ─────────────────────────────────────────
    %%  LLM REGISTRY (cross-cutting)
    %% ─────────────────────────────────────────
    subgraph LLM_REG ["🔋 LLM REGISTRY  (llm_registry.py)"]
        REG["Singleton cache\nOne ChatOpenAI per\n(model · temp · max_tokens)\nSaves ~1.4s per query"]
    end

    %% ─────────────────────────────────────────
    %%  STYLES
    %% ─────────────────────────────────────────
    style USER fill:#4CAF50,color:#fff
    style SESSION fill:#607D8B,color:#fff
    style ROUTER fill:#9C27B0,color:#fff
    style RESOLVER fill:#AB47BC,color:#fff
    style CLARIFY fill:#E91E63,color:#fff
    style END1 fill:#b0bec5,color:#333
    style ANALYZER fill:#FF9800,color:#fff
    style COERCE fill:#FFA726,color:#fff
    style PLANNER_GATE fill:#FF7043,color:#fff
    style PLANNER fill:#FF5722,color:#fff
    style INSIGHT fill:#1565C0,color:#fff
    style SUMMARIZE_LAST fill:#1976D2,color:#fff
    style RULE_EXEC fill:#0288D1,color:#fff
    style CODE_GEN fill:#0277BD,color:#fff
    style SAFE_EXEC fill:#01579B,color:#fff
    style SUMMARIZER fill:#0D47A1,color:#fff
    style VIZ fill:#00838F,color:#fff
    style REDIS_LOAD fill:#00695C,color:#fff
    style PLOTLY fill:#00796B,color:#fff
    style CHART_OK fill:#2E7D32,color:#fff
    style CHART_FAIL fill:#C62828,color:#fff
    style RESPONDER fill:#388E3C,color:#fff
    style ST_LLM fill:#43A047,color:#fff
    style SNAPSHOT fill:#2E7D32,color:#fff
    style SUGGEST fill:#F9A825,color:#333
    style FALLBACK_CHIPS fill:#F57F17,color:#fff
    style CHIPS fill:#F9A825,color:#333
    style MEMORY fill:#455A64,color:#fff
    style STREAM fill:#4CAF50,color:#fff
    style REG fill:#37474F,color:#fff
```

**Planner skip complexity gate** (in `graph.py`):
A query routes directly to `insight` unless it contains complex keywords (`year over year`, `yoy`, `rolling average`, `cumulative`, `cohort`, `percentile`, etc.), has sub-intent `trend`, `correlate`, or `report`, or is longer than 25 words. ~80% of typical data queries skip the planner entirely, saving ~2s.

---

## Nodes (Logical Implementation)

| Node | File | Responsibility |
|------|------|----------------|
| **Router** | `nodes/router.py` | Classify intent (data_query, visualization_request, small_talk, report, summarize_last). Uses **gpt-4o-mini** (temp=0.0, max_tokens=256). Set `is_follow_up` and resolve context: if follow-up, call context_resolver (**gpt-4o-mini**, max_tokens=128) to produce `effective_query`. Detect ambiguous column mentions and set `needs_clarification` + `clarification_options`. |
| **Clarification** | `nodes/clarification.py` | When multiple columns match one mention, emit an assistant message asking the user to choose (e.g. "Did you mean: ColA or ColB?"). On next turn, router/insight use `clarification_resolved` to substitute the chosen column into the query. |
| **Analyzer** | `nodes/analyzer.py` | Select tools and parameters from the query (and schema) using **gpt-4o** (temp=0.1). Output `tool_calls`. Route to planner (complex queries), insight (simple), viz, or responder. Post-processes tool_calls to coerce bar/scatter → heatmap for correlation queries. |
| **Planner** | `nodes/planner.py` | Break down complex queries into multi-step plans using **gpt-4o** (temp=0.1). Only invoked for ~20% of queries (YoY, rolling, cohort, trend, correlate, report, or >25 words). Creates plan with step descriptions and code. For simple queries, the router skips this node entirely. |
| **Insight** | `nodes/insight.py` | Use `effective_query` (or clarified query). Try rule-based execution first (for simple queries — zero LLM calls). If `plan` exists, execute plan steps sequentially. Otherwise, call code_generator (**gpt-4o**) to produce pandas code. Summarize result with **gpt-4o-mini** (max_tokens=256). Run in safe_executor (with validation, row limits, profiling). Handle summarize_last. Map result to `last_insight`, `insight_data`, `one_line_insight`, `generated_code`. On executor/column errors, set `error` and optional `error_suggestion`. |
| **Viz** | `nodes/viz.py` | Read `tool_calls` for chart tools; validate and build config. Call `data_visualization` to generate Plotly figure. Set `viz_config`, `viz_type`, `chart_reason`; on failure set `viz_error` (e.g. too many categories). |
| **Responder** | `nodes/responder.py` | Format final assistant message from intent, `last_insight`, `viz_config`, `viz_error`, `insight_data`. Handle small_talk (**gpt-4o-mini**), did_you_mean, and generic errors. Append AIMessage to `messages` and append current turn's snapshot to `response_snapshots` (viz_config, insight_data, generated_code, viz_error). |
| **Suggestion** | `nodes/suggestion_engine.py` | Generate three follow-up questions using **gpt-4o-mini** (temp=0.4, max_tokens=128). Intent-aware pre-defined fallbacks (compare, trend, correlate, segment, distribution, filter, report) returned instantly on any LLM failure — suggestions always appear, never empty. |

---

## Data Profiling Layer

Comprehensive data profiling runs automatically before any query:

- **Missing Value %**: Percentage of null values per column
- **Cardinality**: Low (<10), Medium (10-100), High (>100) unique values
- **Numeric Distribution**: Mean, median, std, min, max, quartiles for numeric columns
- **Category Counts**: Top 10 most frequent values for categorical columns

Profiles are:
- **Injected into prompts** for better tool selection and code generation
- **Used for chart validation** to prevent unsuitable visualizations
- **Used for smart chart selection** based on data characteristics

See `DATA_PROFILING.md` for detailed documentation.

## Code Execution Guardrails

InsightBot includes comprehensive guardrails for safe code execution:

1. **Code Validation**: Blocks forbidden operations (`.plot()`, file writes, `eval()`, etc.)
2. **Result Variable Enforcement**: Ensures code assigns to `result` variable
3. **Row Limit Enforcement**: Truncates results to max 100k rows
4. **Execution Time Profiling**: Tracks execution time for monitoring
5. **Rule-Based Fast Path**: Handles simple queries (mean, sum, count, max, min) without any LLM call — ~2.5s saved for ~30% of queries

See `execution/GUARDRAILS.md` for detailed documentation.

## Tools

InsightBot uses LangChain's `@tool` decorator pattern for tool definition and LLM function calling:
https://docs.langchain.com/oss/python/langchain/tools

**Tool Definition & Selection:**
- Tools are defined with `@tool` decorator in `chatbot/tools/`
- Analyzer node binds tools to LLM using `llm.bind_tools(tools)`
- LLM selects which tools to call based on user query
- Tool calls are extracted and stored in `state["tool_calls"]`

**Tool Execution (Custom Pattern):**
Unlike LangChain's `ToolNode` (which auto-executes tools), InsightBot uses specialized execution nodes:
- **`insight_tool`** (`tools/data_tools.py`): Executed in `insight_node` for pandas code generation and execution
- **Chart tools** (`tools/simple_charts.py`, `tools/complex_charts.py`): Executed in `viz_node` for chart config validation and storage

This custom pattern allows:
- Domain-specific execution logic (data analysis vs visualization)
- Better error handling per tool type
- Separation of concerns (config generation vs execution)

**Available Tools:**
- `insight_tool`: Data analysis queries (mean, sum, filter, groupby, correlation, etc.)
- `bar_chart`, `line_chart`, `scatter_chart`, `histogram`, `area_chart`, `box_chart`, `heatmap_chart`, `correlation_matrix`: Visualization tools
- `combo_chart`, `dashboard`: Complex visualization tools

---

## Execution (Code Generation & Safe Run)

- **`execution/code_generator.py`:** Uses **gpt-4o** (singleton from registry) via the code_generator prompt to produce pandas code. Prompts enforce:
  - **Correlation:** Only numeric columns. Generic "show correlation" → `df.select_dtypes(include=['number']).corr()`. Two columns → `df['col1'].corr(df['col2'])`. Never full `df.corr()` or `groupby(...).corr()` with no arguments.
  - **Categorical vs numeric:** "Correlation between X and [categorical]" → groupby + agg (e.g. mean/count), not correlation.
  - Filtering, grouping, "for each" (idxmax/idxmin), etc. as in prompts.
- **`execution/rule_based_executor.py`:** Called first in `insight_node` before any LLM. Handles mean, sum, count, min, max queries with direct pandas operations — zero API cost, zero latency.
- **`execution/safe_executor.py`:** Runs the code in a restricted namespace (e.g. only `df`, `pd`, `result`), with timeout and exception handling. Returns result or raises; insight node maps failures to `error` and `error_suggestion`.

---

## Prompts

All in `prompts/` (one file per prompt, loaded via `prompts/__init__.py`):

| Prompt | Use |
|--------|-----|
| **router** | Intent classification, follow-up detection, entity extraction, conversation_context. |
| **context_resolver** | Turn short follow-ups into one full natural-language question. |
| **analyzer** | Tool selection and parameters; schema-aware. |
| **code_generator** | Pandas code from query; correlation rules, filtering, groupby, "for each" patterns. |
| **summarizer** | One-sentence takeaway + optional second sentence from pandas output. |
| **responder** | Not used as a single LLM call; responder node composes from state. |
| **small_talk** | Friendly short replies. |
| **suggestions** | Three follow-up questions for UI chips. |

---

## UI and Session Loading

- **`streamlit_ui.py`:** Renders the InsightBot tab: session pill, sidebar (options, quick actions, clear chat), chat history, suggestion chips, and input. Uses `graph.get_state(config)` and invokes the graph via `ui/chat_input.py`. **Message history:** When `response_snapshots` is present, `display_message_history` iterates messages and for each AI message renders its snapshot (table if no chart/viz_error, chart from `viz_config`, code expander). So previous visualizations stay visible when the user sends a new query.
- **`ui/chat_input.py`:** Handles chat input and invokes the graph using **`graph.stream(stream_mode='values')`**. Yields full state snapshots after each node completes. Shows progressive status captions (`Understanding your question…` → `Selecting analysis tools…` → `Composing response…`) while nodes run. As soon as the responder appends its `AIMessage`, the response is rendered immediately — before the suggestion node finishes. Calls `st.rerun()` at the end to load the full message history with charts/tables/chips.
- **`utils/session_loader.py`:** Loads DataFrames and metadata from Redis by `session_id`; `prepare_state_dataframes()` returns schema, df_dict, operation_history for the graph inputs.

---

## File Structure

```
chatbot/
├── __init__.py
├── state.py              # TypedDict state schema
├── graph.py              # StateGraph, nodes, edges, checkpointer, planner skip gate
├── llm_registry.py       # Singleton LLM cache — one ChatOpenAI per (model, temp, max_tokens)
├── streamlit_ui.py       # Streamlit tab, message history, snapshots
├── README.md             # This file
├── INSIGHTBOT_IMPLEMENTATION.md
│
├── nodes/
│   ├── __init__.py
│   ├── router.py         # Intent (gpt-4o-mini), context resolution, clarification detection
│   ├── clarification.py  # "Did you mean X or Y?" message
│   ├── analyzer.py       # Tool selection (gpt-4o), route_after_analyzer, correlation→heatmap
│   ├── planner.py        # Multi-step query breakdown (gpt-4o, complex queries only)
│   ├── insight.py        # Rule-based fast path → code gen (gpt-4o) → summarize (gpt-4o-mini)
│   ├── viz.py            # Chart config + data_visualization integration
│   ├── responder.py      # Format response, append message, append snapshot
│   └── suggestion_engine.py  # Follow-up suggestions (gpt-4o-mini + intent-aware fallbacks)
│
├── tools/
│   ├── __init__.py       # get_all_tools()
│   ├── data_tools.py     # insight_tool
│   ├── simple_charts.py  # bar, line, scatter, histogram, heatmap, correlation_matrix
│   └── complex_charts.py # combo, dashboard
│
├── execution/
│   ├── __init__.py
│   ├── code_generator.py    # LLM pandas code generation (gpt-4o via registry)
│   ├── code_validator.py    # Forbidden ops, result variable enforcement
│   ├── safe_executor.py     # Sandboxed execution, timeout, row limit
│   └── rule_based_executor.py  # Zero-LLM fast path for simple queries
│
├── prompts/
│   ├── __init__.py           # get_*_prompt() accessors
│   ├── base.py               # PromptTemplate, truncate_schema
│   ├── router_prompt.py
│   ├── analyzer_prompt.py
│   ├── planner_prompt.py
│   ├── code_generator_prompt.py
│   ├── summarizer_prompt.py
│   ├── responder_prompt.py
│   ├── suggestion_prompt.py
│   ├── small_talk_prompt.py
│   └── context_resolver_prompt.py
│
├── utils/
│   ├── __init__.py
│   ├── session_loader.py      # Redis load, prepare_state_dataframes, get_session_profile
│   ├── state_helpers.py       # get_current_query(state) — shared query resolution
│   ├── profile_formatter.py   # Format profile for prompts, chart validation
│   └── chart_selector.py      # Rule-based chart suggestion (not in main graph)
│
└── ui/
    ├── message_history.py     # Render per-turn snapshots (chart/table/code)
    ├── chat_input.py          # graph.stream() with progressive status UI
    └── chart_ui.py            # generate_chart_from_config_ui (Plotly from viz_config)
```

---

## How to Run and Test

1. **Environment:** Set `OPENAI_API_KEY`. Optionally override models via `MAIN_MODEL`, `MINI_MODEL`, etc. Ensure Redis and app backend are running if using session data.
2. **Run app:** `streamlit run app.py`; open the InsightBot tab. Upload data or use an existing session.
3. **Basic flow:** Ask a data question (e.g. "What's the average of X?"), then a chart request (e.g. "Bar chart of X by Y"), then a follow-up (e.g. "What about the maximum?"). Confirm responses and that previous charts remain visible.
4. **Streaming:** Confirm progressive status labels appear while nodes run, and the response renders before suggestion chips load.
5. **Planner skip:** Ask a simple query ("What is the average salary?") and confirm it routes analyzer → insight (no planner). Ask a complex query ("Show year-over-year revenue growth") and confirm the planner is invoked.
6. **Clarification:** Ask something that matches multiple columns (e.g. "show sales") where "sales" matches two columns; confirm "Did you mean …?" and that the next message uses the chosen column.
7. **Correlation:** Ask "show correlation" or "correlation between Price and Weight"; confirm numeric-only behavior.
8. **Rule-based fast path:** Ask "What is the average Price?" — confirm `Rule-based execution hit` in logs (no code generator LLM call).
9. **Suggestions:** Confirm three suggestion chips always appear, even if the LLM fails (intent-based fallbacks kick in).

---

## Limitations and Troubleshooting

- **Windows:** Signal-based timeout in the executor may not work; fallback is try/except without signal.
- **Single chart per response:** One chart per turn; multiple charts in one reply is not implemented.
- **Session not found:** Session expired or missing in Redis; re-upload or re-select data.
- **OpenAI errors:** Check `OPENAI_API_KEY` and quota. `MAIN_MODEL` defaults to `gpt-4o`; `MINI_MODEL` defaults to `gpt-4o-mini`.
- **State field missing:** New state fields must be initialized in the inputs passed from `streamlit_ui.py` when invoking the graph (and in any reducer if applicable).
- **Streaming + checkpointer:** The `MemorySaver` checkpointer is compatible with `graph.stream()`. Each yielded snapshot reflects the full state after the completed node.

For more test scenarios and migration notes, see `TESTING.md` and `MIGRATION.md` (if present). For implementation history and checklist, see `INSIGHTBOT_IMPLEMENTATION.md`.



## InsightBot Architecture

InsightBot is a **LangGraph-powered conversational analytics chatbot** built as a `StateGraph`. It's designed to understand natural language queries about your data, run pandas analysis, render charts, and maintain multi-turn conversation memory.

---

### Core Files

| File | Role |
|---|---|
| `state.py` | TypedDict defining the full graph state |
| `graph.py` | StateGraph wiring — nodes, edges, routing logic |
| `llm_registry.py` | Singleton LLM cache (one `ChatOpenAI` per config tuple) |
| `streamlit_ui.py` | Streamlit UI, message history, per-turn snapshots |
| `nodes/` | 8 logical processing nodes |
| `prompts/` | Modular, versioned prompt files per node |
| `utils/session_loader.py` | Loads DataFrames from Redis by `session_id` |

---

### The LangGraph Flow

```
User Query
    ↓
[Router] → intent + context resolution
    ↓
 ┌──────────────────────────────────┐
 │  needs_clarification?            │ → [Clarification] → END
 │  small_talk?                     │ → [Responder]
 │  summarize_last?                 │ → [Insight]
 │  data_query / viz / report?      │ → [Analyzer]
 └──────────────────────────────────┘
    ↓
[Analyzer] → tool selection via LLM function calling
    ↓
 complex query (~20%)? → [Planner] → [Insight]
 simple query (~80%)?  →            [Insight]  (planner skipped, saves ~2s)
    ↓
[Insight] → rule-based OR LLM code gen + execution + summarization
    ↓
 viz tool selected? → [Viz] → Plotly chart or fallback table
    ↓
[Responder] → formats final message + appends response_snapshot
    ↓
[Suggestion] → 3 follow-up chips (gpt-4o-mini)
    ↓
[MemorySaver checkpoint] → stream to UI
```

---

### The 8 Nodes

**Router** (`router.py`) — uses `gpt-4o-mini` to classify intent (`data_query`, `visualization_request`, `small_talk`, `report`, `summarize_last`), resolve follow-ups like "What about the max?" into full questions, and detect column ambiguity.

**Clarification** (`clarification.py`) — fires when multiple columns match a vague term (e.g. "sales"). Asks "Did you mean X or Y?" and terminates the turn. The next turn resolves the choice.

**Analyzer** (`analyzer.py`) — uses `gpt-4o` with LangChain tool binding. The LLM decides which tools to call (`insight_tool`, `bar_chart`, `line_chart`, `scatter_chart`, `histogram`, `heatmap_chart`, etc.) based on schema + intent.

**Planner** (`planner.py`) — uses `gpt-4o` for genuinely complex multi-step queries (YoY, cohort, rolling average, trend). ~80% of queries skip this node entirely via keyword + sub-intent gate in `graph.py`.

**Insight** (`insight.py`) — the execution engine. Dispatches to either a rule-based executor (mean/sum/count/min/max — zero LLM calls) or LLM code generation (generates pandas code, runs it in a sandbox with timeout and error handling), then summarizes the result with `gpt-4o-mini`.

**Viz** (`viz.py`) — validates chart config, loads data from Redis, builds a Plotly figure via the shared `data_visualization` module. Falls back to a table if the chart fails (e.g. too many categories).

**Responder** (`responder.py`) — formats the final `AIMessage` combining insight text + chart/table + optional "see code" expander. Appends a `response_snapshot` to state so previous turns' visualizations don't disappear.

**Suggestion** (`suggestion_engine.py`) — uses `gpt-4o-mini` to generate 3 contextual follow-up question chips. Has intent-aware pre-defined fallbacks in case LLM fails.

---

### State Schema (key fields)

The `State` TypedDict is what flows through every node:

- **Session:** `session_id`, `messages` (with LangGraph `add_messages` reducer)
- **Data context:** `schema`, `table_names`, `data_profile`, `operation_history`
- **Routing:** `intent`, `sub_intent`, `implicit_viz_hint`, `needs_clarification`
- **Clarification:** `clarification_options`, `clarification_mention`, `clarification_original_query`
- **Query processing:** `effective_query`, `entities`, `tool_calls`, `plan`, `conversation_context`
- **Results:** `last_insight`, `insight_data`, `viz_config`, `response_snapshots`

> Note: DataFrames are **never stored in state** (not serializable). They're loaded fresh from Redis per turn via `session_loader.py`.

---

### LLM Strategy

| Node | Model | Reason |
|---|---|---|
| Router, Summarizer, Suggestions | `gpt-4o-mini` | Classification/summarization — fast & cheap |
| Analyzer, Planner, Code Generator | `gpt-4o` | Schema reasoning requires stronger model |

The **LLM Registry** (`llm_registry.py`) ensures only one `ChatOpenAI` instance per `(model, temperature, max_tokens)` tuple is ever created, saving ~1.4s/query from repeated object instantiation.

---

### Prompt System

Each node has its own prompt file under `chatbot/prompts/`:

`router_prompt.py`, `analyzer_prompt.py`, `code_generator_prompt.py`, `summarizer_prompt.py`, `suggestion_prompt.py`, `small_talk_prompt.py`, `context_resolver_prompt.py`, `responder_prompt.py`

Each has a `VERSION` constant and uses `base.py`'s `PromptTemplate` with safe substitution and automatic schema truncation (max 5 tables, 20 columns each) to avoid token bloat.

---

### Latency Targets

| Query type | Wall clock | Perceived (streaming) |
|---|---|---|
| Simple stat (avg/sum/count) | ~4s | ~1s |
| Comparison / groupby | ~6s | ~2s |
| Visualization | ~5s | ~1.5s |
| Follow-up | ~7s | ~2s |
| Complex (YoY, cohort) | ~10s | ~3s |
| Small talk | ~1s | ~0.5s |

The UI uses `graph.stream(stream_mode='values')` to show progressive status captions and render the response as soon as the responder node completes — before the suggestion node even finishes.


