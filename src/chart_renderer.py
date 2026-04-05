"""Chart rendering for MCP Apps ui:// resources."""

import base64
import re

import chainlit as cl


UI_URI_PATTERN = re.compile(r"ui://[^\s\"']+")


async def render_chart_if_present(
    tool_result_text: str,
    mcp_server,
) -> cl.Text | None:
    """
    Check tool result text for ui:// resource URIs (MCP Apps).

    If found, fetch the HTML resource and return a cl.Text element with HTML content.
    Returns None if no chart URI found or if the server doesn't own the resource.

    Args:
        tool_result_text: The tool return content as a string
        mcp_server: Pydantic AI MCP server instance

    Returns:
        cl.Text element with the chart HTML, or None if no chart found
    """
    match = UI_URI_PATTERN.search(tool_result_text)
    if not match:
        return None

    uri = match.group(0)
    try:
        # Use Pydantic AI's MCP server to read the resource
        html_content = await mcp_server.read_resource(uri)
        # Return cl.Text with HTML content (Chainlit renders HTML in Text elements)
        return cl.Text(
            content=_wrap_chart(html_content),
            display="inline",
        )
    except Exception:
        # Don't return error element - let the loop try other MCP servers
        # Only the owning server will have this resource
        return None


def _wrap_chart(html: str, height: int = 480) -> str:
    """
    Wrap self-contained chart HTML in a sandboxed iframe.

    Chainlit renders cl.Text HTML content directly in the message flow.
    For MCP Apps sandboxing, use a sandboxed iframe via data URI.

    Args:
        html: Self-contained HTML from MCP Apps resource
        height: Height of the iframe in pixels (default: 480)

    Returns:
        HTML string with iframe wrapper
    """
    encoded = base64.b64encode(html.encode()).decode()
    return (
        f'<iframe '
        f'src="data:text/html;base64,{encoded}" '
        f'width="100%" height="{height}px" '
        f'style="border:none; border-radius:8px; background:#fff;" '
        f'sandbox="allow-scripts allow-same-origin">'
        f'</iframe>'
    )
