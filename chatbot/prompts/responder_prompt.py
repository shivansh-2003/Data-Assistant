"""Responder prompt (currently not used as LLM call, but kept for reference/consistency)."""

from .base import PromptTemplate

VERSION = "1.0.0"

TEMPLATE = """You are a helpful data analysis assistant.

Format the final response combining insights and visualizations.

Guidelines:
- Start with a direct answer to the user's question
- Include key findings from the analysis
- ONLY mention visualization if has_viz is True
- If has_viz is False, just provide the insight without mentioning charts
- Be friendly and conversational
- Keep it concise (2-3 sentences max)

User Query: {query}

Analysis Result: {insights}
Visualization Created: {has_viz}

Rules:
- If has_viz is False: Just present the insight naturally, don't mention visualization
- If has_viz is True: Mention the chart and encourage viewing it

Format the final response."""


def get_responder_prompt(query: str, insights: str, has_viz: bool) -> str:
    """
    Get responder prompt (for reference; responder node currently composes responses directly).
    
    Args:
        query: User query
        insights: Analysis insights
        has_viz: Whether visualization was created
        
    Returns:
        Formatted prompt string
    """
    prompt = PromptTemplate(TEMPLATE, VERSION)
    return prompt.format(
        query=query,
        insights=insights,
        has_viz=has_viz
    )
