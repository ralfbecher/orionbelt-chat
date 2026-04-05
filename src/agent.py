"""Pydantic AI agent factory for OrionBelt Chat."""

from pydantic_ai import Agent

from .mcp_servers import get_analytics_server, get_semantic_layer_server
from .prompts import SYSTEM_PROMPT
from .providers import resolve_model


def make_agent(provider: str, model: str) -> Agent:
    """
    Create a Pydantic AI Agent with both OrionBelt MCP servers as toolsets.

    The Agent must be used within `async with agent.run_mcp_servers():` to
    start the MCP subprocess connections before calling run_stream().

    Args:
        provider: Provider name ("openrouter", "mlx", "ollama", "anthropic", "openai")
        model: Model identifier string

    Returns:
        Configured Pydantic AI Agent with MCP toolsets

    Example:
        ```python
        agent = make_agent("openrouter", "anthropic/claude-sonnet-4-5")
        async with agent.run_mcp_servers() as mcp_ctx:
            async with agent.run_stream("Show me sales data") as result:
                async for event in result.stream_events():
                    ...
        ```
    """
    llm_model = resolve_model(provider, model)

    return Agent(
        model=llm_model,
        toolsets=[
            get_analytics_server(),
            get_semantic_layer_server(),
        ],
        system_prompt=SYSTEM_PROMPT,
    )
