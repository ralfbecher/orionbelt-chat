"""Chart rendering for MCP Apps ui:// resources."""

import base64
import re

UI_URI_PATTERN = re.compile(r"ui://[^\s\"']+")


async def render_chart_if_present(
    tool_result_text: str,
    mcp_server,
) -> str | None:
    """
    Check tool result text for ui:// resource URIs (MCP Apps).

    If found, fetch the HTML resource and return an iframe HTML string
    suitable for embedding in a cl.Message (requires unsafe_allow_html=true).

    Returns None if no chart URI found or if the server doesn't own the resource.
    """
    match = UI_URI_PATTERN.search(tool_result_text)
    if not match:
        return None

    uri = match.group(0)
    try:
        html_content = await mcp_server.read_resource(uri)
        return _wrap_chart(html_content)
    except Exception:
        return None


def _wrap_chart(html: str, height: int = 480) -> str:
    """Wrap self-contained chart HTML in a sandboxed iframe via data URI."""
    encoded = base64.b64encode(html.encode()).decode()
    return (
        f'<iframe '
        f'src="data:text/html;base64,{encoded}" '
        f'width="100%" height="{height}px" '
        f'style="border:none; border-radius:8px; background:#fff;" '
        f'sandbox="allow-scripts allow-same-origin">'
        f'</iframe>'
    )
