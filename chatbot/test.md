# InsightBot Test Scenarios — Laptop Dataset (`test.csv`)

**Dataset columns:**  
`Company`, `TypeName`, `Ram`, `Weight`, `Price`, `TouchScreen`, `Ips`, `Ppi`, `Cpu_brand`, `HDD`, `SSD`, `Gpu_brand`, `Os`

**Verification status (chatbot):**  
Sections **1** (Statistical / Data Query) and **2.1–2.6** (Visualization through Combined Insight + Viz) have been **verified** for InsightBot.

**Key facts about this data:**
- Companies: Apple, HP, Dell, Asus, Acer, Lenovo, Chuwi, and others
- TypeNames: Ultrabook, Notebook, Gaming, 2 in 1 Convertible, Netbook
- Price is log-scaled (range ~9.2 – 11.9)
- Ram: 2, 4, 8, 12, 16 GB
- Os: Mac, Windows, Others
- TouchScreen/Ips: binary (0/1)
- Gpu_brand: Intel, AMD, Nvidia
- Cpu_brand: Intel Core i3/i5/i7, AMD Processor, Other Intel Processor

---

## 1. Statistical / Data Query Tests ✅ Verified

### 1.1 Basic Aggregations

| # | Query | Expected Intent | Expected Code Pattern | Expected Output |
|---|-------|-----------------|-----------------------|-----------------|
| S1 | `What is the average Price?` | data_query | `df['Price'].mean()` | Single float ~10.6–10.8 |
| S2 | `What is the maximum Price?` | data_query | `df['Price'].max()` | Single float ~11.9 |
| S3 | `What is the minimum Weight?` | data_query | `df['Weight'].min()` | Single float ~0.92 |
| S4 | `How many laptops are in the dataset?` | data_query | `len(df)` | Integer count |
| S5 | `What is the total SSD storage across all laptops?` | data_query | `df['SSD'].sum()` | Integer |
| S6 | `What is the average Ram?` | data_query | `df['Ram'].mean()` | Float |
| S7 | `What is the median Ppi?` | data_query | `df['Ppi'].median()` | Float |
| S8 | `What is the standard deviation of Price?` | data_query | `df['Price'].std()` | Float |

**Pass criteria:** Rule-based executor should handle S1–S4 without LLM. All return a single value, not a DataFrame.

---

### 1.2 Group-By & Aggregations

| # | Query | Expected Intent | Expected Code Pattern | Expected Output |
|---|-------|-----------------|-----------------------|-----------------|
| G1 | `What is the average Price by Company?` | data_query | `df.groupby('Company')['Price'].mean()` | Series/DataFrame with Company index |
| G2 | `Show the total SSD storage by TypeName` | data_query | `df.groupby('TypeName')['SSD'].sum()` | Series |
| G3 | `What is the average Weight for each Os?` | data_query | `df.groupby('Os')['Weight'].mean()` | Series |
| G4 | `Count the number of laptops by Gpu_brand` | data_query | `df.groupby('Gpu_brand').size()` or `.count()` | Series |
| G5 | `Average Ram by Cpu_brand` | data_query | `df.groupby('Cpu_brand')['Ram'].mean()` | Series |
| G6 | `What is the average Price for each TypeName?` | data_query | `df.groupby('TypeName')['Price'].mean()` | Series/DataFrame |
| G7 | `How many laptops does each company make?` | data_query | `df.groupby('Company').size()` | Series |
| G8 | `Average Ppi by Company` | data_query | `df.groupby('Company')['Ppi'].mean()` | Series |

**Pass criteria:** Returns a multi-row result (DataFrame or Series), not a single value.

---

### 1.3 Filtering & Listing

