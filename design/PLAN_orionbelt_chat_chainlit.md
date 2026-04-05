# Plan: OrionBelt Chat — Chainlit + Pydantic AI

## Goal

Build a standalone, open-architecture chat client that:

- Provides a professional chat UI via **Chainlit**
- Runs agentic tool-calling loops via **Pydantic AI**
- Connects to **any LLM provider** the user configures:
  - Cloud: **OpenRouter** (300+ models, single API key)
  - Local macOS: **mlx-openai-server** (Apple Silicon, OpenAI-compatible)
  - Local cross-platform: **Ollama** (OpenAI-compatible)
  - Direct keys: Anthropic, OpenAI, Gemini (optional bypass of OpenRouter)
- Connects to **orionbelt-analytics** and **orionbelt-semantic-layer** as MCP servers
- Renders interactive charts inline using Chainlit's `cl.Html` element
- Ships as a standalone Python package in the OrionBelt monorepo

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                     OrionBelt Chat                               │
│                   (Chainlit UI — port 8080)                      │
│                                                                  │
│  ┌────────────────────┐    ┌───────────────────────────────────┐ │
│  │  Chat Panel        │    │  Chart Panel (cl.Html iframe)     │ │
│  │  cl.Message        │    │  MCP Apps HTML injected here      │ │
│  │  cl.Step (tools)   │    └───────────────────────────────────┘ │
│  │  cl.Text (debug)   │                                          │
│  └────────────────────┘    ┌───────────────────────────────────┐ │
│                            │  Settings Panel (cl.ChatSettings) │ │
│                            │  Provider / Model / API key       │ │
│                            │  MCP server status                │ │
│                            └───────────────────────────────────┘ │
│                                                                  │
│  ┌───────────────────────────────────────────────────────────┐   │
│  │                   Agent Layer (Pydantic AI)               │   │
│  │                                                           │   │
│  │  Agent(model, toolsets=[analytics_mcp, semantic_mcp])     │   │
│  │  agent.run_stream()  →  cl.Message streaming              │   │
│  └──────────────────────┬─────────────────────┬─────────────┘   │
└─────────────────────────┼─────────────────────┼─────────────────┘
                          │                     │
          ┌───────────────▼──────┐  ┌───────────▼──────────────────┐
          │    LLM Providers     │  │    OrionBelt MCP Servers      │
          │                      │  │                               │
          │  OpenRouter          │  │  orionbelt-analytics          │
          │  openrouter:model    │  │  (MCPServerStdio / HTTP)      │
          │                      │  │                               │
          │  mlx-openai-server   │  │  orionbelt-semantic-layer     │
          │  localhost:8000/v1   │  │  (MCPServerStdio / HTTP)      │
          │                      │  │                               │
          │  Ollama              │  └───────────────────────────────┘
          │  localhost:11434/v1  │
          │                      │
          │  Direct Anthropic /  │
          │  OpenAI / Gemini     │
          └──────────────────────┘
```

---

## Project Structure

```
orionbelt-chat/
├── pyproject.toml
├── uv.lock
├── .env.example
├── chainlit.md                    # Welcome message shown in UI
├── chainlit.yaml                  # Chainlit config (auth, theming)
├── mcp_servers.json               # MCP server definitions (Claude Desktop format)
├── README.md
├── app.py                         # Chainlit entry point
└── orionbelt_chat/
    ├── __init__.py
    ├── agent.py                   # Pydantic AI agent factory
    ├── providers.py               # LLM provider resolution
    ├── mcp_servers.py             # MCP server config + lifecycle
    ├── chart_renderer.py          # MCP Apps HTML → cl.Html
    ├── settings.py                # Pydantic Settings (env vars)
    └── prompts.py                 # System prompt templates
```

---

## Dependencies

```toml
# pyproject.toml
[project]
name = "orionbelt-chat"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "chainlit>=2.0.0",
    "pydantic-ai[openai,anthropic,openrouter]>=0.0.60",
    "pydantic-settings>=2.0.0",
    "python-dotenv>=1.0.0",
    "httpx>=0.27.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0.0", "pytest-asyncio>=0.23.0"]
