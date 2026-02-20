# Code Execution Guardrails

## Overview

Strong guardrails ensure safe, reliable, and performant code execution in InsightBot.

## Implemented Guardrails

### 1. Code Validation (`code_validator.py`)

**Forbidden Operations:**
- `.plot()` - Plotting operations (use visualization tools instead)
- File writes: `.to_csv()`, `.to_excel()`, `.to_json()`, `.to_parquet()`
- File operations: `open()`
- Dynamic imports: `__import__`
- Unsafe execution: `eval()`, `exec()`
- System operations: `subprocess`, `os.*`, `sys.*`

**Result Variable Enforcement:**
- Code must assign final result to `result` variable
- Auto-fixes simple cases (wraps last expression)
- Validates before execution

### 2. Row Limit Enforcement

**Maximum Rows:** 100,000 rows per result

- DataFrames and Series are truncated if they exceed the limit
- Warning logged when truncation occurs
- User receives notification: "Result truncated to 100,000 rows (original: X rows)"

**Implementation:**
```python
if len(result) > MAX_RESULT_ROWS:
    result = result.head(MAX_RESULT_ROWS)
```

### 3. Execution Time Profiling

**Metrics:**
- Total execution time (including validation)
- Code execution time (excluding validation)
- Reported in milliseconds

**Usage:**
- Logged for monitoring
- Included in execution result: `execution_time_ms`
- Helps identify slow queries

### 4. Rule-Based Fallback (`rule_based_executor.py`)

**Purpose:** Avoid LLM calls for simple queries

**Supported Operations:**
- `mean` / `average` / `avg` - Column mean
- `sum` - Column sum
- `count` - Row count
- `max` / `maximum` / `highest` - Column maximum
- `min` / `minimum` / `lowest` - Column minimum

**Detection:**
- Pattern matching on query text
- Column name extraction
- Direct pandas operation execution

**Benefits:**
- Faster response (no LLM latency)
- Lower cost (no API calls)
- More reliable (deterministic)

**Example:**
```
Query: "What's the average Price?"
→ Rule-based: df['Price'].mean()
→ No LLM call needed
```

### 5. Result Variable Standardization

**Enforcement:**
- Code generator prompt explicitly requires `result` variable
- Code validator ensures assignment exists
- Executor expects `result` in locals after execution

**Benefits:**
- Consistent execution interface
- Easier debugging
- Predictable behavior

## Execution Flow

```
Query
  ↓
Try Rule-Based Execution (if simple)
  ↓ (if fails)
Generate Code (LLM)
  ↓
Validate Code (block forbidden ops)
  ↓
Sanitize Code (ensure result variable)
  ↓
Execute Code (with timeout)
  ↓
Enforce Row Limit
  ↓
Return Result (with timing)
```

## Error Handling

### Validation Errors
- **Type:** `validation_error`
- **Message:** Specific forbidden operation detected
- **Action:** Code not executed

### Timeout Errors
- **Type:** `timeout`
- **Message:** "Execution timed out (>X seconds)"
- **Default Timeout:** 10 seconds

### Row Limit Warnings
- **Type:** Warning (not error)
- **Message:** Truncation notification
- **Action:** Result truncated, execution continues

## Configuration

### Constants

```python
# Maximum rows in result
MAX_RESULT_ROWS = 100_000

# Execution timeout (seconds)
DEFAULT_TIMEOUT = 10
```

### Customization

To adjust limits, modify:
- `safe_executor.py`: `MAX_RESULT_ROWS`, `timeout` parameter
- `code_validator.py`: `FORBIDDEN_PATTERNS` list

## Performance Impact

### Rule-Based Execution
- **Latency:** ~1-5ms (vs 500-2000ms for LLM)
- **Cost:** $0 (vs $0.01-0.05 per query)
- **Reliability:** 100% (deterministic)

### Code Validation
- **Overhead:** ~1-2ms per execution
- **Benefit:** Prevents dangerous operations

### Row Limit Enforcement
- **Overhead:** ~1-5ms for large DataFrames
- **Benefit:** Prevents memory issues

## Future Enhancements

1. **Parallel Step Execution:** Execute independent plan steps simultaneously
2. **Result Caching:** Cache rule-based results for repeated queries
3. **Adaptive Timeouts:** Adjust timeout based on query complexity
4. **Memory Profiling:** Track memory usage during execution
5. **Query Complexity Scoring:** Route queries based on complexity

## Files

- `code_validator.py` - Code validation and sanitization
- `rule_based_executor.py` - Rule-based query execution
- `safe_executor.py` - Safe code execution with guardrails
- `code_generator.py` - LLM-based code generation
