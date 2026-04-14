"""OrionBelt Chat - Chainlit + Pydantic AI application entry point."""

import json
import logging

import chainlit as cl
from chainlit.context import local_steps
from chainlit.input_widget import Select, TextInput
from pydantic_ai import Agent
from pydantic_ai.messages import (
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    PartDeltaEvent,
    PartStartEvent,
    TextPart,
    TextPartDelta,
)

from src.agent import make_agent
from src.chart_renderer import render_chart_if_present
from src.file_downloads import extract_downloads_from_response, extract_downloads_from_tool_results
from src.mcp_servers import get_mcp_servers_named
from src.mermaid_renderer import extract_mermaid_from_tool_results
from src.providers import PROVIDER_LABELS, PROVIDER_MODELS, default_model_for
from src.settings import settings

logger = logging.getLogger(__name__)

# Maximum characters to display in a Chainlit tool-call step output.
# Large MCP tool responses (e.g. SQL query results with many rows) can
# overwhelm the WebSocket/browser and stall the agent loop.  The model
# still receives the full content via pydantic-ai's internal history.
STEP_OUTPUT_LIMIT = 10_000


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
        mcp_info = cl.user_session.get("mcp_info", "")
        status_msg = cl.Message(
            content=(
                f"**OrionBelt Analytics Assistant** ready.\n\n"
                f"Provider: `{provider}` | Model: `{model}`\n\n"
                f"{mcp_info}\n\n"
                f"Ask me anything about your data."
            )
        )
        await status_msg.send()
        cl.user_session.set("status_msg", status_msg)


async def _init_agent(provider: str, model: str) -> bool:
    """
    Connect MCP servers individually, create agent with the successful ones.

    Stores ``mcp_info`` in the session describing connectivity status.

    Returns:
        True if agent was created (even with partial MCP connectivity)
    """
    # Close previously connected MCP servers
    for ctx in cl.user_session.get("mcp_contexts") or []:
        try:
            await ctx.__aexit__(None, None, None)
        except Exception:
            pass

    named_servers = get_mcp_servers_named()
    connected = []
    connected_names = []
    failed_names = []
    active_contexts = []

    # Connect each MCP server individually
    for name, server in named_servers:
        try:
            await server.__aenter__()
            connected.append(server)
            connected_names.append(name)
            active_contexts.append(server)
            logger.info("MCP server connected: %s", name)
        except Exception as e:
            logger.warning("MCP server failed: %s — %s", name, e)
            failed_names.append((name, e))

    # Build MCP status info
    parts = []
    if connected_names:
        server_list = "\n".join(f"- `{n}`" for n in connected_names)
        parts.append(f"Connected MCP servers:\n{server_list}")
    if failed_names:
        fail_list = "\n".join(f"- `{n}`: {e}" for n, e in failed_names)
        parts.append(f"Failed to connect:\n{fail_list}")
    if not named_servers:
        parts.append("No MCP servers configured.")
    cl.user_session.set("mcp_info", "\n\n".join(parts))

    # Create agent with whatever servers connected
    try:
        agent = make_agent(provider, model, toolsets=connected)
        cl.user_session.set("agent", agent)
        cl.user_session.set("mcp_contexts", active_contexts)
        return True
    except Exception as e:
        cl.user_session.set("agent", None)
        cl.user_session.set("mcp_contexts", [])
        await cl.Message(
            content=f"Failed to create agent: {e}",
            author="System",
        ).send()
        return False


@cl.on_stop
async def on_stop():
    """Called when the user clicks the stop button or presses Escape."""
    logger.info("User stopped the current task.")


@cl.on_chat_end
async def on_end():
    """Clean up MCP server subprocesses when session ends."""
    for ctx in cl.user_session.get("mcp_contexts") or []:
        try:
            await ctx.__aexit__(None, None, None)
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
    custom_model = (settings_values.get("custom_model") or "").strip()
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
        # _init_agent already created/updated the status_msg with MCP info
        # Just send a confirmation
        await cl.Message(
            content=f"Now using `{model}` via `{provider}`.",
            author="System",
        ).send()

        # Also update the original header status message if it exists
        status_msg = cl.user_session.get("status_msg")
        mcp_info = cl.user_session.get("mcp_info", "")
        if status_msg:
            status_msg.content = (
                f"**OrionBelt Analytics Assistant** ready.\n\n"
                f"Provider: `{provider}` | Model: `{model}`\n\n"
                f"{mcp_info}\n\n"
                f"Ask me anything about your data."
            )
            await status_msg.update()


# ── Message handler ────────────────────────────────────────────────────────


