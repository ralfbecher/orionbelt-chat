"""OrionBelt Chat - Chainlit + Pydantic AI application entry point."""

import chainlit as cl
from chainlit.input_widget import Select, TextInput

from src.agent import make_agent
from src.chart_renderer import render_chart_if_present
from src.mcp_servers import get_mcp_servers, get_mcp_servers_named
from src.providers import PROVIDER_LABELS, PROVIDER_MODELS, default_model_for
from src.settings import settings


# ── Chainlit Chat Settings (sidebar UI) ───────────────────────────────────


def build_chat_settings() -> list[cl.input_widget.InputWidget]:
    """Define the settings panel shown in the Chainlit sidebar."""
    return [
        Select(
            id="provider",
            label="LLM Provider",
            values=list(PROVIDER_LABELS.keys()),
            initial_value=settings.default_provider,
            tooltip="Select your AI provider",
        ),
        Select(
            id="model",
            label="Model",
            values=PROVIDER_MODELS.get(settings.default_provider, []),
            initial_value=default_model_for(settings.default_provider),
        ),
        TextInput(
            id="custom_model",
            label="Custom model name (overrides above)",
            initial="",
            placeholder="e.g. openrouter:google/gemini-2.5-pro or mlx-community/MyModel-4bit",
            tooltip="Leave empty to use the model selected above",
        ),
    ]


# ── Session lifecycle ──────────────────────────────────────────────────────


@cl.on_chat_start
async def on_start():
    """
    Called once per user session.
    Sets up the agent and starts MCP server connections.
    """
    # Show settings panel
    await cl.ChatSettings(build_chat_settings()).send()

    # Read initial values
    provider = settings.default_provider
    model = default_model_for(provider)

    # Store in session
    cl.user_session.set("provider", provider)
    cl.user_session.set("model", model)
    cl.user_session.set("pydantic_history", None)

    # Create agent and start MCP servers
    init_success = await _init_agent(provider, model)

    if init_success:
        named_servers = get_mcp_servers_named()
        if named_servers:
            server_list = "\n".join(f"- `{name}`" for name, _ in named_servers)
            mcp_info = f"Connected MCP servers:\n{server_list}"
        else:
            mcp_info = "No MCP servers configured."

        await cl.Message(
            content=(
                f"**OrionBelt Analytics Assistant** ready.\n\n"
                f"Provider: `{provider}` | Model: `{model}`\n\n"
                f"{mcp_info}\n\n"
                f"Ask me anything about your data."
            )
        ).send()


async def _init_agent(provider: str, model: str) -> bool:
    """
    Create agent, enter MCP context, store in session.

    Returns:
        True if initialization succeeded, False otherwise
    """
    # Close previous MCP context if it exists
    prev_ctx = cl.user_session.get("mcp_context")
    if prev_ctx:
        try:
            await prev_ctx.__aexit__(None, None, None)
        except Exception:
            pass

    try:
        agent = make_agent(provider, model)
        mcp_ctx = agent.run_mcp_servers()
        await mcp_ctx.__aenter__()
        cl.user_session.set("agent", agent)
        cl.user_session.set("mcp_context", mcp_ctx)
        return True
    except Exception as e:
        cl.user_session.set("agent", None)
        cl.user_session.set("mcp_context", None)
        await cl.Message(
            content=f"⚠️ Failed to initialise agent: {e}",
            author="System",
        ).send()
        return False


@cl.on_chat_end
async def on_end():
    """Clean up MCP server subprocesses when session ends."""
    mcp_ctx = cl.user_session.get("mcp_context")
    if mcp_ctx:
        try:
            await mcp_ctx.__aexit__(None, None, None)
        except Exception:
            pass


# ── Settings change handler ────────────────────────────────────────────────


@cl.on_settings_update
async def on_settings_update(settings_values: dict):
    """
    Called when the user changes provider/model in the sidebar.
    Rebuilds the agent with the new model.
    """
    provider = settings_values.get("provider", settings.default_provider)
    custom_model = settings_values.get("custom_model", "").strip()
    selected_model = settings_values.get("model", default_model_for(provider))
    model = custom_model if custom_model else selected_model

    cl.user_session.set("provider", provider)
    cl.user_session.set("model", model)
    cl.user_session.set("pydantic_history", None)  # clear history on model change

    await cl.Message(
        content=f"Switching to `{provider}` / `{model}`...",
        author="System",
    ).send()

    init_success = await _init_agent(provider, model)

    if init_success:
        await cl.Message(
            content=f"✅ Now using `{model}` via `{provider}`.",
            author="System",
        ).send()


# ── Message handler ────────────────────────────────────────────────────────


@cl.on_message
async def on_message(message: cl.Message):
    """
    Main handler. Runs the Pydantic AI agent with streaming,
    renders tool call steps, and injects charts inline.
    """
    agent = cl.user_session.get("agent")
    if agent is None:
        await cl.Message(
            content="No agent initialised. Check your provider settings.",
            author="System",
        ).send()
        return

    # Get message history for multi-turn context
    msg_history = cl.user_session.get("pydantic_history")

    chart_elements: list[cl.Text] = []

    try:
        response_msg = cl.Message(content="")
        await response_msg.send()

        async with agent.run_stream(
            message.content,
            message_history=msg_history,
        ) as streamed:

            async for chunk in streamed.stream_text(delta=True):
                await response_msg.stream_token(chunk)

            # Finalise streaming
            await response_msg.update()

            # Save message history for next turn (multi-turn context)
            cl.user_session.set(
                "pydantic_history",
                streamed.all_messages(),
            )

            # ── Chart rendering ─────────────────────────────────────
            # Check tool results for MCP Apps ui:// resources
            for msg in streamed.all_messages():
                for part in getattr(msg, "parts", []):
                    part_type = type(part).__name__
                    if part_type == "ToolReturnPart":
                        content = str(getattr(part, "content", ""))
                        for server in agent.toolsets:
                            chart_el = await render_chart_if_present(content, server)
                            if chart_el:
                                chart_elements.append(chart_el)
                                break

            if chart_elements:
                chart_msg = cl.Message(
                    content="Interactive chart:",
                    elements=chart_elements,
                )
                await chart_msg.send()

    except Exception as e:
        await cl.Message(
            content=f"Error: {e}",
            author="System",
        ).send()
