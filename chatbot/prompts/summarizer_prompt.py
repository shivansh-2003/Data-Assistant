"""Summarizer prompt for insight generation."""

from .base import PromptTemplate

VERSION = "1.0.0"

TEMPLATE = """You are a data insight explainer.

Given the output from a pandas analysis, provide a clear explanation.

CRITICAL: Your first sentence MUST be a single-sentence takeaway (e.g. "Revenue is up 12% vs last month, driven by Region X" or "Top 3 categories account for 80% of sales."). You may add one short second sentence if needed for context.

Guidelines:
- First sentence: one clear takeaway with key numbers when relevant
- Use natural language (no code or technical jargon)
- Answer the user's original question directly
- Be concise (1-2 sentences total)

User Query: {query}

Pandas Output:
{output}

Provide the single-sentence takeaway first, then optionally one more sentence."""


def get_summarizer_prompt(query: str, output: str) -> str:
    """
    Get formatted summarizer prompt.
    
    Args:
        query: Original user query
        output: Pandas analysis output (string representation)
        
    Returns:
        Formatted prompt string
    """
    prompt = PromptTemplate(TEMPLATE, VERSION)
    return prompt.format(
        query=query,
        output=str(output)[:2000]  # Truncate very long outputs
    )
