"""Chart rendering for FastMCP Apps ui:// resources.

Detects ui:// URIs in MCP tool results, fetches the resource HTML,
extracts Plotly figure data, and renders it natively via Chainlit.
"""

import json
import logging
import re
from dataclasses import dataclass
from typing import ClassVar

from chainlit.element import Element, ElementType

logger = logging.getLogger(__name__)

UI_URI_PATTERN = re.compile(r"ui://[^\s\"']+")


@dataclass
class PlotlyChart(Element):
    """Lightweight Plotly element — sends raw JSON to the Chainlit frontend
    which already bundles Plotly.js.  No plotly Python package required."""

    type: ClassVar[ElementType] = "plotly"

    def __post_init__(self):
        self.mime = "application/json"
        super().__post_init__()


def _extract_plotly_json(text: str) -> str | None:
    """Extract a Plotly figure dict from text and return it as a JSON string.

    Scans for JSON objects containing ``traces`` (or ``data``) + ``layout``.
    Normalises to ``{"data": [...], "layout": {...}}`` for Plotly.js.
    """
    for match in re.finditer(r"\{", text):
        try:
            obj, _ = json.JSONDecoder().raw_decode(text, match.start())
        except (json.JSONDecodeError, ValueError):
            continue
        if not isinstance(obj, dict):
            continue
        traces = obj.get("traces") or obj.get("data")
        if traces and isinstance(traces, list):
            return json.dumps({"data": traces, "layout": obj.get("layout", {})})
    return None


async def render_chart_if_present(
    tool_result_text: str,
    mcp_server,
) -> PlotlyChart | None:
    """Detect a ``ui://`` resource URI (FastMCP Apps) in tool result text.

    Fetches the resource via the MCP server, extracts Plotly figure data,
    and returns a :class:`PlotlyChart` element for native rendering.
    """
    match = UI_URI_PATTERN.search(tool_result_text)
    if not match:
        return None

    uri = match.group(0)
    try:
        resource_content = await mcp_server.read_resource(uri)
        fig_json = _extract_plotly_json(resource_content)
        if fig_json:
            return PlotlyChart(name="chart", content=fig_json, display="inline")
    except Exception as e:
        logger.debug("Failed to render chart from %s: %s", uri, e)

    return None
