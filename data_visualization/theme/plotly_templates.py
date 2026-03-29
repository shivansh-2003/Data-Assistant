"""
Custom Plotly templates aligned with Data Assistant design system.
"""

from __future__ import annotations

import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st


def register_plotly_templates() -> None:
    """Register once; idempotent."""
    if getattr(register_plotly_templates, "_done", False):
        return
    light = go.layout.Template(
        layout=go.Layout(
            font=dict(family="Inter, system-ui, sans-serif", size=13, color="#374151"),
            title=dict(
                font=dict(size=16, color="#111827", family="Inter, system-ui, sans-serif"),
                x=0,
                xanchor="left",
                pad=dict(l=0),
            ),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            colorway=[
                "#667eea",
                "#f59e0b",
                "#22c55e",
                "#ef4444",
                "#8b5cf6",
                "#06b6d4",
                "#ec4899",
                "#14b8a6",
            ],
            xaxis=dict(
                gridcolor="rgba(0,0,0,0.06)",
                zeroline=False,
                title_font=dict(size=12, color="#6b7280"),
            ),
            yaxis=dict(
                gridcolor="rgba(0,0,0,0.06)",
                zeroline=False,
                title_font=dict(size=12, color="#6b7280"),
            ),
            hoverlabel=dict(
                bgcolor="white",
                bordercolor="#e5e7eb",
                font=dict(size=12, family="Inter, system-ui, sans-serif"),
            ),
            legend=dict(
                bgcolor="rgba(0,0,0,0)",
                borderwidth=0,
                font=dict(size=11),
            ),
            margin=dict(l=48, r=24, t=48, b=40),
        )
    )
    dark = go.layout.Template(
        layout=go.Layout(
            font=dict(family="Inter, system-ui, sans-serif", size=13, color="#e5e7eb"),
            title=dict(
                font=dict(size=16, color="#f9fafb", family="Inter, system-ui, sans-serif"),
                x=0,
                xanchor="left",
                pad=dict(l=0),
            ),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            colorway=[
                "#818cf8",
                "#fbbf24",
                "#4ade80",
                "#f87171",
                "#a78bfa",
                "#22d3ee",
                "#f472b6",
                "#2dd4bf",
            ],
            xaxis=dict(
                gridcolor="rgba(255,255,255,0.08)",
                zeroline=False,
                title_font=dict(size=12, color="#9ca3af"),
            ),
            yaxis=dict(
                gridcolor="rgba(255,255,255,0.08)",
                zeroline=False,
                title_font=dict(size=12, color="#9ca3af"),
            ),
            hoverlabel=dict(
                bgcolor="#1f2937",
                bordercolor="#374151",
                font=dict(size=12, family="Inter, system-ui, sans-serif"),
            ),
            legend=dict(
                bgcolor="rgba(0,0,0,0)",
                borderwidth=0,
                font=dict(size=11),
            ),
            margin=dict(l=48, r=24, t=48, b=40),
        )
    )
    pio.templates["data_assistant_light"] = light
    pio.templates["data_assistant_dark"] = dark
    register_plotly_templates._done = True  # type: ignore[attr-defined]


def apply_theme(fig: go.Figure) -> go.Figure:
    """Apply Data Assistant or Streamlit theme to a figure."""
    register_plotly_templates()
    try:
        theme = st.get_option("theme.base")
    except Exception:
        theme = "light"
    name = "data_assistant_dark" if theme == "dark" else "data_assistant_light"
    try:
        fig.update_layout(template=name)
    except Exception:
        fig.update_layout(template="plotly_white" if theme != "dark" else "plotly_dark")
    return fig
