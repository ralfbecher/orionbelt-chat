"""Chart rendering — detects Plotly figure JSON in MCP tool results."""

import json
import logging
import re

import chainlit as cl

logger = logging.getLogger(__name__)

# Matches a ui:// resource URI in tool result text (MCP Apps pattern)
UI_URI_PATTERN = re.compile(r"ui://[^\s\"']+")


def _try_parse_plotly_figure(text: str):
    """
    Try to extract a Plotly figure dict from tool result text.

    Looks for JSON objects containing 'traces' or 'data' + 'layout' keys,
    which indicate a Plotly figure specification.

    Returns a plotly.graph_objects.Figure or None.
    """
    # Find JSON-like blocks in the text
    for match in re.finditer(r"\{", text):
        start = match.start()
        # Try parsing JSON from this position
        try:
            obj, _ = json.JSONDecoder().raw_decode(text, start)
        except (json.JSONDecodeError, ValueError):
            continue

        if not isinstance(obj, dict):
            continue

        # Plotly figure: has "traces" or "data" key with "layout"
        traces = obj.get("traces") or obj.get("data")
        layout = obj.get("layout")
        if traces and isinstance(traces, list):
            try:
                from plotly import graph_objects as go

                fig = go.Figure(data=traces, layout=layout)
                fig.layout.autosize = True
                fig.layout.width = None
                fig.layout.height = None
                return fig
            except Exception as e:
                logger.debug("Failed to create Plotly figure: %s", e)
                continue

    return None


async def render_chart_if_present(
    tool_result_text: str,
    mcp_server,
) -> cl.Plotly | None:
    """
    Check tool result text for Plotly figure data.

    First tries to parse Plotly JSON directly from the tool result text.
    Falls back to fetching a ui:// resource URI (MCP Apps pattern).

    Returns a cl.Plotly element or None.
    """
    # Strategy 1: Parse Plotly figure JSON from the tool result text
    fig = _try_parse_plotly_figure(tool_result_text)
    if fig:
        return cl.Plotly(name="chart", figure=fig, display="inline")

    # Strategy 2: Fetch HTML from ui:// resource and extract Plotly data
    match = UI_URI_PATTERN.search(tool_result_text)
    if not match:
        return None

    uri = match.group(0)
    try:
        html_content = await mcp_server.read_resource(uri)
        # Try to extract Plotly JSON from the HTML (e.g. Plotly.newPlot(..., data))
        fig = _try_parse_plotly_figure(html_content)
        if fig:
            return cl.Plotly(name="chart", figure=fig, display="inline")
    except Exception:
        pass

    return None
