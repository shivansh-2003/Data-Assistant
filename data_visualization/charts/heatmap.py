"""
Heatmap chart: correlation matrix, pivot table, and fallbacks.
"""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from typing import Optional, List

from ..utils import create_error_figure


def generate_heatmap(
    df_agg: pd.DataFrame,
    heatmap_columns: Optional[List[str]],
    x_col: Optional[str],
    y_col: Optional[str],
) -> go.Figure:
    """
    Generate heatmap figure. Handles correlation matrix, pivot table, or X/Y fallback.
    Caller is responsible for apply_theme.
    """
    if heatmap_columns and len(heatmap_columns) > 0:
        heatmap_cols = [col for col in heatmap_columns if col != 'None' and col in df_agg.columns]

        if len(heatmap_cols) == 0:
            return create_error_figure("Please select at least one column for heatmap")
        if len(heatmap_cols) == 1:
            return create_error_figure(
                "Heatmap requires at least 2 columns. Please select more columns."
            )

        try:
            df_sample = df_agg[heatmap_cols].head(1000)
            numeric_cols = [
                col for col in heatmap_cols
                if pd.api.types.is_numeric_dtype(df_sample[col])
            ]

            if len(numeric_cols) == len(heatmap_cols):
                corr_matrix = df_sample[numeric_cols].corr()
                fig = px.imshow(
                    corr_matrix,
                    title=f"Heatmap: Correlation Matrix ({len(numeric_cols)} columns)",
                    labels=dict(color="Correlation"),
                    color_continuous_scale='RdBu',
                    aspect="auto"
                )
                fig.update_layout(
                    xaxis_title="",
                    yaxis_title="",
                    height=max(400, len(numeric_cols) * 50)
                )
            elif len(numeric_cols) >= 2:
                corr_matrix = df_sample[numeric_cols].corr()
                fig = px.imshow(
                    corr_matrix,
                    title=f"Heatmap: Correlation Matrix ({len(numeric_cols)} numeric columns)",
                    labels=dict(color="Correlation"),
                    color_continuous_scale='RdBu',
                    aspect="auto"
                )
                fig.update_layout(
                    xaxis_title="",
                    yaxis_title="",
                    height=max(400, len(numeric_cols) * 50)
                )
            else:
                categorical_cols = [
                    col for col in heatmap_cols
                    if not pd.api.types.is_numeric_dtype(df_sample[col])
                ]

                if len(categorical_cols) >= 2 and len(numeric_cols) >= 1:
                    pivot = df_sample.pivot_table(
                        values=numeric_cols[0],
                        index=categorical_cols[0],
                        columns=categorical_cols[1] if len(categorical_cols) > 1 else None,
                        aggfunc='mean'
                    )
                    if pivot.empty:
                        return create_error_figure(
                            "Cannot create heatmap pivot table with selected columns"
                        )
                    fig = px.imshow(
                        pivot,
                        title=f"Heatmap: {numeric_cols[0]} by {categorical_cols[0]}",
                        labels=dict(color=numeric_cols[0]),
                        aspect="auto"
                    )
                elif len(categorical_cols) >= 1 and len(numeric_cols) >= 1:
                    pivot = df_sample.groupby(categorical_cols[0])[numeric_cols[0]].agg(
                        'mean'
                    ).reset_index()
                    pivot = pivot.set_index(categorical_cols[0])[[numeric_cols[0]]].T
                    fig = px.imshow(
                        pivot,
                        title=f"Heatmap: {numeric_cols[0]} by {categorical_cols[0]}",
                        labels=dict(color=numeric_cols[0]),
                        aspect="auto"
                    )
                else:
                    return create_error_figure(
                        "Heatmap needs numeric columns for correlation or "
                        "categorical columns for pivot table"
                    )
            return fig
        except Exception as e:
            return create_error_figure(f"Heatmap error: {str(e)}")

    if x_col and x_col in df_agg.columns and y_col and y_col in df_agg.columns:
        try:
            df_sample = df_agg.head(1000)
            pivot = df_sample.pivot_table(
                values=y_col if pd.api.types.is_numeric_dtype(df_sample[y_col]) else None,
                index=x_col,
                aggfunc=(
                    'mean' if pd.api.types.is_numeric_dtype(df_sample[y_col]) else 'count'
                )
            )
            if pivot.empty:
                return create_error_figure("Cannot create heatmap with selected columns")
            return px.imshow(pivot, title=f"Heatmap: {y_col} by {x_col}")
        except Exception:
            return create_error_figure(
                "Heatmap needs numeric data—try different columns!"
            )

    return create_error_figure("Heatmap needs 2+ columns—select multiple columns!")