| # | Query | Expected Intent | Expected Code Pattern | Expected Output |
|---|-------|-----------------|-----------------------|-----------------|
| F1 | `List all Apple laptops` | data_query | `df[df['Company'] == 'Apple']` | Filtered DataFrame |
| F2 | `Show laptops with Ram = 16` | data_query | `df[df['Ram'] == 16]` | Filtered DataFrame |
| F3 | `Find laptops with TouchScreen = 1` | data_query | `df[df['TouchScreen'] == 1]` | Filtered DataFrame |
| F4 | `Show all Gaming laptops` | data_query | `df[df['TypeName'] == 'Gaming']` | Filtered DataFrame |
| F5 | `List laptops with Price above 11.5` | data_query | `df[df['Price'] > 11.5]` | Filtered DataFrame |
| F6 | `Find all Mac laptops` | data_query | `df[df['Os'] == 'Mac']` | Filtered DataFrame |
| F7 | `Show laptops with both HDD and SSD (HDD > 0 and SSD > 0)` | data_query | `df[(df['HDD'] > 0) & (df['SSD'] > 0)]` | Filtered DataFrame |
| F8 | `Find laptops with IPS display and TouchScreen` | data_query | `df[(df['Ips'] == 1) & (df['TouchScreen'] == 1)]` | Filtered DataFrame |
| F9 | `Show Dell or HP laptops` | data_query | `df[df['Company'].isin(['Dell','HP'])]` | Filtered DataFrame |
| F10 | `List cheap laptops (Price < 10)` | data_query | `df[df['Price'] < 10]` | Filtered DataFrame |

**Pass criteria:** Returns a DataFrame (tabular), not a scalar.

---

### 1.4 Top-N / Ranking

| # | Query | Expected Intent | Expected Code Pattern | Expected Output |
|---|-------|-----------------|-----------------------|-----------------|
| T1 | `Show the top 5 most expensive laptops` | data_query | `df.nlargest(5, 'Price')` | 5-row DataFrame |
| T2 | `Show the 10 lightest laptops` | data_query | `df.nsmallest(10, 'Weight')` | 10-row DataFrame |
| T3 | `Which company has the highest average Price?` | data_query | `df.groupby('Company')['Price'].mean().idxmax()` | Single string |
| T4 | `Show the top 3 laptops with highest Ppi` | data_query | `df.nlargest(3, 'Ppi')` | 3-row DataFrame |
| T5 | `Which TypeName has the lowest average Weight?` | data_query | `df.groupby('TypeName')['Weight'].mean().idxmin()` | Single string |

---

### 1.5 For-Each / Per-Group Best Row

| # | Query | Expected Intent | Expected Code Pattern | Expected Output |
|---|-------|-----------------|-----------------------|-----------------|
| E1 | `Show the most expensive laptop for each Company` | data_query | `df.loc[df.groupby('Company')['Price'].idxmax()]` | DataFrame (one row per company) |
| E2 | `Show the lightest laptop for each TypeName` | data_query | `df.loc[df.groupby('TypeName')['Weight'].idxmin()]` | DataFrame |
| E3 | `Show the laptop with highest Ppi for each Os` | data_query | `df.loc[df.groupby('Os')['Ppi'].idxmax()]` | DataFrame |
| E4 | `Show the cheapest laptop for each Cpu_brand` | data_query | `df.loc[df.groupby('Cpu_brand')['Price'].idxmin()]` | DataFrame |

**Pass criteria:** Returns one full row per group, NOT just the aggregated value.

---

### 1.6 Correlation Queries

| # | Query | Expected Intent | Expected Code Pattern | Gotcha |
|---|-------|-----------------|-----------------------|--------|
| C1 | `Show correlation between Price and Weight` | data_query | `df['Price'].corr(df['Weight'])` | Single float — do NOT use full df.corr() |
| C2 | `What is the correlation between Ram and Price?` | data_query | `df['Ram'].corr(df['Price'])` | Single float |
| C3 | `Show the correlation matrix` | data_query | `df.select_dtypes(include=['number']).corr()` | Full matrix; must exclude non-numeric |
| C4 | `What correlates with Price?` | data_query | `df.select_dtypes(include=['number']).corr()['Price']` | Series |
| C5 | `Correlation between Price and Company` | data_query | `df.groupby('Company')['Price'].agg(['mean','count']).reset_index()` | Company is categorical — must use groupby, NOT .corr() |
| C6 | `Correlation between Gpu_brand and Price` | data_query | `df.groupby('Gpu_brand')['Price'].agg(['mean','count']).reset_index()` | Same — categorical, use groupby |

