# OrionBelt Chat

**Chainlit + Pydantic AI chat client for OrionBelt Analytics**

A standalone chat application that connects to OrionBelt Analytics and Semantic Layer MCP servers with support for multiple LLM providers (cloud and local).

## Features

- 🤖 **Multi-provider LLM support**: OpenRouter, MLX (Apple Silicon), Ollama, Anthropic, OpenAI
- 🔧 **MCP integration**: Connects to orionbelt-analytics and orionbelt-semantic-layer as tools
- 📊 **Interactive charts**: Renders Plotly charts inline via MCP Apps
- ⚡ **Streaming**: Real-time token streaming with tool call visibility
- 🎯 **Multi-turn context**: Full conversation history management

## Quick Start

### Prerequisites

- Python 3.11+
- `uv` package manager ([install](https://github.com/astral-sh/uv))
- OrionBelt Analytics and Semantic Layer repos cloned alongside this one

### Installation

```bash
# Clone the repository (if not already cloned)
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

DEFAULT_PROVIDER=mlx
```

**Option 3: Ollama local (cross-platform)**
```bash
# Start Ollama first: ollama serve
DEFAULT_PROVIDER=ollama
```

### Run

```bash
uv run chainlit run app.py --watch
```

Open http://localhost:8080 in your browser.

## Architecture

```
┌─────────────────────────────────────────────┐
│          OrionBelt Chat (Chainlit)          │
│                                             │
│  ┌──────────┐         ┌──────────────────┐ │
│  │  Chat UI │         │  Pydantic AI     │ │
│  │          │────────>│  Agent + MCP     │ │
│  └──────────┘         └──────────────────┘ │
└─────────────────────────────────────────────┘
         │                      │
         │                      ├──> orionbelt-analytics (MCP)
         │                      └──> orionbelt-semantic-layer (MCP)
         │
         └──> LLM Provider (OpenRouter/MLX/Ollama/etc)
```

## Usage Examples

**Query data:**
```
Show me revenue by product category as a bar chart
```

**Explore models:**
```
What OBML models are available?
```

**Schema analysis:**
```
Analyze the schema of the sales database
```

## Development

```bash
# Install dev dependencies
uv sync --group dev

# Run tests
uv run pytest

# Format code
uv run ruff format

# Lint
uv run ruff check
```

## Provider Details

### OpenRouter
- Access 300+ models via single API
- Best reliability for tool calling
- Recommended: `anthropic/claude-sonnet-4-5`

### MLX (Apple Silicon)
- Runs locally on Mac with Apple Silicon
- Requires `mlx-openai-server`
- Recommended: `mlx-community/Qwen2.5-14B-Instruct-4bit`

### Ollama
- Cross-platform local inference
- Easiest local setup
- Recommended: `qwen2.5:14b`

## Troubleshooting

**MCP servers not connecting:**
- Ensure `ANALYTICS_SERVER_DIR` and `SEMANTIC_LAYER_SERVER_DIR` point to correct paths
- Check that both repos have dependencies installed (`uv sync`)

**Charts not rendering:**
- Verify `orionbelt-analytics` has MCP Apps support
- Check browser console for errors

**MLX model not calling tools:**
- Ensure `--enable-auto-tool-choice` flag is set
- Use an instruct-tuned model (with `-Instruct` suffix)

## License

Part of the OrionBelt platform. See individual component licenses.

## Links

- [OrionBelt Analytics](https://github.com/ralfbecher/orionbelt-analytics)
- [OrionBelt Semantic Layer](https://github.com/ralfbecher/orionbelt-semantic-layer)
- [Chainlit Documentation](https://docs.chainlit.io)
- [Pydantic AI Documentation](https://ai.pydantic.dev)
