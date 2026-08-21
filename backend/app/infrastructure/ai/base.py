"""
Abstract Base LLM Gateway Interface
Defines the contract for all multi-provider LLM integrations with structured outputs and token tracking.
"""

from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from typing import TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMResponse(BaseModel):
    content: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0
    model: str
    provider: str


class BaseLLMGateway(ABC):
    """Abstract interface for LLM providers (OpenAI, Anthropic, Gemini, Ollama)."""

    @abstractmethod
    async def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """Generate unstructured text completion."""
        pass

    @abstractmethod
    async def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: type[T],
        model: str | None = None,
        temperature: float = 0.1,
    ) -> T:
        """Generate structured response validated against a Pydantic schema."""
        pass

    @abstractmethod
    async def generate_stream(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
        temperature: float = 0.1,
    ) -> AsyncGenerator[str]:
        """Stream text tokens in real time."""
        yield ""
