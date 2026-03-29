"""HTML wrappers for card-based sections (Streamlit markdown)."""


def card_open(extra_class: str = "") -> str:
    cls = "card-elevated viz-chart-container"
    if extra_class:
        cls += f" {extra_class}"
    return f'<div class="{cls}" role="region">'


def card_close() -> str:
    return "</div>"


def section_title(text: str, level: int = 3) -> str:
    tag = f"h{min(max(level, 1), 6)}"
    return f"<{tag} class='viz-section-title'>{text}</{tag}>"
