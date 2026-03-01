"""Anthropic Claude provider implementation."""
from __future__ import annotations

import anthropic

from gym_shared.logging import get_logger

from guidance.providers.base import BaseLLMProvider

log = get_logger(__name__)


class AnthropicProvider(BaseLLMProvider):
    """LLM provider backed by Anthropic Claude models."""

    def __init__(self, api_key: str, model: str, max_tokens: int) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._model = model
        self._max_tokens = max_tokens

    @property
    def model_name(self) -> str:
        return self._model

    async def generate(self, system_prompt: str, user_message: str) -> str | None:
        try:
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
            )
            text = response.content[0].text if response.content else ""
            log.debug(
                "llm_response",
                provider="anthropic",
                model=self._model,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
            )
            return text.strip() or None
        except anthropic.APIError as exc:
            log.error("llm_api_error", provider="anthropic", error=str(exc), status=getattr(exc, "status_code", None))
            return None
        except Exception as exc:
            log.error("llm_unexpected_error", provider="anthropic", error=str(exc))
            return None
