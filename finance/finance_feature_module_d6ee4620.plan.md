---
name: Finance Feature Module
overview: Add a root-level finance module with a Trading Performance Analyzer tool, wire it into the existing tool registry and analyzer prompt so the LLM can select it, and route its execution through the existing insight pipeline.
todos: []
---

# Finance Feature Module Plan

## Approach

- Create a new root module at [`/Users/shivanshmahajan/Developer/Data-Assistant/finance/`](/Users/shivanshmahajan/Developer/Data-Assistant/finance/) to hold the finance feature implementation and documentation.
- Implement a `@tool`-decorated `trading_performance_analyzer()` that mirrors the existing tool contract (returns a dict with `tool` + `query`) so it can be executed by the existing insight pipeline.
- Register the new tool in the tool registry and update the analyzer prompt so the LLM knows when to select it for P&L, win rate, Sharpe, and strategy performance questions.
- Route the new tool through the insight node alongside `insight_tool`, so its queries are executed by the pandas code generator.

## Key Files to Touch

- Add new module files: [`/Users/shivanshmahajan/Developer/Data-Assistant/finance/__init__.py`](/Users/shivanshmahajan/Developer/Data-Assistant/finance/__init__.py), [`/Users/shivanshmahajan/Developer/Data-Assistant/finance/performance_analyzer.py`](/Users/shivanshmahajan/Developer/Data-Assistant/finance/performance_analyzer.py)
- Tool registry: [`/Users/shivanshmahajan/Developer/Data-Assistant/chatbot/tools/__init__.py`](/Users/shivanshmahajan/Developer/Data-Assistant/chatbot/tools/__init__.py)
- Tool selection prompt: [`/Users/shivanshmahajan/Developer/Data-Assistant/chatbot/prompts/system_prompts.py`](/Users/shivanshmahajan/Developer/Data-Assistant/chatbot/prompts/system_prompts.py)
- Insight routing/execution: [`/Users/shivanshmahajan/Developer/Data-Assistant/chatbot/nodes/analyzer.py`](/Users/shivanshmahajan/Developer/Data-Assistant/chatbot/nodes/analyzer.py), [`/Users/shivanshmahajan/Developer/Data-Assistant/chatbot/nodes/insight.py`](/Users/shivanshmahajan/Developer/Data-Assistant/chatbot/nodes/insight.py)

## Notes on Integration

- The new tool should follow the existing tool signature pattern used today:
```
6:25:/Users/shivanshmahajan/Developer/Data-Assistant/chatbot/tools/data_tools.py
@tool
def insight_tool(query: str) -> dict:
    # This is a placeholder - actual execution happens in insight_node
    return {"tool": "insight_tool", "query": query}
```

- In `route_after_analyzer`, treat `trading_performance_analyzer` like `insight_tool` so it routes to the insight node.
- In the analyzer prompt, add a section describing when to use `trading_performance_analyzer` vs the generic `insight_tool` (finance-specific performance questions).

## Documentation

- Add [`/Users/shivanshmahajan/Developer/Data-Assistant/finance/README.md`](/Users/shivanshmahajan/Developer/Data-Assistant/finance/README.md) to host the finance feature notes (either migrate or summarize `finance.md`).

## Todos

- create-finance-module: Create `/finance/` package and performance analyzer tool file
- register-tool: Wire the new tool into `get_all_tools()` and analyzer prompt
- route-execution: Update analyzer/insight routing so the tool executes via insight node
- add-docs: Add `/finance/README.md` with performance analyzer details