```

Install:
```bash
uv sync
```

Run:
```bash
uv run chainlit run app.py --watch
```

---

## Implementation Plan

### Phase 1: Settings (`orionbelt_chat/settings.py`)

Central config via Pydantic Settings, fully driven by `.env` or environment variables.

```python
# orionbelt_chat/settings.py
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    # ── LLM providers ──────────────────────────────────────────
    # Primary: OpenRouter
    openrouter_api_key: str = ""
    openrouter_default_model: str = "anthropic/claude-sonnet-4-5"

    # Local: mlx-openai-server (primary local option)
    mlx_base_url: str = "http://localhost:8000/v1"
    mlx_default_model: str = "mlx-community/Qwen2.5-14B-Instruct-4bit"

    # Local: Ollama (fallback)
    ollama_base_url: str = "http://localhost:11434/v1"
    ollama_default_model: str = "qwen2.5:14b"

    # Direct provider keys (optional, bypass OpenRouter)
    anthropic_api_key: str = ""
    openai_api_key: str = ""

    # ── Default provider on startup ────────────────────────────
    # Values: "openrouter" | "mlx" | "ollama" | "anthropic" | "openai"
    default_provider: str = "openrouter"
    default_model: str = ""       # if empty, uses provider default above

    # ── OrionBelt services ─────────────────────────────────────
    orionbelt_api_url: str = "http://localhost:8000"

    # ── MCP server paths (for stdio transport) ─────────────────
    analytics_server_dir: str = "../orionbelt-analytics"
    semantic_layer_server_dir: str = "../orionbelt-semantic-layer"
    # Set to "http" to use Streamable HTTP instead of stdio
    analytics_transport: str = "stdio"
    analytics_http_url: str = "http://localhost:8001/mcp"
    semantic_transport: str = "stdio"
    semantic_http_url: str = "http://localhost:8002/mcp"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
```

---

### Phase 2: LLM Provider Resolution (`orionbelt_chat/providers.py`)

Single function that maps a provider name + model string to a Pydantic AI model object.
This is where all provider-specific logic lives — the agent itself never touches SDK details.

```python
# orionbelt_chat/providers.py
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.openrouter import OpenRouterModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.providers.openrouter import OpenRouterProvider
from pydantic_ai.providers.anthropic import AnthropicProvider

from .settings import settings


# Human-readable labels shown in the UI dropdown
PROVIDER_LABELS = {
    "openrouter": "OpenRouter (cloud, 300+ models)",
    "mlx": "MLX local (Apple Silicon)",
    "ollama": "Ollama local",
    "anthropic": "Anthropic direct",
    "openai": "OpenAI direct",
}

# Curated model lists per provider shown in the UI
PROVIDER_MODELS = {
    "openrouter": [
        "anthropic/claude-sonnet-4-5",
        "anthropic/claude-opus-4-5",
        "anthropic/claude-haiku-4-5",
        "openai/gpt-4o",
        "openai/gpt-4o-mini",
        "google/gemini-2.5-pro",
        "google/gemini-2.5-flash",
        "deepseek/deepseek-r1",
        "meta-llama/llama-3.3-70b-instruct",
        "qwen/qwen-2.5-72b-instruct",
        "mistralai/mistral-large",
    ],
    "mlx": [
        "mlx-community/Qwen2.5-14B-Instruct-4bit",
        "mlx-community/Llama-3.3-70B-Instruct-4bit",
        "mlx-community/mistral-7b-instruct-v0.3-4bit",
        "mlx-community/gemma-3-12b-it-4bit",
    ],
    "ollama": [
        "qwen2.5:14b",
        "llama3.3:70b",
        "mistral:7b",
        "phi4:14b",
    ],
    "anthropic": [
        "claude-sonnet-4-6",
        "claude-opus-4-6",
        "claude-haiku-4-5-20251001",
    ],
    "openai": [
        "gpt-4o",
        "gpt-4o-mini",
        "o3-mini",
    ],
}


