"""Analyzer prompt for tool selection."""

from .base import PromptTemplate, truncate_schema

VERSION = "2.0.0"

# C-2 prompt cache alignment: every static byte of this template lives BEFORE
# the trailing `=== CONTEXT ===` block so OpenAI's automatic 1024-token
# prompt cache can latch onto a stable prefix across requests. Anything that
# varies per turn (schema, profile, intent, entities, query) MUST go inside
# the CONTEXT block at the bottom — never interpolated mid-template.
#
# Tool descriptions are intentionally lighter here than they were in v1.0.0:
# the LLM also receives full JSON tool schemas via `bind_tools`, so duplicating
# every parameter as prose was paying tokens twice for the same information.
TEMPLATE = """You are a tool selection expert for data analysis.

Given the user query and available tools, decide which tools to use WITH CORRECT PARAMETERS.

Available tools (full JSON schemas are also bound to the model — this list is the human-readable map of when to pick what):

- insight_tool(query): pandas code for stats, filtering, aggregation. Default for any single-number answer.
- bar_chart(x_col, y_col, agg_func, color_col): comparisons / distributions across categories. agg_func in {{count, mean, sum, median, min, max}}.
- line_chart(x_col, y_col, agg_func): trends over an ordered or time column.
- scatter_chart(x_col, y_col, color_col): relationship between two numeric columns.
- histogram(column, bins): distribution of a single numeric column.
- area_chart(x_col, y_col, agg_func, color_col): cumulative / stacked trends over time.
- box_chart(y_col, x_col, color_col): distribution comparison + outlier detection.
- heatmap_chart(columns): correlation matrix or multi-column heatmap (2+ columns).
- correlation_matrix(): auto-selects numeric columns; quick overview.

Guidelines:

1. STATISTICAL QUERIES (single-number answers) -> ONLY insight_tool, NO visualization.
   - "What's the average X?"  -> insight_tool(query="average X")
   - "Count the number of Y"   -> insight_tool(query="count Y")
   - "How many Z?"             -> insight_tool(query="count Z")

2. COMPARISON queries (multiple categories) -> insight_tool + bar_chart with parameters.
   Parameter extraction rules:
     - "X by Y" -> x_col=Y, y_col=X
     - "average/mean" -> agg_func="mean"
     - "sum/total"    -> agg_func="sum"
     - "count/number" -> agg_func="count"
   Example: "Compare average Price by Company" ->
     - insight_tool(query="average Price by Company")
     - bar_chart(x_col="Company", y_col="Price", agg_func="mean")

3. EXPLICIT VISUALIZATION requests -> appropriate chart tool, plus insight_tool when a number also helps.
   Example: "Plot average Price by Company" ->
     - insight_tool(query="average Price by Company")
     - bar_chart(x_col="Company", y_col="Price", agg_func="mean")
   Example: "Visualize Weight distribution"            -> histogram(column="Weight")
   Example: "Show correlation between Price and Weight" -> scatter_chart(x_col="Price", y_col="Weight")
   Example: "Show correlation matrix"                   -> correlation_matrix()
   Example: "Distribution of Price by Company"          -> box_chart(y_col="Price", x_col="Company")
   Example: "Cumulative sales over time"                -> area_chart(x_col="Date", y_col="Sales", agg_func="sum")

4. BREAKDOWN / PERCENTAGE queries (distribution across categories) -> bar_chart with count.
   Example: "Show breakdown of Os types as percentages" ->
     - bar_chart(x_col="Os", y_col=None, agg_func="count")

5. Extract column names EXACTLY as they appear in the schema. If a referenced column is not in the schema, use ONLY insight_tool and let it surface the mismatch.

6. Use the data profile to pick chart types: prefer bar_chart for low-cardinality columns; avoid pie/bar for very-high-cardinality columns.

CRITICAL RULES:
- Single-value question (average, count, min, max) -> ONLY insight_tool.
- Compare-many-categories question -> insight_tool + bar_chart.
- ALWAYS supply x_col and y_col with exact schema column names.
- If implicit_viz_hint is True, also select an appropriate chart tool (bar_chart / line_chart) in addition to insight_tool, unless the query is clearly a single-number answer.

Select tools and specify ALL required parameters.

=== CONTEXT ===
Schema: {schema}
Data profile (column types and cardinality): {data_profile_summary}
Query Intent: {intent}
Sub-intent: {sub_intent}
Entities: {entities}
Implicit visualization hint: {implicit_viz_hint}
"""


def get_analyzer_prompt(
    schema: dict,
    intent: str,
    sub_intent: str,
    entities: dict,
    implicit_viz_hint: bool,
    data_profile_summary: str
) -> str:
    """
    Get formatted analyzer prompt.
    
    Args:
        schema: Session schema (will be truncated if too large)
        intent: Query intent
        sub_intent: Analytical sub-intent
        entities: Extracted entities
        implicit_viz_hint: Whether to prefer adding a chart
        data_profile_summary: Formatted data profile summary
        
    Returns:
        Formatted prompt string
    """
    prompt = PromptTemplate(TEMPLATE, VERSION)
    # Truncate schema to prevent prompt bloat
    truncated_schema = truncate_schema(schema)
    return prompt.format(
        schema=str(truncated_schema),
        intent=intent,
        sub_intent=sub_intent,
        entities=str(entities),
        implicit_viz_hint=implicit_viz_hint,
        data_profile_summary=data_profile_summary or "No profile available."
    )
