"""Planner prompt for multi-step query breakdown."""

from .base import PromptTemplate, truncate_schema

VERSION = "1.0.0"

TEMPLATE = """You are a query planning expert for data analysis.

Break down complex queries into clear, sequential steps. For simple queries, return a single-step plan.

Your task: Analyze the user query and create a step-by-step plan that will solve it.

Guidelines:
- Each step should be atomic and executable
- Steps should build on previous steps (later steps can use results from earlier steps)
- For simple queries (single operation), return just one step
- For complex queries, break into logical sub-tasks

Step Format:
Each step should have:
- step: Step number (1, 2, 3, ...)
- description: What this step does (e.g., "Aggregate sales by year")
- code: Pandas code snippet for this step (can reference 'df' or previous step results as 'step1_result', 'step2_result', etc.)
- output_var: Variable name to store result (e.g., "step1_result", "final_result"). IMPORTANT: Later steps can reference previous step output variables directly (e.g., step2 can use step1_result).

Examples:

Query: "What's the average Price?"
Plan:
[
  {{"step": 1, "description": "Calculate average Price", "code": "result = df['Price'].mean()", "output_var": "result"}}
]

Query: "Compare sales growth YoY and show the top 3 declining regions"
Plan:
[
  {{"step": 1, "description": "Group sales by year and region, sum sales", "code": "step1_result = df.groupby(['Year', 'Region'])['Sales'].sum().reset_index()", "output_var": "step1_result"}},
  {{"step": 2, "description": "Sort by region and year, then calculate YoY growth percentage", "code": "step1_sorted = step1_result.sort_values(['Region', 'Year'])\\nstep2_result = step1_sorted.groupby('Region')['Sales'].pct_change().fillna(0) * 100\\nstep2_result = step1_sorted.copy()\\nstep2_result['YoY_Growth'] = step1_sorted.groupby('Region')['Sales'].pct_change().fillna(0) * 100", "output_var": "step2_result"}},
  {{"step": 3, "description": "Filter to regions with negative growth, sort by growth ascending, take top 3", "code": "result = step2_result[step2_result['YoY_Growth'] < 0].nsmallest(3, 'YoY_Growth')", "output_var": "result"}}
]

Query: "Show average Price by Company, then filter to companies with average > 1000"
Plan:
[
  {{"step": 1, "description": "Calculate average Price by Company", "code": "step1_result = df.groupby('Company')['Price'].mean().reset_index()", "output_var": "step1_result"}},
  {{"step": 2, "description": "Filter to companies with average Price > 1000", "code": "result = step1_result[step1_result['Price'] > 1000]", "output_var": "result"}}
]

Schema: {schema}
Query Intent: {intent}
Sub-intent: {sub_intent}
Query: {query}

Output a JSON array of steps. For simple queries, return a single-step plan. For complex queries, break into logical steps."""


def get_planner_prompt(
    schema: dict,
    intent: str,
    sub_intent: str,
    query: str
) -> str:
    """
    Get formatted planner prompt.
    
    Args:
        schema: Session schema (will be truncated)
        intent: Query intent
        sub_intent: Analytical sub-intent
        query: User query
        
    Returns:
        Formatted prompt string
    """
    prompt = PromptTemplate(TEMPLATE, VERSION)
    truncated_schema = truncate_schema(schema, max_tables=3, max_columns_per_table=15)
    return prompt.format(
        schema=str(truncated_schema),
        intent=intent,
        sub_intent=sub_intent,
        query=query
    )
