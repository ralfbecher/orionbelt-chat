"""LLM provider resolution for Pydantic AI."""

from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.models.anthropic import AnthropicModel

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

    Args:
        provider: Provider name ("openrouter", "mlx", "ollama", "anthropic", "openai")
        model: Model identifier string

    Returns:
        Pydantic AI model instance configured for the provider

    Raises:
        ValueError: For unknown providers or missing credentials
    """
    match provider:
        case "openrouter":
            if not settings.openrouter_api_key:
                raise ValueError("OPENROUTER_API_KEY not set in environment")
            return OpenAIModel(
                model,
                base_url="https://openrouter.ai/api/v1",
                api_key=settings.openrouter_api_key,
            )

        case "mlx":
            # mlx-openai-server exposes an OpenAI-compatible endpoint
            return OpenAIModel(
                model,
                base_url=settings.mlx_base_url,
                api_key="mlx-local",  # ignored by local server
            )

        case "ollama":
            return OpenAIModel(
                model,
                base_url=settings.ollama_base_url,
                api_key="ollama",  # ignored by local server
            )

        case "anthropic":
            if not settings.anthropic_api_key:
                raise ValueError("ANTHROPIC_API_KEY not set in environment")
            return AnthropicModel(
                model,
                api_key=settings.anthropic_api_key,
            )

        case "openai":
            if not settings.openai_api_key:
                raise ValueError("OPENAI_API_KEY not set in environment")
            return OpenAIModel(
                model,
                api_key=settings.openai_api_key,
            )

        case _:
            raise ValueError(f"Unknown provider: {provider!r}")


def default_model_for(provider: str) -> str:
    """Return the default model string for a provider."""
    # Use global default_model override if set
    if settings.default_model:
        return settings.default_model

    defaults = {
        "openrouter": settings.openrouter_default_model,
        "mlx": settings.mlx_default_model,
        "ollama": settings.ollama_default_model,
        "anthropic": "claude-sonnet-4-6",
        "openai": "gpt-4o",
    }
    return defaults.get(provider, "")
