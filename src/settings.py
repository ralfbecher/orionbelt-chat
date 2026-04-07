"""Configuration management via Pydantic Settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """OrionBelt Chat configuration loaded from environment variables or .env file."""

    # ── LLM providers ──────────────────────────────────────────
    # Primary: OpenRouter
    openrouter_api_key: str = ""
    openrouter_default_model: str = "anthropic/claude-sonnet-4-5"

    # Local: mlx-openai-server (primary local option for Apple Silicon)
    mlx_base_url: str = "http://localhost:8000/v1"
    mlx_default_model: str = "mlx-community/Qwen2.5-14B-Instruct-4bit"

    # Local: Ollama (cross-platform fallback)
    ollama_base_url: str = "http://localhost:11434/v1"
    ollama_default_model: str = "qwen2.5:14b"

    # Direct provider keys (optional, bypass OpenRouter)
    anthropic_api_key: str = ""
    openai_api_key: str = ""

    # ── Default provider on startup ────────────────────────────
    # Values: "openrouter" | "mlx" | "ollama" | "anthropic" | "openai"
    default_provider: str = "openrouter"
    default_model: str = ""  # if empty, uses provider default above

    # ── MCP servers ─────────────────────────────────────────
    # Each server can be configured as either:
    #   - a local directory path  → stdio transport (spawns subprocess)
    #   - an HTTP(S) URL          → Streamable HTTP transport (remote)
    # Set the *_dir variable to a path or URL accordingly.
    analytics_server_dir: str = "../orionbelt-analytics"
    semantic_layer_server_dir: str = "../orionbelt-semantic-layer-mcp"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


# Global settings instance
settings = Settings()