**Pass criteria for C5/C6:** Must NOT call `.corr()` on a categorical column. Must use groupby aggregation instead.

---

## 2. Visualization Tests

### 2.1 Bar Charts ✅ Verified

| # | Query | Expected Tool | Expected Params | Validation |
|---|-------|---------------|-----------------|------------|
| V1 | `Show a bar chart of average Price by Company` | bar_chart | x_col=Company, y_col=Price, agg_func=mean | Company has ~10 unique values — should render fine |
| V2 | `Bar chart of laptop count by TypeName` | bar_chart | x_col=TypeName, agg_func=count | TypeName has 5 unique values — fine |
| V3 | `Compare average Weight by Os` | bar_chart | x_col=Os, y_col=Weight, agg_func=mean | Os has 3 unique values — fine |
| V4 | `Show breakdown of Gpu_brand distribution` | bar_chart | x_col=Gpu_brand, agg_func=count | 3 brands — fine |
| V5 | `Bar chart of average Ram by TypeName` | bar_chart | x_col=TypeName, y_col=Ram, agg_func=mean | 5 unique TypeNames |

---

### 2.2 Scatter Charts ✅ Verified

| # | Query | Expected Tool | Expected Params | Validation |
|---|-------|---------------|-----------------|------------|
| SC1 | `Scatter plot of Price vs Weight` | scatter_chart | x_col=Price, y_col=Weight | Both numeric |
| SC2 | `Show relationship between Ppi and Price` | scatter_chart | x_col=Ppi, y_col=Price | Both numeric |
| SC3 | `Plot Ram against Price` | scatter_chart | x_col=Ram, y_col=Price | Both numeric |

---

### 2.3 Histograms ✅ Verified

| # | Query | Expected Tool | Expected Params | Validation |
|---|-------|---------------|-----------------|------------|
| H1 | `Show distribution of Price` | histogram | column=Price | Numeric — valid |
| H2 | `Distribution of Weight` | histogram | column=Weight | Numeric — valid |
| H3 | `Histogram of Ppi` | histogram | column=Ppi | Numeric — valid |
| H4 | `Show distribution of Ram` | histogram | column=Ram | Numeric (few unique values — will render as histogram with sparse bins) |

---

### 2.4 Heatmap / Correlation Matrix ✅ Verified

| # | Query | Expected Tool | Expected Params | Validation |
|---|-------|---------------|-----------------|------------|
| HM1 | `Show correlation matrix` | correlation_matrix | auto (all numeric cols) | Must select only numeric columns |
| HM2 | `Heatmap of Price, Weight, Ram, Ppi` | heatmap_chart | heatmap_columns=[Price, Weight, Ram, Ppi] | All numeric |
| HM3 | `Show correlation between all numeric columns` | correlation_matrix | auto | Full matrix |

---

### 2.5 Box Charts ✅ Verified

| # | Query | Expected Tool | Expected Params | Validation |
|---|-------|---------------|-----------------|------------|
| BX1 | `Box plot of Price by Company` | box_chart | y_col=Price, x_col=Company | Price numeric — valid |
| BX2 | `Distribution of Weight by TypeName as box plot` | box_chart | y_col=Weight, x_col=TypeName | Weight numeric — valid |
| BX3 | `Show Price distribution by Os` | box_chart | y_col=Price, x_col=Os | Price numeric — valid |

---

### 2.6 Combined Insight + Visualization ✅ Verified

