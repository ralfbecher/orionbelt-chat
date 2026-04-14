"""MCP server configuration and lifecycle management."""

from pydantic_ai.mcp import MCPServerStdio, MCPServerStreamableHTTP

from .settings import settings


def _is_url(value: str) -> bool:
    return value.startswith("http://") or value.startswith("https://")


def _make_server(endpoint: str, module: str) -> MCPServerStreamableHTTP | MCPServerStdio:
    if _is_url(endpoint):
        return MCPServerStreamableHTTP(url=endpoint, timeout=60)
    return MCPServerStdio(
        "uv",
        args=["run", "--directory", endpoint, "python", "-m", module],
        timeout=60,
    )


_SERVER_DEFS: list[tuple[str, str, str]] = [
    ("OrionBelt Analytics", "analytics_server_dir", "orionbelt_analytics"),
    ("OrionBelt Semantic Layer", "semantic_layer_server_dir", "orionbelt_semantic_layer"),
]


def get_mcp_servers_named() -> list[tuple[str, MCPServerStreamableHTTP | MCPServerStdio]]:
    """Return (display_name, server) pairs for configured MCP servers."""
    servers = []
    for name, attr, module in _SERVER_DEFS:
        endpoint = getattr(settings, attr, "")
        if endpoint:
            servers.append((name, _make_server(endpoint, module)))
    return servers
