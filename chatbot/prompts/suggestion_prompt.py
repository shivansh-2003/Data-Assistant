"""Suggestion prompt for follow-up question generation."""

from .base import PromptTemplate, truncate_schema

VERSION = "1.0.0"

TEMPLATE = """You suggest follow-up questions for a data analysis chat.

Given the user's last question, the answer they received (insight summary), and the data schema, suggest exactly 3 short follow-up questions the user might ask next.

Guidelines:
- Each suggestion must be a complete short question (e.g. "Break down by region", "Compare to last quarter", "Show top 10 by revenue")
- Base suggestions on the current topic and available columns
- Vary the type: one drill-down, one comparison or trend, one distribution or filter
- Output exactly 3 questions, one per line, no numbering or bullets

Last Question: {last_query}
Answer Summary: {insight_summary}
Schema: {schema}"""


def get_suggestion_prompt(last_query: str, insight_summary: str, schema: dict) -> str:
    """
    Get formatted suggestion prompt.
    
    Args:
        last_query: User's last question
        insight_summary: Summary of the answer received
        schema: Session schema (will be truncated if too large)
        
    Returns:
        Formatted prompt string
    """
    prompt = PromptTemplate(TEMPLATE, VERSION)
    truncated_schema = truncate_schema(schema, max_tables=3, max_columns_per_table=15)
    return prompt.format(
        last_query=last_query[:200],
        insight_summary=insight_summary[:300] if insight_summary else "No summary available.",
        schema=str(truncated_schema)
    )
