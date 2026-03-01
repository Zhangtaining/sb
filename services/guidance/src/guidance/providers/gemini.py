"""Google Gemini provider implementation."""
from __future__ import annotations

from google import genai
from google.genai import types

from gym_shared.logging import get_logger

from guidance.providers.base import BaseLLMProvider

log = get_logger(__name__)


class GeminiProvider(BaseLLMProvider):
    """LLM provider backed by Google Gemini models."""

    def __init__(self, api_key: str, model: str, max_tokens: int) -> None:
        self._client = genai.Client(api_key=api_key)
        self._model = model
        self._max_tokens = max_tokens

    @property
    def model_name(self) -> str:
        return self._model

    async def generate(self, system_prompt: str, user_message: str) -> str | None:
        try:
            response = await self._client.aio.models.generate_content(
                model=self._model,
                contents=user_message,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    max_output_tokens=self._max_tokens,
                ),
            )
            text = response.text or ""
            log.debug("llm_response", provider="gemini", model=self._model)
            return text.strip() or None
        except Exception as exc:
            log.error("llm_unexpected_error", provider="gemini", error=str(exc))
            return None