| # | Query | Expected Tools | Notes |
|---|-------|----------------|-------|
| CV1 | `Compare average Price by Company and show a chart` | insight_tool + bar_chart | Should produce both text and chart |
| CV2 | `Plot average Weight by TypeName` | insight_tool + bar_chart | "Plot" triggers viz; insight summarizes numbers |
| CV3 | `Show me a scatter of Price vs Weight and tell me the correlation` | insight_tool + scatter_chart | Dual output |
| CV4 | `Give me the top companies by average Price with a bar chart` | insight_tool + bar_chart | Groupby + chart |

---

### 2.7 Visualization Failure / Fallback Tests

| # | Query | Expected Behavior |
|---|-------|-------------------|
| VF1 | `Bar chart of Price by Ppi` (Ppi has 100+ unique values) | Should detect high cardinality (>25), set viz_error, fall back to table |
| VF2 | `Pie chart of Company` | If pie_chart were attempted, 10+ companies → too many slices (not directly exposed but similar logic) |
| VF3 | `Line chart of Price` (no x_col) | Should fail validation (missing x_col), skip chart, show insight only |
| VF4 | `Histogram of Company` | Company is categorical — should reject with error, show table instead |

---

## 3. Multi-Turn / Follow-Up Tests

These test context resolution and conversation memory across turns.

### 3.1 Follow-Up Resolution Chain

```
Turn 1: "What is the average Price by Company?"
Turn 2: "What about the maximum?"         ← should resolve to "maximum Price by Company"
Turn 3: "Now just for Apple"               ← should resolve to "maximum Price for Apple"
Turn 4: "And the minimum?"                 ← should resolve to "minimum Price for Apple"
```

**Expected:** Each follow-up correctly inherits prior context.

---

### 3.2 Implicit Follow-Up After Filtering

```
Turn 1: "Show me all Apple laptops"
Turn 2: "How many are there?"             ← should resolve to "How many Apple laptops are there?"
Turn 3: "What's the average Price of those?" ← should resolve to average Price of Apple laptops
```

---

### 3.3 Visualization Follow-Up

```
Turn 1: "Compare average Price by Company"
Turn 2: "Now show me that as a bar chart"  ← should add bar_chart to the same groupby result
Turn 3: "Can you do the same for Weight?"  ← should resolve to "Compare average Weight by Company with bar chart"
```

---

### 3.4 Summarize Previous Result

```
Turn 1: "Show the top 10 most expensive laptops"   ← returns DataFrame
Turn 2: "Summarize that"                            ← intent = summarize_last, re-summarizes prior result
Turn 3: "What does that show?"                     ← same as above
```

**Expected:** `summarize_last` intent is detected; no new code execution; LLM re-summarizes `last_insight`.

---

## 4. Clarification / Ambiguity Tests

These test the column disambiguation flow.

| # | Query | Ambiguous Term | Expected Behavior |
|---|-------|----------------|-------------------|
| AM1 | `Show me the average price` | "price" → matches `Price` (unique match — should NOT trigger clarification) | Direct execution |
| AM2 | If schema had `Price_USD` and `Price_INR`: `Show me price` | "price" → 2 matches | Should ask "Did you mean Price_USD or Price_INR?" |
| AM3 | `Show gpu performance` | "gpu" could match `Gpu_brand` | Partial match → clarification if 2+ columns match |

**For test.csv specifically:** The schema has clean unique column names, so most queries should NOT trigger clarification. Test that false positives don't appear.

---

## 5. Edge Cases & Error Handling

### 5.1 Column Not Found (Did You Mean?)

| # | Query | Typo | Expected Behavior |
|---|-------|------|-------------------|
| ER1 | `What is the average Prise?` | "Prise" → not found | Should suggest "Price" via `get_close_matches` |
| ER2 | `Show laptops with Companyy = Apple` | "Companyy" → not found | Should suggest "Company" |
| ER3 | `Average Weigth by TypeName` | "Weigth" → not found | Should suggest "Weight" |
| ER4 | `Show Ram8 laptops` | "Ram8" → not found | Should suggest "Ram" |

