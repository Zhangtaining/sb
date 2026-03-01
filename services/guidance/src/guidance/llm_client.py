"""Anthropic LLM client wrapper for the guidance service."""
from __future__ import annotations

import anthropic

from gym_shared.logging import get_logger

log = get_logger(__name__)


class GymLLMClient:
    """Async wrapper around AsyncAnthropic for gym coaching use cases.

    Args:
        api_key: Anthropic API key.
        model: Model ID (default: claude-sonnet-4-6).
        max_tokens: Maximum tokens in the response.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-6",
        max_tokens: int = 1024,
    ) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._model = model
        self._max_tokens = max_tokens

    async def generate_guidance(
        self,
        system_prompt: str,
        user_message: str,
    ) -> str | None:
        """Call the LLM and return the text response.

        Returns None on API error — does not raise.
        """
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
                model=self._model,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
            )
            return text.strip() or None
        except anthropic.APIError as exc:
            log.error("llm_api_error", error=str(exc), status=getattr(exc, "status_code", None))
            return None
        except Exception as exc:
            log.error("llm_unexpected_error", error=str(exc))
            return None
