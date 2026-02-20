# Prompt Management System

Modular, versioned prompt architecture for InsightBot.

## Architecture

### Separation by Responsibility

Each prompt is in its own file:
- `router_prompt.py` - Intent classification
- `context_resolver_prompt.py` - Follow-up resolution
- `analyzer_prompt.py` - Tool selection
- `code_generator_prompt.py` - Pandas code generation
- `summarizer_prompt.py` - Insight summarization
- `suggestion_prompt.py` - Follow-up suggestions
- `small_talk_prompt.py` - Casual conversation
- `responder_prompt.py` - Response formatting (reference only)

### Base Utilities

`base.py` provides:
- `PromptTemplate` - Versioned template class with safe substitution
- `truncate_schema()` - Prevents prompt bloat by limiting schema size

## Usage

### Import and Use

```python
from chatbot.prompts import get_router_prompt, get_analyzer_prompt

# Router
prompt = get_router_prompt(
    schema=schema,
    operation_history=history,
    conversation_context=context
)

# Analyzer
prompt = get_analyzer_prompt(
    schema=schema,
    intent="data_query",
    sub_intent="compare",
    entities={"columns": ["Price"]},
    implicit_viz_hint=False,
    data_profile_summary="Price: numeric, 100 unique"
)
```

### Versioning

Each prompt file has a `VERSION` constant. Update when making breaking changes:

```python
VERSION = "1.1.0"  # Increment on changes
```

### Schema Truncation

Large schemas are automatically truncated to prevent prompt bloat:
- Max 5 tables (configurable)
- Max 20 columns per table (configurable)
- Truncation markers added: `_truncated` and `_truncated_tables`

## Benefits

1. **Modularity** - Each prompt is independent and testable
2. **Versioning** - Track prompt changes over time
3. **Maintainability** - Easy to find and update specific prompts
4. **Guardrails** - Schema truncation prevents token limits
5. **Type Safety** - Function signatures document required parameters
6. **Separation** - No monolithic file with all prompts

## Migration from Old System

The old `PROMPTS` dict is still available for backward compatibility:

```python
from chatbot.prompts import PROMPTS  # Deprecated
```

New code should use the modular functions:

```python
from chatbot.prompts import get_router_prompt  # Preferred
```

## Testing

Each prompt can be tested independently:

```python
from chatbot.prompts.router_prompt import get_router_prompt

prompt = get_router_prompt(
    schema={"tables": {"main": {"columns": ["Price", "Weight"]}}},
    operation_history=[],
    conversation_context="None"
)
assert "query intent classifier" in prompt.lower()
```
