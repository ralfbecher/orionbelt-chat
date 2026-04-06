<!-- mcp-name: io.github.ralfbecher/orionbelt-chat -->
<p align="center">
  <img src="https://raw.githubusercontent.com/ralfbecher/orionbelt-analytics/main/assets/ORIONBELT_Logo.png" alt="OrionBelt Logo" width="400">
</p>

<h1 align="center">OrionBelt Chat</h1>

<p align="center"><strong>AI-powered chat interface for OrionBelt Analytics & Semantic Layer</strong></p>

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: BSL 1.1](https://img.shields.io/badge/License-BSL_1.1-orange.svg)](https://github.com/ralfbecher/orionbelt-chat/blob/main/LICENSE)
[![Chainlit](https://img.shields.io/badge/Chainlit-2.0+-blue)](https://chainlit.io)
[![Pydantic AI](https://img.shields.io/badge/Pydantic_AI-0.0.60+-blue)](https://ai.pydantic.dev)

[![OpenRouter](https://img.shields.io/badge/OpenRouter-300%2B_Models-blueviolet)](https://openrouter.ai)
[![MLX](https://img.shields.io/badge/MLX-Apple_Silicon-black)](https://github.com/ml-explore/mlx)
[![Ollama](https://img.shields.io/badge/Ollama-Local_LLMs-green)](https://ollama.com)

A production-ready chat application that connects to OrionBelt Analytics and OrionBelt Semantic Layer MCP servers, providing a conversational interface for database analysis, semantic modeling, and interactive data visualization. Built with Chainlit and Pydantic AI, supporting multiple LLM providers (cloud and local).

> **Better Together:** Works seamlessly with [**OrionBelt Analytics**](https://github.com/ralfbecher/orionbelt-analytics) and [**OrionBelt Semantic Layer**](https://github.com/ralfbecher/orionbelt-semantic-layer). Connect to both MCP servers simultaneously for schema-aware ontology generation, semantic modeling, guaranteed-correct SQL compilation, and interactive chart rendering.

## 🌟 Key Features

### 🤖 Multi-Provider LLM Support

- **OpenRouter** - Access 300+ models via single API (recommended for production)
- **MLX** - Local inference on Apple Silicon with mlx-openai-server
- **Ollama** - Cross-platform local inference with easy setup
- **Anthropic** - Direct API access (bypass OpenRouter)
- **OpenAI** - Direct API access (bypass OpenRouter)

### 🔧 MCP Integration

- **Dual MCP server support** - Connect to Analytics and Semantic Layer simultaneously
- **Tool visibility** - Collapsible steps show tool calls with arguments and results
- **Streaming responses** - Real-time token streaming with visual feedback
- **Multi-turn context** - Full conversation history management with Pydantic AI

### 📊 Interactive Charts

- **MCP Apps rendering** - Inline Plotly charts via ui:// resource URIs
- **Sandboxed iframes** - Secure chart rendering with base64 data URIs
- **Multiple chart types** - Bar, line, scatter, heatmap with auto-detection
- **Auto-format detection** - Time series data automatically switches to line charts

### ⚡ Real-Time Streaming

- **Token-by-token streaming** - Smooth response rendering as model generates
- **Tool call tracking** - Visual feedback for each MCP tool invocation
- **Error handling** - Graceful failures with clear error messages
- **Progress indicators** - Loading states during long-running operations

### 🎨 Chainlit UI

- **Settings panel** - Switch providers and models on the fly
- **Custom model input** - Override default models with specific versions
- **Message history** - Persistent conversation context across sessions
- **Responsive design** - Works on desktop and mobile browsers

## 🚀 Quick Start

### Prerequisites

- **Python 3.11+** (3.13 recommended)
- **uv** package manager ([install](https://github.com/astral-sh/uv))
- **OrionBelt Analytics** and **Semantic Layer** repos cloned alongside this one

### Installation

```bash
# Clone the repository
cd orionbelt-chat

# Install dependencies
uv sync

# Copy environment template
cp .env.example .env

# Edit .env and add your API keys
```

### Configuration

Edit `.env` and configure your LLM provider:

**Option 1: OpenRouter (recommended for cloud)**

```bash
OPENROUTER_API_KEY=sk-or-v1-...
OPENROUTER_DEFAULT_MODEL=anthropic/claude-sonnet-4-5
DEFAULT_PROVIDER=openrouter
```

**Option 2: MLX local (Apple Silicon)**

```bash
# Start mlx-openai-server first:
mlx-openai-server launch \
  --model-path mlx-community/Qwen2.5-14B-Instruct-4bit \
  --model-type lm \
  --enable-auto-tool-choice \
  --port 8000

MLX_DEFAULT_MODEL=mlx-community/Qwen2.5-14B-Instruct-4bit
DEFAULT_PROVIDER=mlx
```

**Option 3: Ollama local (cross-platform)**

```bash
# Start Ollama first: ollama serve
OLLAMA_DEFAULT_MODEL=qwen2.5:14b
DEFAULT_PROVIDER=ollama
```

**MCP Server Paths:**

```bash
# Ensure these point to your local repos
ANALYTICS_SERVER_DIR=../orionbelt-analytics
SEMANTIC_LAYER_SERVER_DIR=../orionbelt-semantic-layer-mcp
```

### Run

```bash
uv run chainlit run app.py --watch
```

Open **http://localhost:8080** in your browser.

## 📖 Usage Examples

**Connect to database:**

```
Connect to my PostgreSQL database at localhost
```

**Schema analysis:**

```
Analyze the schema and show me all tables with their relationships
```

**Query with charts:**

```
Show me revenue by product category as a bar chart
```

**Explore semantic models:**

```
What OBML models are available in the semantic layer?
```

**Generate OBML model:**

```
Create an OBML model for customer analytics with metrics for revenue, order count, and average order value
```

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────────────┐
│          OrionBelt Chat (Chainlit + Pydantic AI)             │
│                                                              │
│  ┌──────────┐         ┌──────────────────────────────────┐  │
│  │  Chat UI │         │  Pydantic AI Agent + MCP Client │  │
│  │          │────────>│  - Multi-turn context          │  │
│  │ Chainlit │         │  - Streaming events            │  │
│  │  2.0+    │         │  - Tool orchestration          │  │
│  └──────────┘         └──────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
         │                      │
         │                      ├──> orionbelt-analytics (MCP stdio)
         │                      │    - Schema analysis
         │                      │    - Ontology generation
         │                      │    - SQL execution
         │                      │    - Interactive charts
         │                      │
         │                      └──> orionbelt-semantic-layer (MCP stdio)
         │                           - OBML model management
         │                           - Semantic query compilation
         │                           - Guaranteed-correct SQL
         │
         └──> LLM Provider (OpenRouter/MLX/Ollama/Anthropic/OpenAI)
```

**Key Components:**

- **Chainlit 2.0+** - Chat UI framework with streaming, steps, and settings
- **Pydantic AI 0.0.60+** - Agent framework with MCP client integration
- **MCP Stdio Transport** - Subprocess-based MCP server communication
- **Chart Renderer** - MCP Apps ui:// resource handler with iframe sandboxing

## 🛠️ Development

```bash
# Install dev dependencies
uv sync --group dev

# Run tests (when available)
uv run pytest

# Format code
uv run ruff format

# Lint
uv run ruff check --fix
```

## 📦 Provider Details

### OpenRouter

- **Access**: 300+ models via single API
- **Reliability**: Best tool-calling support across vendors
- **Recommended models**:
  - `anthropic/claude-sonnet-4-5` - Best reasoning and tool use
  - `anthropic/claude-opus-4` - Maximum intelligence
  - `google/gemini-2.5-pro` - Fast and cost-effective
- **Setup**: Get API key at [openrouter.ai](https://openrouter.ai)

### MLX (Apple Silicon)

- **Platform**: Mac with Apple Silicon (M1/M2/M3/M4)
- **Requirements**: `mlx-openai-server`
- **Recommended models**:
  - `mlx-community/Qwen2.5-14B-Instruct-4bit` - Excellent tool use
  - `mlx-community/Qwen2.5-32B-Instruct-4bit` - Better reasoning (requires 32GB+ RAM)
- **Setup**: Install with `pip install mlx-openai-server`
- **Notes**: Must use `--enable-auto-tool-choice` flag for tool calling

### Ollama

- **Platform**: Cross-platform (Mac/Linux/Windows)
- **Ease of use**: Simplest local setup
- **Recommended models**:
  - `qwen2.5:14b` - Good balance of speed and accuracy
  - `qwen2.5:32b` - Better reasoning (requires 32GB+ RAM)
- **Setup**: Download from [ollama.com](https://ollama.com)
- **Notes**: Built-in tool calling support with instruct models

## 🐛 Troubleshooting

### MCP servers not connecting

**Symptom:** Agent initialization fails on startup

**Solutions:**
- Ensure `ANALYTICS_SERVER_DIR` and `SEMANTIC_LAYER_SERVER_DIR` point to correct paths
- Check that both repos have dependencies installed (`uv sync`)
- Verify both MCP servers can start independently (`uv run server.py`)
- Check for port conflicts if using HTTP transport (future feature)

### Charts not rendering

**Symptom:** Charts don't appear after generate_chart tool call

**Solutions:**
- Verify `orionbelt-analytics` has MCP Apps support (v1.2.0+)
- Check browser console for iframe or CSP errors
- Ensure chart data is valid JSON in tool result
- Verify analytics server returned ui:// resource URI

### MLX model not calling tools

**Symptom:** Model ignores tools and tries to answer directly

**Solutions:**
- Ensure `--enable-auto-tool-choice` flag is set when starting mlx-openai-server
- Use an instruct-tuned model (with `-Instruct` suffix)
- Try a different model (Qwen2.5 series has best tool support)
- Check mlx-openai-server logs for errors

### Streaming stops or hangs

**Symptom:** Response stops mid-generation

**Solutions:**
- Check MCP server logs for errors
- Verify tool calls are completing successfully
- Increase timeout settings if using slow local models
- Restart both MCP servers and the chat app

## 📄 License

Licensed under the **Business Source License 1.1** (BSL 1.1).

- **Production use allowed** for internal/personal use
- **Commercial embedding/SaaS restrictions** - contact licensing@ralforion.com
- **Change Date**: 2030-04-05
- **Change License**: Apache 2.0

See [LICENSE](./LICENSE) for full terms.

## 🔗 Links

### OrionBelt Platform
- [**OrionBelt Analytics**](https://github.com/ralfbecher/orionbelt-analytics) - MCP server for database analysis and ontology generation
- [**OrionBelt Semantic Layer**](https://github.com/ralfbecher/orionbelt-semantic-layer) - MCP server for OBML models and semantic SQL compilation
- [**OrionBelt Ontology Builder**](https://github.com/ralfbecher/orionbelt-ontology-builder) - Visual ontology editor (Streamlit app)

### Frameworks
- [**Chainlit**](https://docs.chainlit.io) - Chat UI framework
- [**Pydantic AI**](https://ai.pydantic.dev) - Agent framework with MCP support
- [**Model Context Protocol**](https://modelcontextprotocol.io) - Tool integration standard

### LLM Providers
- [**OpenRouter**](https://openrouter.ai) - Unified API for 300+ models
- [**MLX**](https://github.com/ml-explore/mlx) - Apple Silicon inference
- [**Ollama**](https://ollama.com) - Local LLM runtime

---

<p align="center">
  <a href="https://ralforion.com">
    <img src="https://raw.githubusercontent.com/ralfbecher/orionbelt-analytics/main/assets/RALFORION_doo_Logo.png" alt="RALFORION d.o.o." height="60">
  </a>
</p>

<p align="center">
  <strong>Built by RALFORION d.o.o.</strong><br>
  Enterprise-grade data intelligence solutions
</p>