**Expected response:** `"Column 'Prise' not found. Did you mean: Price?"` — uses `error_suggestion.type = "did_you_mean"`.

---

### 5.2 Invalid Operations

| # | Query | Expected Behavior |
|---|-------|-------------------|
| EV1 | `Correlation between Company and TypeName` | Both categorical — should use groupby or count, not .corr() |
| EV2 | `Sum of Company names` | Company is text — should return an error or sensible fallback |
| EV3 | `Average of Os` | Os is text — should fail gracefully with "Os is not numeric" |

---

### 5.3 Execution Safety (Guardrail Tests)

These verify that `code_validator.py` blocks forbidden operations:

| # | Scenario | Expected Behavior |
|---|----------|-------------------|
| GR1 | LLM-generated code contains `df.to_csv('output.csv')` | Code validator blocks it — validation_error returned |
| GR2 | LLM-generated code contains `df.plot()` | Code validator blocks it |
| GR3 | LLM-generated code contains `eval(...)` | Code validator blocks it |
| GR4 | Code produces > 100,000 rows | Row limit enforcement truncates result; user sees warning message |
| GR5 | Code runs infinite loop or very slow operation | Thread-based timeout triggers after 10s |

---

### 5.4 Empty / Degenerate Queries

| # | Query | Expected Behavior |
|---|-------|-------------------|
| EQ1 | ` ` (blank) | Chat input not submitted |
| EQ2 | `hello` | Small talk intent, no tool calls, friendly response |
| EQ3 | `thanks` | Small talk, brief acknowledgment |
| EQ4 | `what can you do?` | Small talk or exploratory — overview response |
| EQ5 | `summarize` (no prior data) | summarize_last with no prior result → "No previous result to summarize" |

---

## 6. Intent Classification Tests

These validate the router node's structured output.

| # | Query | Expected `intent` | Expected `sub_intent` | Expected `is_follow_up` |
|---|-------|-------------------|-----------------------|------------------------|
| IC1 | `What is the average Price?` | data_query | general | false |
| IC2 | `Plot Price vs Weight` | visualization_request | correlate | false |
| IC3 | `Show a bar chart of companies` | visualization_request | segment | false |
| IC4 | `Hello!` | small_talk | general | false |
| IC5 | `Give me a report on laptop prices` | report | general | false |
| IC6 | `Summarize that` | summarize_last | general | true |
| IC7 | `What about the minimum?` | data_query | general | true |
| IC8 | `Compare average Weight by Os` | data_query | compare | false |
| IC9 | `How has Price trended by TypeName?` | data_query | trend | false |
| IC10 | `Show distribution of Price` | visualization_request | distribution | false |
| IC11 | `How are we doing?` | data_query | general | false (but `implicit_viz_hint=true`) |
| IC12 | `Give me an overview of the data` | data_query | general | false (but `implicit_viz_hint=true`) |

---

## 7. Planner / Multi-Step Query Tests

These test the planner node for complex queries that require sequential steps.

| # | Query | Expected Steps | Notes |
|---|-------|----------------|-------|
| P1 | `Show average Price by Company, then filter to companies with average > 11.0` | Step 1: groupby mean; Step 2: filter | Two sequential steps; step2 uses step1_result |
| P2 | `Show the top 5 most expensive Apple laptops sorted by Weight` | Step 1: filter Apple; Step 2: sort by Price; Step 3: top 5 | Three steps |
| P3 | `Compare average Price by TypeName then show only types with average > 10.5 as a bar chart` | Step 1: groupby; Step 2: filter; + bar_chart | Mixed insight + viz |
| P4 | `What is the average Price?` | Step 1: mean only | Simple query — single step |
| P5 | `List Nvidia laptops with SSD > 256 sorted by Price` | Step 1: filter Nvidia + SSD>256; Step 2: sort | Two steps |

