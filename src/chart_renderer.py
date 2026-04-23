"""Chart rendering for FastMCP Apps ui:// resources.

Detects ui:// URIs in MCP tool results, fetches the resource HTML,
extracts Plotly figure data, and renders it natively via Chainlit.
"""

import json
import logging
import re
from typing import ClassVar

from pydantic.dataclasses import dataclass

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

    Strategies (tried in order):
    1. JSON object with ``data`` or ``traces`` key (standard Plotly figure dict)
    2. ``Plotly.newPlot(el, data, layout)`` call in HTML/JS
    3. JSON array of trace objects (bare traces)

    Normalises to ``{"data": [...], "layout": {...}}`` for Plotly.js.
    """
    # Strategy 1: JSON object with data/traces key
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

    # Strategy 2: Plotly.newPlot(element, data, layout) in JS/HTML
    newplot_match = re.search(r"Plotly\.newPlot\s*\(\s*['\"]?\w+['\"]?\s*,\s*", text)
    if newplot_match:
        rest = text[newplot_match.end():]
        try:
            data, end = json.JSONDecoder().raw_decode(rest)
            if isinstance(data, list):
                # Try to find layout after the data array
                layout = {}
                after_data = rest[end:].lstrip()
                if after_data.startswith(","):
                    after_data = after_data[1:].lstrip()
                    try:
                        layout_obj, _ = json.JSONDecoder().raw_decode(after_data)
                        if isinstance(layout_obj, dict):
                            layout = layout_obj
                    except (json.JSONDecodeError, ValueError):
                        pass
                return json.dumps({"data": data, "layout": layout})
        except (json.JSONDecodeError, ValueError):
            pass

    # Strategy 3: bare JSON array of trace objects
    for match in re.finditer(r"\[", text):
        try:
            arr, _ = json.JSONDecoder().raw_decode(text, match.start())
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(arr, list) and arr and isinstance(arr[0], dict):
            # Looks like trace objects if they have type/x/y/values etc.
            first = arr[0]
            if any(k in first for k in ("type", "x", "y", "values", "labels", "z")):
                return json.dumps({"data": arr, "layout": {}})

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
    logger.info("Chart URI detected: %s (server: %s)", uri, type(mcp_server).__name__)

    if not hasattr(mcp_server, "read_resource"):
        logger.warning("Server %s has no read_resource method", type(mcp_server).__name__)
        return None

    try:
        resource_content = await mcp_server.read_resource(uri)
        logger.info(
            "Resource fetched (%s, %d chars): %.300s",
            type(resource_content).__name__,
            len(str(resource_content)),
            str(resource_content)[:300],
        )
        content_str = str(resource_content) if not isinstance(resource_content, str) else resource_content
        fig_json = _extract_plotly_json(content_str)
        if fig_json:
            fig = json.loads(fig_json)
            layout = fig.setdefault("layout", {})
            layout.setdefault("autosize", True)
            layout.setdefault("width", 900)
            layout.setdefault("height", 550)
            margin = layout.setdefault("margin", {})
            margin.setdefault("t", 40)
            layout.setdefault("legend", {})
            fig.setdefault("config", {
                "displaylogo": False,
                "modeBarButtons": [[
                    "toImage", "zoom2d", "pan2d", "resetScale2d",
                ]],
            })
            fig_json = json.dumps(fig)
            logger.debug("Chart layout modebar: %s", layout.get("modebar"))
            logger.info("Plotly JSON extracted (%d chars)", len(fig_json))
            return PlotlyChart(name="chart", content=fig_json, display="inline")
        else:
            logger.warning("No Plotly JSON found in resource content")
    except Exception as e:
        logger.warning("Failed to render chart from %s: %s", uri, e, exc_info=True)

    return None
