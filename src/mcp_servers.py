"""MCP server configuration and lifecycle management."""

import logging

from . import mcp_sampling  # noqa: F401  — patches ClientSession to advertise sampling.tools
from pydantic_ai.mcp import MCPServerStdio, MCPServerStreamableHTTP

from .providers import default_model_for, resolve_model
from .settings import settings

logger = logging.getLogger(__name__)


def _is_url(value: str) -> bool:
    return value.startswith("http://") or value.startswith("https://")


def _resolve_sampling_model():
    """Resolve the env-configured default model used to answer MCP sampling calls."""
    provider = settings.default_provider
    if not provider:
        return None
    model_name = default_model_for(provider)
    if not model_name:
        return None
    try:
        model = resolve_model(provider, model_name)
    except ValueError as e:
        logger.warning("MCP sampling disabled — could not resolve default model: %s", e)
        return None
    logger.info("MCP sampling model: %s/%s", provider, model_name)
    return model


def _make_server(
    endpoint: str, module: str, sampling_model
) -> MCPServerStreamableHTTP | MCPServerStdio:
    if _is_url(endpoint):
        return MCPServerStreamableHTTP(
            url=endpoint, timeout=60, max_retries=3, sampling_model=sampling_model
        )
    return MCPServerStdio(
        "uv",
        args=["run", "--directory", endpoint, "python", "-m", module],
        timeout=60,
        max_retries=3,
        sampling_model=sampling_model,
    )


_SERVER_DEFS: list[tuple[str, str, str]] = [
    ("OrionBelt Analytics", "analytics_server_dir", "orionbelt_analytics"),
    ("OrionBelt Semantic Layer", "semantic_layer_server_dir", "orionbelt_semantic_layer"),
]


def get_mcp_servers_named() -> list[tuple[str, MCPServerStreamableHTTP | MCPServerStdio]]:
    """Return (display_name, server) pairs for configured MCP servers."""
    sampling_model = _resolve_sampling_model()
    servers = []
    for name, attr, module in _SERVER_DEFS:
        endpoint = getattr(settings, attr, "")
        if endpoint:
            servers.append((name, _make_server(endpoint, module, sampling_model)))
    return servers
