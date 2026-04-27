# CLAUDE.md

## Project

OrionBelt Chat — Chainlit + Pydantic AI chat client for OrionBelt Analytics & Semantic Layer MCP servers.

## Code Review

Code is reviewed with OpenAI Codex. Write clean, well-structured code that passes automated review.

## Git Workflow

- Never commit directly to main — always create feature/ or fix/ branches
- Version must be bumped in three places: `pyproject.toml`, `public/header.js`, `README.md` badge

## Stack

- Python 3.11+, Chainlit, Pydantic AI
- MCP servers: orionbelt-analytics (stdio/HTTP), orionbelt-semantic-layer (HTTP)
- LLM providers: OpenRouter, MLX, Ollama, Anthropic, OpenAI
