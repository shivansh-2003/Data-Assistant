"""Visualization Centre scoped CSS (injected once per tab)."""

import streamlit as st

_VIZ_CSS_MARK = "_viz_css_injected"


def inject_viz_css() -> None:
    if st.session_state.get(_VIZ_CSS_MARK):
        return
    st.markdown(
        """
<style>
/* Chart hero area */
.viz-chart-container {
    background: var(--card-bg, rgba(255,255,255,0.02));
    border: 1px solid var(--border-color, rgba(128,128,128,0.2));
    border-radius: 16px;
    padding: 20px;
    box-shadow: 0 2px 12px rgba(0,0,0,0.04);
    transition: box-shadow 200ms ease, opacity 0.3s ease-out;
    animation: chartFadeIn 0.3s ease-out;
}
.viz-chart-container:hover {
    box-shadow: 0 4px 20px rgba(0,0,0,0.08);
}
@keyframes chartFadeIn {
    from { opacity: 0; transform: translateY(6px); }
    to { opacity: 1; transform: translateY(0); }
}

/* Chart type pills */
.viz-pill-row {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    align-items: center;
    margin-bottom: 12px;
}
.chart-type-pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 6px 14px;
    border-radius: 999px;
    border: 1px solid var(--border-color, rgba(128,128,128,0.35));
    font-size: 0.8rem;
    font-weight: 500;
    cursor: pointer;
    transition: all 150ms ease;
    background: transparent;
}
.chart-type-pill.active {
    background: var(--primary-color, #667eea);
    color: white !important;
    border-color: var(--primary-color, #667eea);
}

/* Filter bar */
.filter-pill {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 6px 12px;
    border-radius: 999px;
    background: rgba(102, 126, 234, 0.12);
    border: 1px solid rgba(102, 126, 234, 0.35);
    font-size: 0.85rem;
}

/* Skeleton bars (chart loading) */
.viz-skeleton-bars {
    height: 400px;
    display: flex;
    align-items: flex-end;
    gap: 8px;
    padding: 40px;
    justify-content: center;
}
.viz-skeleton-bars .skeleton {
    flex: 1;
    max-width: 48px;
    border-radius: 4px;
    background: linear-gradient(90deg, #e5e7eb 25%, #f3f4f6 50%, #e5e7eb 75%);
    background-size: 200% 100%;
    animation: skeletonShine 1.2s ease-in-out infinite;
}
@keyframes skeletonShine {
    0% { background-position: 200% 0; }
    100% { background-position: -200% 0; }
}

/* Dashboard chart card */
.dash-chart-card {
    border: 1px solid var(--border-color, rgba(128,128,128,0.25));
    border-radius: 12px;
    padding: 8px;
    margin-bottom: 12px;
    background: var(--card-bg, rgba(255,255,255,0.03));
}
.dash-chart-card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 0.85rem;
    font-weight: 600;
    padding: 4px 8px;
    margin-bottom: 4px;
}

.viz-section-title {
    margin: 0 0 0.5rem 0;
    font-size: 1rem;
    font-weight: 600;
}
</style>
        """,
        unsafe_allow_html=True,
    )
    st.session_state[_VIZ_CSS_MARK] = True
