"""Abstract base class for LLM providers."""
from __future__ import annotations

from abc import ABC, abstractmethod


class BaseLLMProvider(ABC):
    """Common interface every LLM provider must implement.

    Adding a new provider (e.g. OpenAI, Mistral) means:
      1. Subclass BaseLLMProvider
      2. Implement generate()
      3. Register in providers/__init__.py create_llm_provider()
    """

    @abstractmethod
    async def generate(self, system_prompt: str, user_message: str) -> str | None:
        """Send a prompt and return the model's text response.

        Args:
            system_prompt: Instructions that shape the model's behaviour.
            user_message: The specific request for this call.

        Returns:
            The model's text response, or None on error.
            Must not raise — log and return None instead.
        """
        ...

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Human-readable identifier, e.g. 'claude-sonnet-4-6' or 'gemini-2.0-flash'."""
        ...
