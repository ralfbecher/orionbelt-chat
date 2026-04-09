"""OrionBelt Chat - Chainlit + Pydantic AI application entry point."""

import json
import logging

import chainlit as cl
from chainlit.input_widget import Select, TextInput
from pydantic_ai import AgentRunResultEvent
from pydantic_ai.messages import (
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    PartDeltaEvent,
    PartStartEvent,
    TextPart,
    TextPartDelta,
)

logger = logging.getLogger(__name__)

from src.agent import make_agent
from src.chart_renderer import render_chart_if_present
from src.mcp_servers import get_mcp_servers_named
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
    Main handler. Runs the Pydantic AI agent with event streaming,
    shows tool call steps in the UI, and injects charts inline.
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
    response_msg = cl.Message(content="")
    active_step: cl.Step | None = None
    result_messages = None

    try:
        await response_msg.send()

        async for event in agent.run_stream_events(
            message.content,
            message_history=msg_history,
        ):
            # ── Final result: capture messages for history + charts ──
            if isinstance(event, AgentRunResultEvent):
                result_messages = event.result.all_messages()
                continue

            # ── Tool call start ──────────────────────────────────────
            if isinstance(event, FunctionToolCallEvent):
                tool_name = event.part.tool_name
                tool_args = event.part.args
                if isinstance(tool_args, str):
                    try:
                        tool_args = json.loads(tool_args)
                    except (json.JSONDecodeError, TypeError):
                        pass

                logger.info("Tool call: %s(%s)", tool_name, tool_args)

                active_step = cl.Step(name=tool_name, type="tool")
                active_step.input = json.dumps(tool_args, indent=2) if isinstance(tool_args, dict) else str(tool_args)
                await active_step.send()
                continue

            # ── Tool call result ─────────────────────────────────────
            if isinstance(event, FunctionToolResultEvent):
                result_content = str(event.result.content)
                logger.info(
                    "Tool result: %s → %s",
                    event.result.tool_name,
                    result_content[:200],
                )

                if active_step:
                    active_step.output = result_content
                    await active_step.update()
                    active_step = None
                continue

            # ── Text streaming ───────────────────────────────────────
            if isinstance(event, PartStartEvent) and isinstance(event.part, TextPart):
                if event.part.content:
                    await response_msg.stream_token(event.part.content)
                continue

            if isinstance(event, PartDeltaEvent) and isinstance(event.delta, TextPartDelta):
                chunk = event.delta.content_delta
                # Filter leaked model thinking tokens (e.g. Gemma)
                if "<|channel>" in chunk or "<channel|>" in chunk:
                    continue
                await response_msg.stream_token(chunk)
                continue

        # Finalise streaming
        await response_msg.update()

        # Save message history for next turn
        if result_messages is not None:
            cl.user_session.set("pydantic_history", result_messages)

        # ── Chart rendering ─────────────────────────────────────
        if result_messages:
            for msg in result_messages:
                for part in getattr(msg, "parts", []):
                    if type(part).__name__ == "ToolReturnPart":
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
        logger.exception("Error in message handler")
        await cl.Message(
            content=f"Error: {e}",
            author="System",
        ).send()