**Complexity detection keywords in these queries:** "then", "filter to", "sorted by" — planner should detect `needs_planning=True` for P1/P2/P3/P5.

---

## 8. Tone / Response Style Tests

These validate the `_apply_tone` logic in `responder.py`.

| # | Tone | Query | Expected Behavior |
|---|------|-------|-------------------|
| TO1 | `explorer` | `Average Price by Company` | Response ends with a follow-up suggestion ("Want to dig into a specific segment?") |
| TO2 | `technical` | `Average Price by Company` | Response mentions code expander ("You can see how this was computed...") |
| TO3 | `executive` | Long insight with 5+ sentences | Response truncated to ≤2 sentences |

---

## 9. Suggestion Engine Tests

After each successful response, the suggestion engine should emit 3 follow-up questions.

| # | Prior Query | Expected Suggestions (approximately) |
|---|-------------|--------------------------------------|
| SG1 | `Average Price by Company` | e.g. "Break down by TypeName", "Which company has the highest Price?", "Compare Weight by Company" |
| SG2 | `Show top 10 expensive laptops` | e.g. "Filter by OS", "Show only Gaming laptops", "Compare these by Company" |
| SG3 | `Distribution of Price` | e.g. "Compare by TypeName", "Show top 10 by Price", "Average Price by Cpu_brand" |

**Pass criteria:** Exactly 3 suggestions returned; each is a complete question; no numbering or bullets in raw text.

---

## 10. Quick-Action Tests (Sidebar Buttons)

| # | Button | Expected Query Submitted | Expected Result |
|---|--------|--------------------------|-----------------|
| QA1 | 📊 Summary stats | "Show summary statistics for the main table" | Returns `df.describe()` or similar |
| QA2 | 📈 Trend | "Plot the trend over time for the main metric" | May fail if no datetime column — should handle gracefully |
| QA3 | 🔍 Top 10 | "Show the top 10 rows by the primary numeric column" | Returns 10-row DataFrame |
| QA4 | 🎯 Correlation | "Show correlation between the two most important numeric columns" | Scatter or correlation value |

---

## 11. Full End-to-End Scenarios

These are realistic conversation flows to run as integration tests.

### Scenario A: Laptop Price Explorer
```
1. "What is the average Price?"                          → S1 (scalar)
2. "Break that down by Company"                         → G1 (groupby)
3. "Show it as a bar chart"                             → V1 (bar chart added)
4. "Which company is most expensive?"                   → T3 (idxmax)
5. "Show me all their laptops"                          → F1 filtered to that company
6. "Summarize what you found"                           → summarize_last
```

### Scenario B: Gaming Laptop Analysis
```
1. "Show all Gaming laptops"                            → F4 (filtered DataFrame)
2. "How many are there?"                                → follow-up (count)
3. "What's the average Price?"                          → follow-up (mean of filtered Gaming)
4. "Which Gpu_brand is most common in Gaming laptops?"  → groupby count on filtered set
5. "Plot that as a bar chart"                           → bar_chart
```

### Scenario C: Correlation Deep Dive
```
1. "Show the correlation matrix"                        → HM1 (correlation_matrix tool)
2. "What's the correlation between Price and Weight?"   → C1 (single float)
3. "Does Ram affect Price?"                             → C2 (correlation or groupby)
4. "Show me a scatter plot of Price vs Weight"          → SC1
5. "Color it by Os"                                     → follow-up adding color_col=Os
```

### Scenario D: OS Comparison Report
```
1. "Compare average Price by Os"                        → G3 variant
2. "Which Os has the highest average Price?"            → idxmax on above
3. "Show Mac laptops only"                              → F6 filter
4. "What TypeNames are available for Mac?"              → groupby or unique on filtered
5. "Give me a report on Mac laptop specs"               → report intent
```

