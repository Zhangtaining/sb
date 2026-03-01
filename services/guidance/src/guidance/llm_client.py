"""GymLLMClient — thin facade over the configured LLM provider."""
from __future__ import annotations

from guidance.config import GuidanceConfig
from guidance.providers import create_llm_provider
from guidance.providers.base import BaseLLMProvider


class GymLLMClient:
    """Wraps the active LLM provider with the gym-specific interface.

    The concrete provider (Anthropic, Gemini, …) is chosen at construction
    time via ``config.llm_provider``.  Callers never need to know which
    backend is in use.
    """

    def __init__(self, config: GuidanceConfig) -> None:
        self._provider: BaseLLMProvider = create_llm_provider(
            provider=config.llm_provider,
            model=config.llm_model,
            max_tokens=config.llm_max_tokens,
            anthropic_api_key=config.anthropic_api_key,
            gemini_api_key=config.gemini_api_key,
        )

    @property
    def model_name(self) -> str:
        return self._provider.model_name

    async def generate_guidance(self, system_prompt: str, user_message: str) -> str | None:
        """Generate a coaching message.  Returns None on error — never raises."""
        return await self._provider.generate(system_prompt, user_message)
