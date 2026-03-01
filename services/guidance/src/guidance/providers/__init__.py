"""LLM provider factory."""
from __future__ import annotations

from guidance.providers.base import BaseLLMProvider


def create_llm_provider(
    provider: str,
    model: str,
    max_tokens: int,
    anthropic_api_key: str = "",
    gemini_api_key: str = "",
) -> BaseLLMProvider:
    """Instantiate the correct LLM provider based on the provider name.

    Args:
        provider: ``"anthropic"`` or ``"gemini"``.
        model: Model ID string (e.g. ``"claude-sonnet-4-6"`` or ``"gemini-2.0-flash"``).
        max_tokens: Maximum tokens for the response.
        anthropic_api_key: Required when provider is ``"anthropic"``.
        gemini_api_key: Required when provider is ``"gemini"``.

    Returns:
        A ready-to-use :class:`BaseLLMProvider` instance.

    Raises:
        ValueError: If ``provider`` is not recognised.
    """
    if provider == "anthropic":
        from guidance.providers.anthropic import AnthropicProvider
        return AnthropicProvider(api_key=anthropic_api_key, model=model, max_tokens=max_tokens)
    if provider == "gemini":
        from guidance.providers.gemini import GeminiProvider
        return GeminiProvider(api_key=gemini_api_key, model=model, max_tokens=max_tokens)
    raise ValueError(f"Unknown LLM provider: {provider!r}. Choose 'anthropic' or 'gemini'.")