def resolve_model(provider: str, model: str):
    """
    Return a Pydantic AI model object for the given provider + model name.
    Raises ValueError for unknown providers or missing credentials.
    """
    match provider:
        case "openrouter":
            if not settings.openrouter_api_key:
                raise ValueError("OPENROUTER_API_KEY not set")
            return OpenRouterModel(
                model,
                provider=OpenRouterProvider(api_key=settings.openrouter_api_key),
            )

        case "mlx":
            # mlx-openai-server exposes an OpenAI-compatible endpoint
            return OpenAIModel(
                model,
                provider=OpenAIProvider(
                    base_url=settings.mlx_base_url,
                    api_key="mlx-local",  # ignored by local server
                ),
            )

        case "ollama":
            return OpenAIModel(
                model,
                provider=OpenAIProvider(
                    base_url=settings.ollama_base_url,
                    api_key="ollama",
                ),
            )

        case "anthropic":
            if not settings.anthropic_api_key:
                raise ValueError("ANTHROPIC_API_KEY not set")
            return AnthropicModel(
                model,
                provider=AnthropicProvider(api_key=settings.anthropic_api_key),
            )

        case "openai":
            if not settings.openai_api_key:
                raise ValueError("OPENAI_API_KEY not set")
            return OpenAIModel(model)

        case _:
            raise ValueError(f"Unknown provider: {provider!r}")


def default_model_for(provider: str) -> str:
    """Return the default model string for a provider."""
    defaults = {
        "openrouter": settings.openrouter_default_model,
        "mlx": settings.mlx_default_model,
        "ollama": settings.ollama_default_model,
        "anthropic": "claude-sonnet-4-6",
        "openai": "gpt-4o",
    }
    return defaults.get(provider, "")
```

---

### Phase 3: MCP Server Config (`orionbelt_chat/mcp_servers.py`)

Returns Pydantic AI MCP server objects based on settings.
Supports both stdio (subprocess) and Streamable HTTP transport.

```python
# orionbelt_chat/mcp_servers.py
from pydantic_ai.mcp import MCPServerStdio, MCPServerStreamableHTTP
from .settings import settings


def get_analytics_server():
    """Return Pydantic AI MCP server for orionbelt-analytics."""
    if settings.analytics_transport == "http":
        return MCPServerStreamableHTTP(settings.analytics_http_url)
    return MCPServerStdio(
        "uv",
        args=[
            "run",
            "--directory", settings.analytics_server_dir,
            "python", "-m", "orionbelt_analytics",
        ],
        timeout=60,
    )


def get_semantic_layer_server():
    """Return Pydantic AI MCP server for orionbelt-semantic-layer."""
    if settings.semantic_transport == "http":
        return MCPServerStreamableHTTP(settings.semantic_http_url)
    return MCPServerStdio(
        "uv",
        args=[
            "run",
            "--directory", settings.semantic_layer_server_dir,
            "python", "-m", "orionbelt_semantic_layer",
        ],
        timeout=60,
    )
```

---

### Phase 4: System Prompt (`orionbelt_chat/prompts.py`)

```python
# orionbelt_chat/prompts.py

SYSTEM_PROMPT = """
You are the OrionBelt Analytics Assistant — an expert data analyst with access to
the OrionBelt Semantic Layer and Analytics tools.

## Your capabilities
- Query live data through the OrionBelt Semantic Layer (OBML models)
- Execute SQL queries and retrieve results
- Generate interactive charts and visualizations
- Analyze schemas, ontologies, and data relationships

## How to work
1. Always explore the available OBML models first when the user asks about data
2. Use compile_query to generate SQL from OBML, then execute_sql_query to run it
3. When showing data visually, use execute_chart to generate an interactive chart
4. For schema questions, use analyze_schema or generate_ontology

## Response style
- Be concise and data-focused
- When returning query results, always summarize key insights
- Mention chart interactions available (hover, filter, zoom) when a chart is shown
- If a tool fails, explain what happened and suggest an alternative approach
""".strip()
```

---

### Phase 5: Agent Factory (`orionbelt_chat/agent.py`)

Creates a Pydantic AI Agent with the selected model and both MCP servers as toolsets.
The agent is recreated per Chainlit session when the user changes provider/model.

```python
# orionbelt_chat/agent.py
from pydantic_ai import Agent
from .providers import resolve_model
from .mcp_servers import get_analytics_server, get_semantic_layer_server
from .prompts import SYSTEM_PROMPT