---

## 12. Regression Tests (Previously Fixed Bugs)

| # | Issue | Test Query | Verify |
|---|-------|------------|--------|
| RG1 | `df.corr()` called on non-numeric columns | `Show correlation` | Verifies `select_dtypes(include=['number'])` used |
| RG2 | `GroupBy.corr()` called with no args | `Correlation between Price and Company` | Verifies groupby+agg used, not `.corr()` |
| RG3 | Responder fallback used `PROMPTS["responder"]` (NameError) | Any query that hits `format_fallback_response` | Verifies `get_responder_prompt()` is called instead |
| RG4 | Viz shown even when validation fails | `Bar chart of Price vs Ppi` (high cardinality) | Verifies viz_error is set and chart is NOT rendered |
| RG5 | Generated code missing `result = ` variable | Complex multi-step code | Verifies `ensure_result_variable()` auto-fixes or code validator catches it |

---

## 13. Performance Benchmarks

| Scenario | Target Latency | Acceptable | Concerning |
|----------|---------------|------------|------------|
| Rule-based simple query (S1–S4) | < 100ms | < 500ms | > 1s |
| LLM code-gen + execution (G1–G8) | 3–5s | < 8s | > 12s |
| Combined insight + viz (CV1–CV4) | 6–10s | < 15s | > 20s |
| Follow-up with context resolution | 4–7s | < 10s | > 15s |
| Planner + multi-step (P1–P5) | 8–12s | < 18s | > 25s |
| Suggestion generation | < 3s | < 6s | > 10s |

---

## 14. How to Run These Tests

### Manual Testing Checklist

1. Upload `test.csv` via the **Upload** tab — note the session ID.
2. Navigate to **💬 InsightBot** tab.
3. For each test, paste the query and verify:
   - **Intent** matches expected (visible in debug/Langfuse trace)
   - **Output type** is correct (scalar vs DataFrame)
   - **Chart** renders (or correctly falls back)
   - **Suggestions** appear after response
   - **Code expander** shows valid pandas code

### Automated Test Skeleton (pytest)

