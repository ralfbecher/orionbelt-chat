"""MCP server configuration and lifecycle management."""

from pydantic_ai.mcp import MCPServerHTTP, MCPServerStdio

from .settings import settings


def _is_url(value: str) -> bool:
    return value.startswith("http://") or value.startswith("https://")


def _make_server(endpoint: str, module: str) -> MCPServerHTTP | MCPServerStdio:
    if _is_url(endpoint):
        return MCPServerHTTP(url=endpoint, timeout=60)
    return MCPServerStdio(
        "uv",
        args=["run", "--directory", endpoint, "python", "-m", module],
        timeout=60,
    )


def get_mcp_servers() -> list[MCPServerHTTP | MCPServerStdio]:
    """Return list of configured MCP servers. Skips servers with empty config."""
    servers = []
    if settings.analytics_server_dir:
        servers.append(_make_server(settings.analytics_server_dir, "orionbelt_analytics"))
    if settings.semantic_layer_server_dir:
        servers.append(
            _make_server(settings.semantic_layer_server_dir, "orionbelt_semantic_layer")
        )
    return servers
