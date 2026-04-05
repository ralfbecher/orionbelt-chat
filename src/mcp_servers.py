"""MCP server configuration and lifecycle management."""

from pydantic_ai.mcp import MCPServerStdio

from .settings import settings


def get_analytics_server():
    """
    Return Pydantic AI MCP server for orionbelt-analytics.

    The server will be started as a subprocess when entering the MCP context
    via agent.run_mcp_servers(). Supports stdio transport only for now.

    Returns:
        MCPServerStdio instance configured for orionbelt-analytics
    """
    return MCPServerStdio(
        "uv",
        args=[
            "run",
            "--directory",
            settings.analytics_server_dir,
            "python",
            "-m",
            "orionbelt_analytics",
        ],
        timeout=60,
    )


def get_semantic_layer_server():
    """
    Return Pydantic AI MCP server for orionbelt-semantic-layer.

    The server will be started as a subprocess when entering the MCP context
    via agent.run_mcp_servers(). Supports stdio transport only for now.

    Returns:
        MCPServerStdio instance configured for orionbelt-semantic-layer
    """
    return MCPServerStdio(
        "uv",
        args=[
            "run",
            "--directory",
            settings.semantic_layer_server_dir,
            "python",
            "-m",
            "orionbelt_semantic_layer",
        ],
        timeout=60,
    )
