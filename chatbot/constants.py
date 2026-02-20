"""Shared constants for InsightBot. Single source of truth for intents and tool names."""

# Intent classification (router output)
INTENT_DATA_QUERY = "data_query"
INTENT_VISUALIZATION = "visualization_request"
INTENT_SMALL_TALK = "small_talk"
INTENT_REPORT = "report"
INTENT_SUMMARIZE_LAST = "summarize_last"

INTENTS = frozenset({
    INTENT_DATA_QUERY,
    INTENT_VISUALIZATION,
    INTENT_SMALL_TALK,
    INTENT_REPORT,
    INTENT_SUMMARIZE_LAST,
})

# Sub-intents (analytical sub-type from router)
SUB_INTENT_COMPARE = "compare"
SUB_INTENT_TREND = "trend"
SUB_INTENT_CORRELATE = "correlate"
SUB_INTENT_SEGMENT = "segment"
SUB_INTENT_DISTRIBUTION = "distribution"
SUB_INTENT_FILTER = "filter"
SUB_INTENT_REPORT = "report"
SUB_INTENT_GENERAL = "general"

# Tool names (must match LangChain tool names in tools/)
TOOL_INSIGHT = "insight_tool"
TOOL_BAR_CHART = "bar_chart"
TOOL_LINE_CHART = "line_chart"
TOOL_SCATTER_CHART = "scatter_chart"
TOOL_HISTOGRAM = "histogram"
TOOL_AREA_CHART = "area_chart"
TOOL_BOX_CHART = "box_chart"
TOOL_HEATMAP_CHART = "heatmap_chart"
TOOL_CORRELATION_MATRIX = "correlation_matrix"
TOOL_COMBO_CHART = "combo_chart"
TOOL_DASHBOARD = "dashboard"

# Single source for all viz tool names (used in graph routing and viz node)
VIZ_TOOL_NAMES = (
    TOOL_BAR_CHART,
    TOOL_LINE_CHART,
    TOOL_SCATTER_CHART,
    TOOL_HISTOGRAM,
    TOOL_AREA_CHART,
    TOOL_BOX_CHART,
    TOOL_HEATMAP_CHART,
    TOOL_CORRELATION_MATRIX,
    TOOL_COMBO_CHART,
    TOOL_DASHBOARD,
)

# User tone options (response style)
USER_TONE_EXPLORER = "explorer"
USER_TONE_TECHNICAL = "technical"
USER_TONE_EXECUTIVE = "executive"

USER_TONES = (USER_TONE_EXPLORER, USER_TONE_TECHNICAL, USER_TONE_EXECUTIVE)
