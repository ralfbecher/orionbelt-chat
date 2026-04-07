"""MCP server configuration and lifecycle management."""

from pydantic_ai.mcp import MCPServerHTTP, MCPServerStdio

from .settings import settings


def _is_url(value: str) -> bool:
    return value.startswith("http://") or value.startswith("https://")


def get_analytics_server() -> MCPServerHTTP | MCPServerStdio:
    """
    Return Pydantic AI MCP server for orionbelt-analytics.

    If the configured value is an HTTP(S) URL, returns an MCPServerHTTP
    instance (Streamable HTTP transport). Otherwise treats it as a local
    directory path and returns an MCPServerStdio instance.
    """
    endpoint = settings.analytics_server_dir
    if _is_url(endpoint):
        return MCPServerHTTP(url=endpoint, timeout=60)
    return MCPServerStdio(
        "uv",
        args=[
            "run",
            "--directory",
            endpoint,
            "python",
            "-m",
            "orionbelt_analytics",
        ],
        timeout=60,
    )


def get_semantic_layer_server() -> MCPServerHTTP | MCPServerStdio:
    """
    Return Pydantic AI MCP server for orionbelt-semantic-layer.

    If the configured value is an HTTP(S) URL, returns an MCPServerHTTP
    instance (Streamable HTTP transport). Otherwise treats it as a local
    directory path and returns an MCPServerStdio instance.
    """
    endpoint = settings.semantic_layer_server_dir
    if _is_url(endpoint):
        return MCPServerHTTP(url=endpoint, timeout=60)
    return MCPServerStdio(
        "uv",
        args=[
            "run",
            "--directory",
            endpoint,
            "python",
            "-m",
            "orionbelt_semantic_layer",
        ],
        timeout=60,
    )