```python
# tests/test_insightbot.py
import pytest
from langchain_core.messages import HumanMessage
from chatbot.graph import graph
from chatbot.nodes.router import router_node
from chatbot.execution.rule_based_executor import try_rule_based_execution
import pandas as pd

# Load test data
df = pd.read_csv("test.csv")

class TestRuleBasedExecutor:
    def test_average_price(self):
        result = try_rule_based_execution("What is the average Price?", {"df": df})
        assert result is not None and result["success"]
        assert abs(result["output"] - df['Price'].mean()) < 0.001

    def test_count(self):
        result = try_rule_based_execution("How many laptops are there?", {"df": df})
        assert result is not None and result["success"]
        assert result["output"] == len(df)

    def test_max(self):
        result = try_rule_based_execution("What is the maximum Price?", {"df": df})
        assert result is not None and result["success"]
        assert abs(result["output"] - df['Price'].max()) < 0.001

class TestCodeValidator:
    def test_blocks_plot(self):
        from chatbot.execution.code_validator import validate_code
        is_valid, msg = validate_code("df.plot()")
        assert not is_valid

    def test_blocks_to_csv(self):
        from chatbot.execution.code_validator import validate_code
        is_valid, msg = validate_code("df.to_csv('out.csv')")
        assert not is_valid

    def test_blocks_eval(self):
        from chatbot.execution.code_validator import validate_code
        is_valid, msg = validate_code("result = eval('1+1')")
        assert not is_valid

    def test_valid_code_passes(self):
        from chatbot.execution.code_validator import validate_code
        is_valid, msg = validate_code("result = df['Price'].mean()")
        assert is_valid

class TestSafeExecutor:
    def test_basic_mean(self):
        from chatbot.execution.safe_executor import execute_pandas_code
        result = execute_pandas_code("result = df['Price'].mean()", {"df": df})
        assert result["success"]
        assert abs(result["output"] - df['Price'].mean()) < 0.001

    def test_column_not_found(self):
        from chatbot.execution.safe_executor import execute_pandas_code
        result = execute_pandas_code("result = df['Prise'].mean()", {"df": df})
        assert not result["success"]
        assert result["error_type"] == "column_not_found"
        assert "Price" in (result["suggested_columns"] or [])

    def test_row_limit_enforced(self):
        from chatbot.execution.safe_executor import execute_pandas_code, MAX_RESULT_ROWS
        # Create large df
        big_df = pd.concat([df] * 2000, ignore_index=True)
        result = execute_pandas_code("result = big_df", {"big_df": big_df})
        assert result["success"]
        assert len(result["output"]) <= MAX_RESULT_ROWS

class TestVizValidation:
    def test_high_cardinality_bar_rejected(self):
        from chatbot.nodes.viz import validate_data_compatibility
        # Ppi has many unique values
        config = {"x_col": "Ppi", "y_col": "Price"}
        error = validate_data_compatibility("bar_chart", config, df)
        assert error is not None  # Should reject

    def test_low_cardinality_bar_accepted(self):
        from chatbot.nodes.viz import validate_data_compatibility
        config = {"x_col": "Company", "y_col": "Price"}
        error = validate_data_compatibility("bar_chart", config, df)
        assert error is None  # Should accept (Company has ~10 unique values)

    def test_scatter_requires_numeric(self):
        from chatbot.nodes.viz import validate_data_compatibility
        config = {"x_col": "Company", "y_col": "Price"}
        error = validate_data_compatibility("scatter_chart", config, df)
        assert error is not None  # Company is not numeric

class TestProfileFormatter:
    def test_format_profile(self):
        from chatbot.utils.profile_formatter import format_profile_for_prompt
        profile = {
            "tables": {
                "test": {
                    "columns": {
                        "Price": {"dtype": "float64", "n_unique": 100, "n_null": 0,
                                  "missing_pct": 0.0, "cardinality": "high",
                                  "is_numeric": True, "is_categorical": False,
                                  "numeric_stats": {"mean": 10.5, "median": 10.4,
                                                    "std": 0.5, "min": 9.2, "max": 11.9,
                                                    "q25": 10.1, "q75": 10.9}}
                    }
                }
            }
        }
        result = format_profile_for_prompt(profile)
        assert "Price" in result
        assert "numeric" in result
        assert "mean=" in result
```

---

## 15. Test Coverage Summary

| Category | # Tests | Priority |
|----------|---------|----------|
| Basic aggregations (rule-based) | 8 | P0 — must pass |
| Group-by & aggregation | 8 | P0 |
| Filtering & listing | 10 | P0 |
| Top-N / ranking | 5 | P1 |
| For-each / per-group | 4 | P1 |
| Correlation (numeric only) | 6 | P0 — critical guardrail |
| Bar charts | 5 | P1 |
| Scatter charts | 3 | P1 |
| Histograms | 4 | P1 |
| Heatmap / correlation matrix | 3 | P1 |
| Box charts | 3 | P1 |
| Combined insight + viz | 4 | P1 |
| Viz failure / fallback | 4 | P0 |
| Multi-turn follow-ups | 12 | P1 |
| Clarification / ambiguity | 3 | P2 |
| Error handling (typos) | 4 | P1 |
| Execution safety (guardrails) | 5 | P0 |
| Intent classification | 12 | P1 |
| Planner / multi-step | 5 | P1 |
| Tone adaptation | 3 | P2 |
| Suggestion engine | 3 | P2 |
| Quick actions | 4 | P2 |
| End-to-end scenarios | 4 | P1 |
| Regression | 5 | P0 |
| **TOTAL** | **~130** | |

**P0** = blocking, must pass before any release  
**P1** = high priority, must pass for stable release  
**P2** = nice to have, can be deferred