def make_agent(provider: str, model: str) -> Agent:
    """
    Create a Pydantic AI Agent with both OrionBelt MCP servers as toolsets.

    The Agent must be used within `async with agent.run_mcp_servers():` to
    start the MCP subprocess connections before calling run_stream().
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
```

---

### Phase 6: Chart Renderer (`orionbelt_chat/chart_renderer.py`)

Detects MCP Apps `ui://` resource references in tool results and renders them
inline via `cl.Html`. Since Chainlit renders HTML directly, no iframe wrapping
workaround is needed — the HTML is injected as-is into the message.

```python
# orionbelt_chat/chart_renderer.py
import re
import httpx
import chainlit as cl
from pydantic_ai.messages import ToolReturnPart


UI_URI_PATTERN = re.compile(r'ui://[^\s"\']+')


async def render_chart_if_present(
    tool_result_text: str,
    mcp_server,
) -> cl.Html | None:
    """
    Check tool result text for ui:// resource URIs (MCP Apps).
    If found, fetch the HTML resource and return a cl.Html element.
    Returns None if no chart URI found.
    """
    match = UI_URI_PATTERN.search(tool_result_text)
    if not match:
        return None

    uri = match.group(0)
    try:
        # Use Pydantic AI's MCP server to read the resource
        html_content = await mcp_server.read_resource(uri)
        return cl.Html(
            content=_wrap_chart(html_content),
            display="inline",
        )
    except Exception as e:
        return cl.Html(
            content=f'<p style="color:#c00">Chart load error: {e}</p>',
            display="inline",
        )


def _wrap_chart(html: str, height: int = 480) -> str:
    """
    Wrap self-contained chart HTML in a sized container.
    Chainlit renders cl.Html content directly in the message flow.
    For MCP Apps sandboxing, use a sandboxed iframe via data URI.
    """
    import base64
    encoded = base64.b64encode(html.encode()).decode()
    return (
        f'<iframe '
        f'src="data:text/html;base64,{encoded}" '
        f'width="100%" height="{height}px" '
        f'style="border:none; border-radius:8px; background:#fff;" '
        f'sandbox="allow-scripts allow-same-origin">'
        f'</iframe>'
    )
```

---

### Phase 7: Chainlit App Entry Point (`app.py`)

This is the core of the application. Chainlit's `@cl.on_*` decorators handle
the session lifecycle. The Pydantic AI agent's `run_mcp_servers()` context
manager keeps the MCP subprocess connections alive for the whole session.

```python
# app.py
import chainlit as cl
from contextlib import asynccontextmanager

from orionbelt_chat.agent import make_agent
from orionbelt_chat.providers import (
    PROVIDER_LABELS, PROVIDER_MODELS, default_model_for
)
from orionbelt_chat.chart_renderer import render_chart_if_present
from orionbelt_chat.settings import settings


# ── Chainlit Chat Settings (sidebar UI) ───────────────────────────────────

def build_chat_settings() -> list[cl.input_widget.InputWidget]:
    """Define the settings panel shown in the Chainlit sidebar."""
    return [
        cl.Select(
            id="provider",
            label="LLM Provider",
            values=list(PROVIDER_LABELS.keys()),
            initial_value=settings.default_provider,
            tooltip="Select your AI provider",
        ),
        cl.Select(
            id="model",
            label="Model",
            values=PROVIDER_MODELS.get(settings.default_provider, []),
            initial_value=default_model_for(settings.default_provider),
        ),
        cl.TextInput(
            id="custom_model",
            label="Custom model name (overrides above)",
            initial="",
            placeholder="e.g. openrouter:google/gemini-2.5-pro or mlx-community/MyModel-4bit",
            tooltip="Leave empty to use the model selected above",
        ),
        cl.TextInput(
            id="system_prompt_extra",
            label="Additional system prompt instructions",
            initial="",
            placeholder="Optional: add context about your data or preferences",
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
    cl.user_session.set("history", [])

    # Create agent and start MCP servers
    await _init_agent(provider, model)

    await cl.Message(
        content=(
            f"**OrionBelt Analytics Assistant** ready.\n\n"
            f"Provider: `{provider}` | Model: `{model}`\n\n"
            f"Connected MCP servers:\n"
            f"- `orionbelt-analytics`\n"
            f"- `orionbelt-semantic-layer`\n\n"
            f"Ask me anything about your data."
        )
    ).send()


async def _init_agent(provider: str, model: str):
    """Create agent, enter MCP context, store in session."""
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
    except Exception as e:
        cl.user_session.set("agent", None)
        cl.user_session.set("mcp_context", None)
        await cl.Message(
            content=f"⚠️ Failed to initialise agent: {e}",
            author="System",
        ).send()


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
    cl.user_session.set("history", [])   # clear history on model change

    await cl.Message(
        content=f"Switching to `{provider}` / `{model}`...",
        author="System",
    ).send()

    await _init_agent(provider, model)

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

    history = cl.user_session.get("history", [])

    # Build message history for Pydantic AI
    # Pydantic AI expects MessageHistory from previous runs
    # We store the raw RunResult.all_messages() and pass them back
    msg_history = cl.user_session.get("pydantic_history", None)

    # Prepare the response message (streams tokens into it)
    response_msg = cl.Message(content="")
    await response_msg.send()

    # Track tool calls for collapsible steps
    active_step: cl.Step | None = None
    chart_elements: list[cl.Html] = []

    try:
        async with agent.run_stream(
            message.content,
            message_history=msg_history,
        ) as streamed:

            async for event in streamed.stream_events():
                event_type = type(event).__name__

                # ── Streaming text tokens ──────────────────────────
                if event_type == "PartDeltaEvent":
                    delta = getattr(event.delta, "content_delta", None)
                    if delta:
                        await response_msg.stream_token(delta)

                # ── Tool call start ────────────────────────────────
                elif event_type == "PartStartEvent":
                    part = event.part
                    if hasattr(part, "tool_name"):
                        # Close previous step if open
                        if active_step:
                            await active_step.__aexit__(None, None, None)
                        active_step = cl.Step(
                            name=part.tool_name,
                            type="tool",
                            show_input=True,
                        )
                        await active_step.__aenter__()
                        if hasattr(part, "args"):
                            active_step.input = str(part.args)

                # ── Tool result ────────────────────────────────────
                elif event_type == "FinalResultEvent":
                    pass  # handled by streaming above

            # Finalise streaming
            await response_msg.update()

            # Close any open tool step
            if active_step:
                await active_step.__aexit__(None, None, None)

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
                        # Get the MCP server that owns this tool
                        # (simplified: try analytics first, then semantic layer)
                        for server in agent.toolsets:
                            chart_el = await render_chart_if_present(
                                content, server
                            )
                            if chart_el:
                                chart_elements.append(chart_el)
                                break

            # Send charts as separate messages with elements
            if chart_elements:
                chart_msg = cl.Message(
                    content="📊 Interactive chart:",
                    elements=chart_elements,
                )
                await chart_msg.send()

    except Exception as e:
        await cl.Message(
            content=f"❌ Error: {e}",
            author="System",
        ).send()
        if active_step:
            try:
                await active_step.__aexit__(type(e), e, None)
            except Exception:
                pass
```

---

### Phase 8: Chainlit Configuration

**`chainlit.md`** — shown as welcome message:
```markdown
# OrionBelt Analytics Assistant

Ask questions about your data in natural language.

**Connected tools:**
- OrionBelt Semantic Layer — OBML model management, query compilation
- OrionBelt Analytics — schema analysis, SQL execution, chart generation

**Examples:**
- "What OBML models are available?"
- "Show me revenue by product category for last quarter as a bar chart"
- "Analyze the schema of the orionbelt_1 database"
- "Generate an ontology for the sales schema"
```

**`chainlit.yaml`**:
```yaml
# chainlit.yaml
project:
  name: "OrionBelt Chat"

ui:
  name: "OrionBelt Chat"
  default_collapse_content: false
  hide_cot: false              # show chain-of-thought steps (tool calls)

features:
  prompt_playground: false
  speech_to_text: false
```

---

### Phase 9: Environment Configuration (`.env.example`)

```bash
# ── LLM Providers ──────────────────────────────────────────────
# Primary cloud provider (recommended)
OPENROUTER_API_KEY=sk-or-...
OPENROUTER_DEFAULT_MODEL=anthropic/claude-sonnet-4-5

# Local: mlx-openai-server on Apple Silicon (start with mlx-openai-server)
MLX_BASE_URL=http://localhost:8000/v1
MLX_DEFAULT_MODEL=mlx-community/Qwen2.5-14B-Instruct-4bit

# Local: Ollama (optional)
OLLAMA_BASE_URL=http://localhost:11434/v1
OLLAMA_DEFAULT_MODEL=qwen2.5:14b

# Direct provider keys (optional, bypass OpenRouter)
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...

# Default on startup
DEFAULT_PROVIDER=openrouter

# ── OrionBelt services ──────────────────────────────────────────
ORIONBELT_API_URL=http://localhost:8000

# ── MCP server configuration ────────────────────────────────────
# Transport: "stdio" (subprocess) or "http" (running server)
ANALYTICS_TRANSPORT=stdio
ANALYTICS_SERVER_DIR=../orionbelt-analytics
ANALYTICS_HTTP_URL=http://localhost:8001/mcp

SEMANTIC_TRANSPORT=stdio
SEMANTIC_LAYER_SERVER_DIR=../orionbelt-semantic-layer
SEMANTIC_HTTP_URL=http://localhost:8002/mcp
```

---

## Key Technical Notes

### Pydantic AI MCP Lifecycle

Pydantic AI's `MCPServerStdio` starts the MCP subprocess when entering `agent.run_mcp_servers()`. This must stay alive for the full Chainlit session — that's why `_init_agent()` enters the context manager and stores it in the session, and `on_chat_end` exits it cleanly.

```python
# The pattern used per session:
agent = make_agent(provider, model)
mcp_ctx = agent.run_mcp_servers()
await mcp_ctx.__aenter__()   # starts both subprocess MCP servers
# ... all agent.run_stream() calls happen here ...
await mcp_ctx.__aexit__(...)  # stops subprocesses on session end
```

### Streaming with Pydantic AI

Pydantic AI provides `agent.run_stream()` which returns a `StreamedRunResult`. Use `stream_events()` to get fine-grained events:

- `PartStartEvent` with `tool_name` → new tool call starting → open a `cl.Step`
- `PartDeltaEvent` with `content_delta` → text token → `response_msg.stream_token()`
- Tool results → available in `streamed.all_messages()` after completion

### Multi-turn Context

Pydantic AI tracks conversation history via `streamed.all_messages()`. Pass this back as `message_history` on the next `run_stream()` call. This gives the LLM full context across turns without re-sending raw text — it uses the structured message format the model expects.

### mlx-openai-server Setup

Start before launching the chat client:
```bash
mlx-openai-server launch \
  --model-path mlx-community/Qwen2.5-14B-Instruct-4bit \
  --model-type lm \
  --enable-auto-tool-choice \
  --port 8000
```

The chat client connects to `http://localhost:8000/v1` via `OpenAIModel` with `OpenAIProvider`. Tool calling works if `--enable-auto-tool-choice` is set and the model supports it. Check `mlx-community` for models with tool support (Qwen2.5, Llama 3.x, Mistral).

### Chart Rendering

When `orionbelt-analytics` returns a tool result with a `ui://` resource URI
(MCP Apps pattern from `PLAN_mcp_apps_charts.md`), `render_chart_if_present()`
fetches the HTML and wraps it in a sandboxed iframe injected as a `cl.Html` element.
This renders inline in the Chainlit message flow with full Plotly interactivity.

---

## Implementation Order

1. [ ] Scaffold project: `uv init orionbelt-chat`, add `pyproject.toml`
2. [ ] Implement `settings.py` and verify `.env` loading
3. [ ] Implement `providers.py` — test each provider with a simple `agent.run()`
4. [ ] Implement `mcp_servers.py` — verify both MCP servers connect and list tools
5. [ ] Implement `agent.py` — verify tool calls flow end-to-end
6. [ ] Build minimal `app.py` — `on_start` + `on_message` with streaming, no charts yet
7. [ ] Add `cl.ChatSettings` panel — provider/model switcher working
8. [ ] Add `chart_renderer.py` — wire up after `execute_chart` tool works in analytics
9. [ ] Add `chainlit.md` and `chainlit.yaml` — branding and welcome text
10. [ ] Test mlx-openai-server path with a local model
11. [ ] Test OpenRouter path with `anthropic/claude-sonnet-4-5` and `deepseek/deepseek-r1`
12. [ ] Test full OrionBelt workflow: model list → compile query → execute chart → render

---

## Future Extensions

| Feature | Approach |
|---|---|
| **Conversation history persistence** | `chainlit.data_layer` with SQLite or Postgres |
| **User authentication** | `chainlit.yaml` auth section (password / OAuth) |
| **Model cost display** | OpenRouter returns usage in response; display in step footer |
| **API key input in UI** | `cl.TextInput` in settings for keys (masked) |
| **orionbelt-langchain integration** | Add as a third MCP server via `MCPServerStreamableHTTP` |
| **Docker deployment** | `Dockerfile` + `docker-compose.yml` with all three services |
| **Tool approval UI** | Pydantic AI's human-in-the-loop + `cl.AskActionMessage` |
| **Chainlit Copilot embed** | Embed OrionBelt Chat in the OrionBelt Analytics web UI |

---

## Critical Implementation Notes

### 1. MCP Lifecycle — Get This Right First

The MCP lifecycle pattern is the most important thing to get right before touching
the UI. `agent.run_mcp_servers()` must be entered **once per Chainlit session** and
kept alive for the entire session. That is what `_init_agent()` does by storing the
async context manager in `cl.user_session`:

```python
mcp_ctx = agent.run_mcp_servers()
await mcp_ctx.__aenter__()          # starts both MCP subprocesses
cl.user_session.set("mcp_context", mcp_ctx)
# ... all agent.run_stream() calls happen within this context ...
await mcp_ctx.__aexit__(None, None, None)   # on_chat_end
```

If you enter and exit the context on every message instead, the MCP subprocesses
restart on every turn — slow, and stateful servers lose their connection state.

### 2. mlx-openai-server — Enable Tool Calling Explicitly

Start `mlx-openai-server` with `--enable-auto-tool-choice`, otherwise the model
will not call MCP tools at all:

```bash
mlx-openai-server launch \
  --model-path mlx-community/Qwen2.5-14B-Instruct-4bit \
  --model-type lm \
  --enable-auto-tool-choice \
  --port 8000
```

Not all MLX models support tool calling. **Safe starting points** from `mlx-community`:
- `Qwen2.5-14B-Instruct-4bit` — strong tool calling, good context window
- `Llama-3.3-70B-Instruct-4bit` — best quality, needs 48GB+ unified memory
- `mistral-7b-instruct-v0.3-4bit` — lighter, but tool calling less reliable

Avoid base models (no `-Instruct` suffix) — they do not follow tool calling format.

### 3. Streaming Events — Why `stream_events()` Not `stream_text()`

The agent loop uses `stream_events()` rather than the simpler `stream_text()` because
we need to intercept `PartStartEvent` to detect tool calls and open `cl.Step` blocks.
This is what produces the collapsible "🔧 compile_query(…)" steps in the chat —
Chainlit's killer feature for agentic UIs that shows the user exactly what tools
are being called and why.

If you only need text streaming and do not care about tool step visibility, you can
simplify to:

```python
async with agent.run_stream(message.content, message_history=msg_history) as r:
    async for chunk in r.stream_text(delta=True):
        await response_msg.stream_token(chunk)
```

But the full `stream_events()` loop is recommended for production.

### 4. OpenRouter — Fastest Path to First Working Demo

OpenRouter is the fastest path to a working demo. Set two environment variables and
you immediately have access to every model — including Claude for direct comparison
against your local MLX model:

```bash
OPENROUTER_API_KEY=sk-or-...
DEFAULT_PROVIDER=openrouter
```

Then test with `anthropic/claude-sonnet-4-5` first (most reliable tool calling),
then try `deepseek/deepseek-r1` or `meta-llama/llama-3.3-70b-instruct` for
comparison. Only move to local MLX once the cloud path is fully working end-to-end.

---

## References

| Resource | URL |
|---|---|
| Chainlit docs | https://docs.chainlit.io |
| Chainlit `cl.Step` | https://docs.chainlit.io/concepts/step |
| Chainlit `cl.Html` | https://docs.chainlit.io/api-reference/elements/html |
| Chainlit `cl.ChatSettings` | https://docs.chainlit.io/api-reference/chat-settings |
| Pydantic AI MCP client | https://ai.pydantic.dev/mcp/client/ |
| Pydantic AI streaming | https://ai.pydantic.dev/agents/#streaming |
| Pydantic AI OpenRouter | https://ai.pydantic.dev/models/openrouter/ |
| OpenRouter model list | https://openrouter.ai/models |
| mlx-openai-server | https://github.com/cubist38/mlx-openai-server |
| MCP Apps plan | PLAN_mcp_apps_charts.md (this repo) |
