"""Analyzer prompt for tool selection."""

from .base import PromptTemplate, truncate_schema

VERSION = "1.0.0"

TEMPLATE = """You are a tool selection expert for data analysis.

Given the user query and available tools, decide which tools to use WITH CORRECT PARAMETERS.

Available Tools:
- insight_tool(query: str): Generate pandas code for statistical analysis, filtering, aggregation
  
- bar_chart(x_col: str, y_col: str|None, agg_func: str, color_col: str|None):
  * x_col: Categorical column for x-axis (REQUIRED)
  * y_col: Numeric column to aggregate (optional, if None will count x_col)
  * agg_func: 'count', 'mean', 'sum', 'median', 'min', 'max'
  * Use for: comparisons, distributions by category
  
- line_chart(x_col: str, y_col: str, agg_func: str):
  * x_col: Ordered/time column for x-axis
  * y_col: Numeric column for y-axis
  * Use for: trends over time
  
- scatter_chart(x_col: str, y_col: str, color_col: str|None):
  * x_col, y_col: Numeric columns
  * Use for: relationships between two numeric variables
  
- histogram(column: str, bins: int|None):
  * column: Numeric column to show distribution
  * Use for: distribution of a single numeric variable
  
- area_chart(x_col: str, y_col: str, agg_func: str, color_col: str|None):
  * x_col: Time/date column for X-axis
  * y_col: Numeric column for Y-axis
  * Use for: cumulative values, stacked area comparisons, trends with filled areas
  
- box_chart(y_col: str, x_col: str|None, color_col: str|None):
  * y_col: Numeric column for distribution (REQUIRED)
  * x_col: Optional categorical column for grouping
  * Use for: distribution comparison, outlier detection, statistical summary
  
- heatmap_chart(columns: list):
  * columns: List of 2+ column names (numeric for correlation matrix)
  * Use for: correlation matrices, pivot table heatmaps, multi-column relationships
  
- correlation_matrix():
  * Auto-selects all numeric columns
  * Use for: quick correlation overview, finding relationships

Guidelines:

1. STATISTICAL QUERIES (single number answers) -> ONLY insight_tool, NO visualization:
   - "What's the average X?"
   - "Count the number of Y"
   - "Average X for Y devices/laptops"
   - "How many Z?"
   Example: "Average SSD size for Nvidia devices" -> insight_tool(query="average SSD for Nvidia")
   
2. COMPARISON queries (multiple categories) -> insight_tool + bar_chart WITH PARAMETERS:
   - "Compare X by Y"
   - "Show differences between A and B"
   - "Which has higher X?"
   
   PARAMETER EXTRACTION RULES:
   - "X by Y" -> x_col=Y, y_col=X
   - "average/mean" -> agg_func="mean"
   - "sum/total" -> agg_func="sum"
   - "count/number" -> agg_func="count"
   
   Example: "Compare average Price by Company" ->
   - insight_tool(query="average Price by Company")
   - bar_chart(x_col="Company", y_col="Price", agg_func="mean")
   
   Example: "Plot average Weight by TypeName" ->
   - insight_tool(query="average Weight by TypeName")
   - bar_chart(x_col="TypeName", y_col="Weight", agg_func="mean")
   
3. EXPLICIT VISUALIZATION requests -> Use appropriate chart tool WITH insight_tool if needed:
   - "Plot X by Y" - use insight_tool + chart
   - "Show/Display a chart/graph of X"
   - "Visualize X"
   - "Create a bar/line/scatter chart"
   Example: "Plot average Price by Company" -> 
   - insight_tool(query="average Price by Company")
   - bar_chart(x_col="Company", y_col="Price", agg_func="mean")
   
   Example: "Visualize Weight distribution" -> histogram(column="Weight")
   
   Example: "Show correlation between Price and Weight" -> scatter_chart(x_col="Price", y_col="Weight")
   Example: "Show correlation matrix" -> correlation_matrix()
   Example: "Distribution of Price by Company" -> box_chart(y_col="Price", x_col="Company")
   Example: "Cumulative sales over time" -> area_chart(x_col="Date", y_col="Sales", agg_func="sum")
   
4. BREAKDOWN/PERCENTAGE queries (distribution across categories) -> bar_chart with count:
   - "Show breakdown of X"
   - "Distribution of X as percentages"
   - "How is X distributed?"
   - "Percentage breakdown by X"
   Example: "Show breakdown of Os types as percentages" ->
   - bar_chart(x_col="Os", y_col=None, agg_func="count")
   
5. Extract column names EXACTLY as they appear in schema: {schema}

6. Use data profile when choosing chart types: prefer bar_chart for columns with few unique values; avoid pie/bar for columns with very many categories.
Data profile (column types and cardinality): {data_profile_summary}

CRITICAL RULES:
- If query asks for a SINGLE VALUE (average, count, min, max), use ONLY insight_tool
- If query asks to COMPARE MULTIPLE CATEGORIES, use insight_tool + bar_chart
- ALWAYS specify x_col and y_col with EXACT column names from schema
- If you can't find column names in schema, use ONLY insight_tool

Query Intent: {intent}
Sub-intent: {sub_intent}
Entities: {entities}
Implicit visualization hint (user asked exploratory/overview question; prefer adding a chart): {implicit_viz_hint}

If implicit_viz_hint is True, prefer to also select an appropriate chart tool (e.g. bar_chart or line_chart) in addition to insight_tool, unless the query is clearly a single-number answer.

Select tools and specify ALL required parameters."""


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
