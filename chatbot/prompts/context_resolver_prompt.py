"""Context resolver prompt for follow-up question resolution."""

from .base import PromptTemplate

VERSION = "1.0.0"

TEMPLATE = """You resolve follow-up data questions into a single full question.

Given the previous context (last question and last answer summary) and the user's short follow-up message, output ONE full natural language question that combines them.

Examples:
- Previous: "Show average revenue by region" / Answer showed regions with averages. User: "What about the maximum?" -> "Show maximum revenue by region"
- Previous: "Show me sales" / Answer showed sales data. User: "Just for Q1" -> "Show me sales for Q1"
- Previous: "Show me sales for Q1" / Answer showed Q1 sales. User: "By region" -> "Show me sales for Q1 by region"

Output only the full question, nothing else."""


def get_context_resolver_prompt() -> str:
    """
    Get context resolver prompt (no variables needed).
    
    Returns:
        Prompt string
    """
    return PromptTemplate(TEMPLATE, VERSION).template_str
