# Multi-Step Reasoning Planner Implementation

## Overview

Added a **Planner Node** to InsightBot that breaks down complex queries into sequential steps before code generation. This dramatically improves reliability for multi-step analytics queries.

## Architecture Change

### Before
```
User → Router → Analyzer → Insight (one-shot code gen) → Viz → Responder
```

### After
```
User → Router → Analyzer → Planner → Insight (executes plan) → Viz → Responder
```

## Implementation Details

### 1. Planner Node (`nodes/planner.py`)

**Responsibilities:**
- Detects query complexity using heuristics
- Breaks down complex queries into sequential steps
- Creates plan structure with step descriptions and code
- For simple queries, returns single-step plan

**Complexity Detection:**
- Keywords: "then", "after", "and show", "yoy", "growth", "top N", etc.
- Multiple operations in entities
- Complex sub-intents (compare, trend, correlate) with multiple parts

**Plan Structure:**
```python
[
    {
        "step": 1,
        "description": "Aggregate sales by year and region",
        "code": "step1_result = df.groupby(['Year', 'Region'])['Sales'].sum().reset_index()",
        "output_var": "step1_result"
    },
    {
        "step": 2,
        "description": "Calculate YoY growth",
        "code": "step2_result = step1_result.sort_values(['Region', 'Year']).groupby('Region')['Sales'].pct_change() * 100",
        "output_var": "step2_result"
    },
    ...
]
```

### 2. State Schema Updates

Added to `state.py`:
- `plan: Optional[List[Dict[str, Any]]]` - Multi-step plan
- `needs_planning: Optional[bool]` - Complexity flag

### 3. Graph Integration

**Updated `graph.py`:**
- Added `planner` node
- Analyzer routes to planner when `insight_tool` is selected
- Planner always routes to insight (plan is used there)
- Simple queries still work (planner returns single-step plan)

### 4. Insight Node Updates

**Updated `nodes/insight.py`:**
- Checks for `plan` in state
- If plan exists: combines all step codes into unified code block, executes sequentially
- If no plan: uses existing code_generator path (backward compatible)
- Ensures final step stores result in `result` variable

**Plan Execution:**
- All steps combined into one code block
- Later steps can reference earlier step variables (e.g., `step1_result`)
- Final step result stored in `result` for executor

### 5. Planner Prompt (`prompts/planner_prompt.py`)

**Features:**
- Guides LLM to break down complex queries
- Provides examples of multi-step plans
- Ensures step chaining (later steps use previous step results)
- For simple queries, returns single-step plan

## Benefits

### 1. Reliability
- **Before**: Complex queries like "Compare sales growth YoY and show top 3 declining regions" often failed with one-shot code generation
- **After**: Planner breaks into steps: aggregate → calculate growth → filter → sort → top N

### 2. Transparency
- Each step has a description
- Users can see the reasoning process in "Show code"
- Easier to debug when steps fail

### 3. Maintainability
- Plan structure is clear and testable
- Can validate each step independently
- Easier to optimize specific steps

### 4. Extensibility
- Can add step-level error recovery
- Can parallelize independent steps (future)
- Can cache intermediate results (future)

## Example Queries That Benefit

1. **"Compare sales growth YoY and show the top 3 declining regions"**
   - Step 1: Aggregate by year and region
   - Step 2: Calculate YoY growth
   - Step 3: Filter negative growth, sort, top 3

2. **"Show average Price by Company, then filter to companies with average > 1000"**
   - Step 1: Calculate average by Company
   - Step 2: Filter to averages > 1000

3. **"List all laptops with Price > 5000, sort by Weight, show top 10"**
   - Step 1: Filter Price > 5000
   - Step 2: Sort by Weight
   - Step 3: Take top 10

## Backward Compatibility

- Simple queries still work (planner returns single-step plan)
- Existing code generation path remains for queries without plan
- No breaking changes to other nodes

## Future Enhancements

1. **Step-level error recovery**: Retry individual steps on failure
2. **Parallel execution**: Execute independent steps simultaneously
3. **Plan validation**: Pre-validate plan before execution
4. **Plan optimization**: Merge or reorder steps for efficiency
5. **Intermediate result caching**: Cache step results for reuse

## Files Changed

- `state.py` - Added `plan` and `needs_planning` fields
- `nodes/planner.py` - NEW: Planner node implementation
- `nodes/insight.py` - Updated to use plan if available
- `graph.py` - Added planner node and routing
- `prompts/planner_prompt.py` - NEW: Planner prompt
- `prompts/__init__.py` - Export `get_planner_prompt`
- `nodes/__init__.py` - Export `planner_node`
- `README.md` - Updated flow diagram and node descriptions