@cl.on_message
async def on_message(message: cl.Message):
    """
    Main handler. Iterates the Pydantic AI agent graph node-by-node,
    streaming text deltas and showing tool call steps in the Chainlit UI.

    Uses agent.iter() instead of run_stream_events() to avoid the anyio
    rendezvous-channel backpressure that can stall the agent after many
    tool calls.
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

    # The @cl.on_message decorator wraps this handler in an "on_message" Step
    # via local_steps. All Steps must be children of that wrapper so they render
    # in chronological order (Steps first, response text last).
    _parent_steps = local_steps.get() or []
    _run_step_id = _parent_steps[-1].id if _parent_steps else None

    chart_elements: list = []
    response_msg = cl.Message(content="")
    response_sent = False
    tool_steps: dict[str, cl.Step] = {}  # tool_call_id → Step
    result_messages = None

    logger.info(
        "Message received (%d history messages): %.100s",
        len(msg_history) if msg_history else 0,
        message.content,
    )

    try:
        text_parts: list[str] = []
        thinking_step: cl.Step | None = None

        async with agent.iter(
            message.content,
            message_history=msg_history,
        ) as agent_run:
            async for node in agent_run:
                node_name = type(node).__name__
                logger.debug("Agent node: %s", node_name)

                # ── Model request: collect text ────────────────────
                if Agent.is_model_request_node(node):
                    logger.info("Streaming model request …")
                    # Show a thinking indicator while the model generates
                    thinking_step = cl.Step(name="Thinking", type="run", parent_id=_run_step_id)
                    await thinking_step.send()
                    async with node.stream(agent_run.ctx) as stream:
                        async for event in stream:
                            if isinstance(event, PartStartEvent) and isinstance(event.part, TextPart):
                                if thinking_step:
                                    thinking_step.output = ""
                                    await thinking_step.update()
                                    thinking_step = None
                                if event.part.content:
                                    text_parts.append(event.part.content)
                            elif isinstance(event, PartDeltaEvent) and isinstance(event.delta, TextPartDelta):
                                if thinking_step:
                                    thinking_step.output = ""
                                    await thinking_step.update()
                                    thinking_step = None
                                chunk = event.delta.content_delta
                                # Filter leaked model thinking tokens (e.g. Gemma)
                                if "<|channel>" in chunk or "<channel|>" in chunk:
                                    continue
                                text_parts.append(chunk)
                    # Close thinking step if model produced no text (only tool calls)
                    if thinking_step:
                        thinking_step.output = ""
                        await thinking_step.update()
                        thinking_step = None
                    logger.info("Model request complete.")

                # ── Tool calls: show as Chainlit steps ──────────────
                elif Agent.is_call_tools_node(node):
                    logger.info("Processing tool calls …")
                    try:
                        async with node.stream(agent_run.ctx) as stream:
                            async for event in stream:
                                if isinstance(event, FunctionToolCallEvent):
                                    tool_name = event.part.tool_name
                                    tool_args = event.part.args
                                    call_id = event.part.tool_call_id
                                    if isinstance(tool_args, str):
                                        try:
                                            tool_args = json.loads(tool_args)
                                        except (json.JSONDecodeError, TypeError):
                                            pass

                                    logger.info("Tool call [%s]: %s(%s)", call_id, tool_name, tool_args)

                                    step = cl.Step(name=tool_name, type="tool", parent_id=_run_step_id)
                                    step.input = (
                                        json.dumps(tool_args, indent=2) if isinstance(tool_args, dict) else str(tool_args)
                                    )
                                    await step.send()
                                    tool_steps[call_id] = step

                                elif isinstance(event, FunctionToolResultEvent):
                                    result_content = str(event.result.content)
                                    call_id = event.result.tool_call_id
                                    logger.info(
                                        "Tool result [%s] (%d chars): %s → %s",
                                        call_id,
                                        len(result_content),
                                        event.result.tool_name,
                                        result_content[:200],
                                    )

                                    step = tool_steps.pop(call_id, None)
                                    if step:
                                        if len(result_content) > STEP_OUTPUT_LIMIT:
                                            step.output = (
                                                result_content[:STEP_OUTPUT_LIMIT]
                                                + f"\n\n… (truncated — {len(result_content):,} chars total)"
                                            )
                                        else:
                                            step.output = result_content
                                        await step.update()
                    except Exception as tool_err:
                        # pydantic-ai's ModelRetry (MCP tool validation errors)
                        # can leak through node.stream() instead of being retried
                        # internally.  Log the error, close any open UI steps, and
                        # let the agent loop continue — the model will see the
                        # error in its history and can adjust.
                        logger.warning("Tool execution error: %s", tool_err)
                        for call_id, step in list(tool_steps.items()):
                            step.output = f"Error: {tool_err}"
                            await step.update()
                        tool_steps.clear()
                    logger.info("Tool calls complete.")

            # Capture full message history while the run context is still open
            if agent_run.result is not None:
                result_messages = agent_run.all_messages()
                logger.info("Agent run finished — %d messages in history.", len(result_messages))
            else:
                logger.warning("Agent run ended without a result.")

        logger.debug("Agent context closed.")

        # Send the response message AFTER all steps so it appears below them
        response_msg.content = "".join(text_parts)

        # Attach downloadable files from code blocks in the response
        download_elements = extract_downloads_from_response(response_msg.content)
        if result_messages:
            download_elements.extend(extract_downloads_from_tool_results(result_messages))
        if download_elements:
            # Deduplicate by content (code block and tool result may overlap)
            seen_content: set[bytes] = set()
            unique = []
            for el in download_elements:
                key = el.content if isinstance(el.content, bytes) else (el.content or "").encode()
                if key not in seen_content:
                    seen_content.add(key)
                    unique.append(el)
            response_msg.elements = unique

        await response_msg.send()
        response_sent = True
        logger.debug("Response message sent.")

        # Save message history for next turn
        if result_messages is not None:
            cl.user_session.set("pydantic_history", result_messages)

        # ── Chart rendering ─────────────────────────────────────
        if result_messages:
            mcp_servers = [s for s in agent.toolsets if hasattr(s, "read_resource")]
            logger.info(
                "Chart scan: %d messages, %d MCP servers with read_resource",
                len(result_messages), len(mcp_servers),
            )
            for msg in result_messages:
                for part in getattr(msg, "parts", []):
                    if type(part).__name__ == "ToolReturnPart":
                        raw = getattr(part, "content", "")
                        # content may be str, dict, or list — flatten to string for URI detection
                        content = json.dumps(raw) if isinstance(raw, dict | list) else str(raw)
                        logger.info(
                            "ToolReturnPart [%s] (%d chars): %.200s",
                            getattr(part, "tool_name", "?"),
                            len(content),
                            content[:200],
                        )
                        for server in mcp_servers:
                            chart_el = await render_chart_if_present(content, server)
                            if chart_el:
                                chart_elements.append(chart_el)
                                break

        if chart_elements:
            logger.info("Sending %d chart elements", len(chart_elements))
            await cl.Message(
                content="",
                elements=chart_elements,
            ).send()

        # ── Mermaid diagram rendering ──────────────────────────────
        # If tool results contain Mermaid syntax and the LLM response
        # doesn't already include a mermaid code block, send it so
        # the client-side Mermaid.js renderer picks it up.
        if result_messages and "```mermaid" not in response_msg.content:
            for diagram in extract_mermaid_from_tool_results(result_messages):
                logger.info("Sending Mermaid diagram (%d chars)", len(diagram))
                await cl.Message(content=f"```mermaid\n{diagram}\n```").send()

    except BaseException as e:
        # BaseException catches asyncio.CancelledError (Python 3.9+)
        # which Chainlit may raise on WebSocket disconnect / timeout.
        logger.exception("Error in message handler")
        if isinstance(e, KeyboardInterrupt | SystemExit):
            raise

        # Detect MCP session termination and attempt automatic reconnection
        err_chain = str(e) + " " + str(getattr(e, "__cause__", ""))
        is_mcp_session_error = any(
            phrase in err_chain
            for phrase in ("Session terminated", "session expired", "McpError")
        )

        try:
            if is_mcp_session_error:
                logger.warning("MCP session lost — attempting reconnection …")
                await cl.Message(
                    content="MCP server connection lost. Reconnecting …",
                    author="System",
                ).send()
                provider = cl.user_session.get("provider")
                model = cl.user_session.get("model")
                if await _init_agent(provider, model):
                    mcp_info = cl.user_session.get("mcp_info", "")
                    await cl.Message(
                        content=f"Reconnected. {mcp_info}\n\nPlease resend your message.",
                        author="System",
                    ).send()
                else:
                    await cl.Message(
                        content="Reconnection failed. Check that MCP servers are running.",
                        author="System",
                    ).send()
            else:
                await cl.Message(
                    content=f"Error: {e}",
                    author="System",
                ).send()
        except Exception:
            pass  # UI may already be gone
    finally:
        # Ensure the response message is sent even on error so the UI
        # never shows a permanent "loading" state.
        try:
            if not response_sent:
                response_msg.content = "".join(text_parts) if text_parts else ""
                await response_msg.send()
        except Exception:
            pass
