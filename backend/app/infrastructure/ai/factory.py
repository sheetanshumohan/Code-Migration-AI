"""
Multi-LLM Gateway Factory & Dynamic Provider Implementation
Supports OpenAI, Anthropic, Google Gemini, and Local Ollama with Instructor structured outputs.
"""

import os
from collections.abc import AsyncGenerator
from typing import Any, TypeVar, cast

try:
    from langsmith import traceable as observe
    LANGSMITH_AVAILABLE = True
except ImportError:
    observe = lambda *args, **kwargs: (lambda func: func)
    LANGSMITH_AVAILABLE = False

try:
    import instructor
    INSTRUCTOR_AVAILABLE = True
except ImportError:
    instructor = None
    INSTRUCTOR_AVAILABLE = False

try:
    from openai import AsyncOpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    AsyncOpenAI = None
    OPENAI_AVAILABLE = False

try:
    from anthropic import AsyncAnthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    AsyncAnthropic = None
    ANTHROPIC_AVAILABLE = False

try:
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=FutureWarning)
        import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    genai = None
    GEMINI_AVAILABLE = False

from pydantic import BaseModel

from app.core.config import settings
from app.core.logging import get_logger
from app.core.telemetry import LLM_TOKEN_USAGE_COUNTER
from app.core.token_counter import calculate_cost
from app.infrastructure.agents.safety import agent_safety_filter
from app.infrastructure.ai.base import BaseLLMGateway, LLMResponse

logger = get_logger("codemigration.ai.factory")
T = TypeVar("T", bound=BaseModel)


class OpenAIGateway(BaseLLMGateway):
    def __init__(self) -> None:
        self.api_key = settings.OPENAI_API_KEY or os.getenv("OPENAI_API_KEY")
        self.client = AsyncOpenAI(api_key=self.api_key) if (self.api_key and OPENAI_AVAILABLE and AsyncOpenAI) else None
        self.instructor_client = (
            instructor.from_openai(self.client) if (self.client and INSTRUCTOR_AVAILABLE and instructor) else None
        )

    def _ensure_client(self) -> AsyncOpenAI | None:
        key = self.api_key or settings.OPENAI_API_KEY or os.getenv("OPENAI_API_KEY")
        if key and (self.client is None or self.api_key != key) and OPENAI_AVAILABLE and AsyncOpenAI:
            self.api_key = key
            self.client = AsyncOpenAI(api_key=key)
            if INSTRUCTOR_AVAILABLE and instructor:
                self.instructor_client = instructor.from_openai(self.client)
        return self.client

    @observe(run_type="llm")
    async def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        model_name = model or settings.DEFAULT_FRONTIER_MODEL
        client = self._ensure_client()
        if not client:
            logger.warning("OpenAI API key missing for text generation")
            raise ValueError("OpenAI client not configured. Please supply OPENAI_API_KEY.")

        # Protect against prompt injection by sanitizing untrusted repository content
        sanitized_user_prompt = agent_safety_filter.sanitize_repository_content(user_prompt)
        if not sanitized_user_prompt.strip():
            sanitized_user_prompt = "Execute the modernization and code transformation according to the system policy."

        if "gpt-oss" in model_name or "qwen" in model_name:
            model_name = "gpt-4o"

        candidate_models = [
            model_name,
            "gpt-4o-mini",
            "gpt-4o",
            "gpt-3.5-turbo",
        ]

        last_err = None
        for m in candidate_models:
            try:
                resp = await client.chat.completions.create(
                    model=m,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": sanitized_user_prompt},
                    ],
                    temperature=temperature,
                    max_tokens=max_tokens,
                )

                content = resp.choices[0].message.content or ""
                p_tokens = resp.usage.prompt_tokens if resp.usage else 0
                c_tokens = resp.usage.completion_tokens if resp.usage else 0
                tot_tokens = p_tokens + c_tokens

                # Record metrics
                LLM_TOKEN_USAGE_COUNTER.labels(provider="openai", model=m, token_type="prompt").inc(p_tokens)
                LLM_TOKEN_USAGE_COUNTER.labels(provider="openai", model=m, token_type="completion").inc(c_tokens)

                return LLMResponse(
                    content=content,
                    prompt_tokens=p_tokens,
                    completion_tokens=c_tokens,
                    total_tokens=tot_tokens,
                    estimated_cost_usd=calculate_cost(p_tokens, c_tokens, model=m, provider="openai"),
                    model=m,
                    provider="openai",
                )
            except Exception as e:
                logger.debug(f"OpenAI model {m} failed: {e}")
                last_err = e

        raise last_err or RuntimeError("OpenAI generate_text failed across candidate models.")



    @observe(run_type="llm")
    async def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: type[T],
        model: str | None = None,
        temperature: float = 0.1,
    ) -> T:
        model_name = model or settings.DEFAULT_FRONTIER_MODEL
        self._ensure_client()
        if not self.instructor_client:
            # Return a default instance or mock when API key not set
            logger.warning("OpenAI API key missing, returning fallback structured instance")
            raise ValueError("OpenAI client not configured. Please supply OPENAI_API_KEY.")

        res = await self.instructor_client.chat.completions.create(
            model=model_name,
            response_model=response_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
        )
        return res

    @observe(run_type="llm")
    async def generate_stream(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
        temperature: float = 0.1,
    ) -> AsyncGenerator[str]:
        model_name = model or settings.DEFAULT_FRONTIER_MODEL
        client = self._ensure_client()
        if not client:
            logger.warning("OpenAI API key missing for stream generation")
            raise ValueError("OpenAI client not configured. Please supply OPENAI_API_KEY.")

        if "gpt-oss" in model_name or "qwen" in model_name:
            model_name = "gpt-4o"

        candidate_models = [
            model_name,
            "gpt-4o-mini",
            "gpt-4o",
            "gpt-3.5-turbo",
        ]

        last_err = None
        for m in candidate_models:
            try:
                stream = await self.client.chat.completions.create(
                    model=m,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=temperature,
                    stream=True,
                )
                async for chunk in stream:
                    token = chunk.choices[0].delta.content or ""
                    if token:
                        yield token
                return
            except Exception as e:
                logger.debug(f"OpenAI model {m} failed: {e}")
                last_err = e
        raise last_err or RuntimeError("OpenAI generate_stream failed across candidate models.")


class AnthropicGateway(BaseLLMGateway):
    def __init__(self) -> None:
        self.api_key = settings.ANTHROPIC_API_KEY
        self.client = AsyncAnthropic(api_key=self.api_key) if (self.api_key and ANTHROPIC_AVAILABLE and AsyncAnthropic) else None
        self.instructor_client = (
            instructor.from_anthropic(self.client) if (self.client and INSTRUCTOR_AVAILABLE and instructor) else None
        )

    @observe(run_type="llm")
    async def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        model_name = model or settings.ANTHROPIC_DEFAULT_MODEL
        if not self.client:
            logger.warning("Anthropic API key missing for text generation")
            raise ValueError("Anthropic client not configured. Please supply ANTHROPIC_API_KEY.")

        candidate_models = [model_name, "claude-3-5-sonnet-20241022", "claude-3-5-sonnet-20240620", "claude-3-5-haiku-20241022", "claude-3-haiku-20240307"]
        unique_models = list(dict.fromkeys(candidate_models))
        last_err = None

        for m in unique_models:
            try:
                resp = await self.client.messages.create(
                    model=m,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_prompt}],
                    temperature=temperature,
                    max_tokens=max_tokens,
                )

                content = ""
                if resp.content and hasattr(resp.content[0], "text"):
                    content = resp.content[0].text
                p_tokens = resp.usage.input_tokens
                c_tokens = resp.usage.output_tokens
                tot_tokens = p_tokens + c_tokens

                LLM_TOKEN_USAGE_COUNTER.labels(provider="anthropic", model=m, token_type="prompt").inc(p_tokens)
                LLM_TOKEN_USAGE_COUNTER.labels(provider="anthropic", model=m, token_type="completion").inc(c_tokens)

                return LLMResponse(
                    content=content,
                    prompt_tokens=p_tokens,
                    completion_tokens=c_tokens,
                    total_tokens=tot_tokens,
                    estimated_cost_usd=calculate_cost(p_tokens, c_tokens, model=m, provider="anthropic"),
                    model=m,
                    provider="anthropic",
                )
            except Exception as e:
                last_err = e
                logger.debug(f"Anthropic model {m} failed: {e}")
                continue

        raise last_err or ValueError("Anthropic text generation failed on all models.")

    @observe(run_type="llm")
    async def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: type[T],
        model: str | None = None,
        temperature: float = 0.1,
    ) -> T:
        model_name = model or settings.ANTHROPIC_DEFAULT_MODEL
        if not self.instructor_client:
            raise ValueError("Anthropic client not configured.")

        res = await self.instructor_client.messages.create(
            model=model_name,
            response_model=response_model,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
            max_tokens=4096,
            temperature=temperature,
        )
        return res

    @observe(run_type="llm")
    async def generate_stream(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
        temperature: float = 0.1,
    ) -> AsyncGenerator[str]:
        model_name = model or settings.ANTHROPIC_DEFAULT_MODEL
        if not self.client:
            raise ValueError("Anthropic client not configured.")

        async with self.client.messages.stream(
            model=model_name,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
            max_tokens=4096,
            temperature=temperature,
        ) as stream:
            async for text in stream.text_stream:
                yield text

class GroqGateway(OpenAIGateway):
    def __init__(self) -> None:
        self.api_key = settings.GROQ_API_KEY
        self.provider = "groq"
        self.client = AsyncOpenAI(api_key=self.api_key, base_url="https://api.groq.com/openai/v1") if (self.api_key and OPENAI_AVAILABLE and AsyncOpenAI) else None
        self.instructor_client = (
            instructor.from_openai(self.client, mode=instructor.Mode.JSON) if (self.client and INSTRUCTOR_AVAILABLE and instructor) else None
        )

    async def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        model_name = model or settings.GROQ_DEFAULT_MODEL or "qwen/qwen3.6-27b"
        candidate_models = [
            model_name,
            "openai/gpt-oss-120b",
            "qwen/qwen3.6-27b",
            "openai/gpt-oss-20b",
        ]
        unique_models = list(dict.fromkeys(candidate_models))
        last_error = None

        for m in unique_models:
            try:
                res = await super().generate_text(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    model=m,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                res.provider = self.provider
                return res
            except Exception as e:
                last_error = e
                logger.warning(f"Groq model {m} failed: {e}. Trying fallback model...")
                continue

        raise last_error or ValueError("Groq generation failed on all models.")

    @observe(run_type="llm")
    async def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: type[T],
        model: str | None = None,
        temperature: float = 0.1,
    ) -> T:
        if not self.instructor_client:
            raise ValueError("Groq client not configured or SDK not installed. Please set GROQ_API_KEY in .env.")

        model_name = model or settings.GROQ_DEFAULT_MODEL or "qwen/qwen3.6-27b"
        candidate_models = [
            model_name,
            "openai/gpt-oss-120b",
            "qwen/qwen3.6-27b",
            "openai/gpt-oss-20b",
        ]
        unique_models = list(dict.fromkeys(candidate_models))

        last_error = None
        for m in unique_models:
            try:
                res = await self.instructor_client.chat.completions.create(
                    model=m,
                    response_model=response_model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=temperature,
                    max_tokens=4096,
                )
                return res
            except Exception as e:
                last_error = e
                logger.warning(f"Groq structured model {m} failed: {e}. Trying fallback model...")
                continue

        raise last_error or ValueError("Groq structured output failed across all candidate models.")


class PerplexityGateway(OpenAIGateway):
    def __init__(self) -> None:
        self.api_key = settings.PERPLEXITY_API_KEY
        self.provider = "perplexity"
        self.client = AsyncOpenAI(api_key=self.api_key, base_url="https://api.perplexity.ai") if (self.api_key and OPENAI_AVAILABLE and AsyncOpenAI) else None
        self.instructor_client = (
            instructor.from_openai(self.client) if (self.client and INSTRUCTOR_AVAILABLE and instructor) else None
        )

    async def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        model_name = model or "sonar-pro"
        res = await super().generate_text(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=model_name,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        res.provider = self.provider
        return res


class GeminiGateway(BaseLLMGateway):
    def __init__(self) -> None:
        self.api_key = settings.GEMINI_API_KEY
        if self.api_key and GEMINI_AVAILABLE and genai:
            genai.configure(api_key=self.api_key)
            self.client = genai.GenerativeModel(settings.GEMINI_DEFAULT_MODEL)
            self.instructor_client = (
                instructor.from_gemini(self.client) if (INSTRUCTOR_AVAILABLE and instructor) else None
            )
        else:
            self.client = None
            self.instructor_client = None

    @observe(run_type="llm")
    async def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        if not self.api_key or genai is None:
            logger.warning("Gemini API key missing for text generation")
            raise ValueError("Gemini client not configured or SDK not installed.")

        # Candidate models in order of capability & free-tier availability
        requested_model = model or settings.GEMINI_DEFAULT_MODEL
        candidate_models = [
            requested_model,
            "gemini-3.6-flash",
            "gemini-3.6-pro",
        ]
        # Deduplicate while preserving order
        unique_models = list(dict.fromkeys(candidate_models))

        last_err = None
        for m_name in unique_models:
            try:
                model_client = genai.GenerativeModel(model_name=m_name, system_instruction=system_prompt)
                resp = await model_client.generate_content_async(
                    user_prompt,
                    generation_config=genai.types.GenerationConfig(temperature=temperature, max_output_tokens=max_tokens)
                )

                content = resp.text
                tot_tokens = resp.usage_metadata.total_token_count if hasattr(resp, "usage_metadata") else 0
                p_tokens = resp.usage_metadata.prompt_token_count if hasattr(resp, "usage_metadata") else 0
                c_tokens = resp.usage_metadata.candidates_token_count if hasattr(resp, "usage_metadata") else 0

                LLM_TOKEN_USAGE_COUNTER.labels(provider="gemini", model=m_name, token_type="prompt").inc(p_tokens)
                LLM_TOKEN_USAGE_COUNTER.labels(provider="gemini", model=m_name, token_type="completion").inc(c_tokens)

                return LLMResponse(
                    content=content,
                    prompt_tokens=p_tokens,
                    completion_tokens=c_tokens,
                    total_tokens=tot_tokens,
                    estimated_cost_usd=calculate_cost(p_tokens, c_tokens, model=m_name, provider="gemini"),
                    model=m_name,
                    provider="gemini",
                )
            except Exception as e:
                last_err = e
                logger.debug(f"Gemini model {m_name} failed: {e}")
                continue

        raise last_err or ValueError("Gemini text generation failed across all candidate models.")

    @observe(run_type="llm")
    async def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: type[T],
        model: str | None = None,
        temperature: float = 0.1,
    ) -> T:
        if not self.api_key or genai is None:
            if settings.OPENAI_API_KEY:
                openai_gw = OpenAIGateway()
                return cast(
                    T,
                    await openai_gw.generate_structured(
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                        response_model=response_model,
                        temperature=temperature,
                    ),
                )
            raise ValueError("Gemini client not configured or SDK not installed.")

        requested_model = model or settings.GEMINI_DEFAULT_MODEL
        candidate_models = [
            requested_model,
            "gemini-3.6-flash",
            "gemini-3.6-pro",
        ]
        unique_models = list(dict.fromkeys(candidate_models))

        last_err = None
        for m_name in unique_models:
            try:
                model_client = genai.GenerativeModel(model_name=m_name, system_instruction=system_prompt)
                resp = await model_client.generate_content_async(
                    user_prompt,
                    generation_config=genai.GenerationConfig(
                        response_mime_type="application/json",
                        response_schema=response_model,
                        temperature=temperature,
                    )
                )
                if resp.text:
                    return response_model.model_validate_json(resp.text)
            except Exception as e:
                last_err = e
                logger.debug(f"Gemini structured model {m_name} failed: {e}")
                continue

        raise last_err or ValueError("Gemini structured output failed.")

    @observe(run_type="llm")
    async def generate_stream(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
        temperature: float = 0.1,
    ) -> AsyncGenerator[str]:
        model_name = model or settings.GEMINI_DEFAULT_MODEL
        if not self.api_key or genai is None:
            raise ValueError("Gemini client not configured or SDK not installed.")

        model_client = genai.GenerativeModel(model_name=model_name, system_instruction=system_prompt)
        resp = await model_client.generate_content_async(
            user_prompt,
            generation_config=genai.types.GenerationConfig(temperature=temperature),
            stream=True
        )
        async for chunk in resp:
            if chunk.text:
                yield chunk.text

class ResilientGateway(BaseLLMGateway):
    def __init__(self, primary_provider: str):
        self.primary_provider = primary_provider

    def __getattr__(self, name):
        gw = LLMGatewayFactory._get_raw_gateway(self.primary_provider)
        return getattr(gw, name)

    def _get_fallback_chain(self) -> list[str]:
        configured = LLMGatewayFactory.get_configured_providers()
        if self.primary_provider in configured:
            configured.remove(self.primary_provider)
        return [self.primary_provider] + configured

    @observe(run_type="llm")
    async def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        last_err = None
        for provider in self._get_fallback_chain():
            try:
                if provider != self.primary_provider:
                    logger.info(f"Failing over to {provider} for generate_text...")
                gw = LLMGatewayFactory._get_raw_gateway(provider)
                target_model = model if provider == self.primary_provider else None
                return await gw.generate_text(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    model=target_model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            except Exception as e:
                logger.warning(f"Provider {provider} failed during generate_text: {e}")
                last_err = e
        raise last_err or RuntimeError("All LLM providers failed for generate_text.")

    @observe(run_type="llm")
    async def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: type[T],
        model: str | None = None,
        temperature: float = 0.1,
    ) -> T:
        last_err = None
        for provider in self._get_fallback_chain():
            try:
                if provider != self.primary_provider:
                    logger.info(f"Failing over to {provider} for generate_structured...")
                gw = LLMGatewayFactory._get_raw_gateway(provider)
                target_model = model if provider == self.primary_provider else None
                return await gw.generate_structured(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    response_model=response_model,
                    model=target_model,
                    temperature=temperature,
                )
            except Exception as e:
                logger.warning(f"Provider {provider} failed during generate_structured: {e}")
                last_err = e
        raise last_err or RuntimeError("All LLM providers failed for generate_structured.")

    @observe(run_type="llm")
    async def generate_stream(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
        temperature: float = 0.1,
    ) -> AsyncGenerator[str]:
        last_err = None
        for provider in self._get_fallback_chain():
            try:
                if provider != self.primary_provider:
                    logger.info(f"Failing over to {provider} for generate_stream...")
                gw = LLMGatewayFactory._get_raw_gateway(provider)
                target_model = model if provider == self.primary_provider else None

                stream = gw.generate_stream(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    model=target_model,
                    temperature=temperature,
                )
                async for chunk in stream:
                    yield chunk
                return
            except Exception as e:
                logger.warning(f"Provider {provider} failed during generate_stream: {e}")
                last_err = e
        raise last_err or RuntimeError("All LLM providers failed for generate_stream.")


class LLMGatewayFactory:
    """Factory to retrieve appropriate LLM Gateway based on provider configuration."""

    _instances: dict[str, BaseLLMGateway] = {}
    _current_loop: Any = None

    @classmethod
    def reset(cls) -> None:
        """Reset all cached gateway instances so new tasks bind cleanly to active event loops."""
        cls._instances.clear()
        cls._current_loop = None

    @classmethod
    def get_configured_providers(cls) -> list[str]:
        providers = []
        if settings.OPENAI_API_KEY or os.getenv("OPENAI_API_KEY"):
            providers.append("openai")
        if settings.GEMINI_API_KEY or os.getenv("GEMINI_API_KEY"):
            providers.append("gemini")
        if settings.ANTHROPIC_API_KEY or os.getenv("ANTHROPIC_API_KEY"):
            providers.append("anthropic")
        if settings.GROQ_API_KEY or os.getenv("GROQ_API_KEY"):
            providers.append("groq")
        if settings.PERPLEXITY_API_KEY or os.getenv("PERPLEXITY_API_KEY"):
            providers.append("perplexity")
        return providers

    @classmethod
    def _get_raw_gateway(cls, provider: str | None = None) -> BaseLLMGateway:
        import asyncio
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            current_loop = None

        if cls._current_loop != current_loop:
            cls._instances.clear()
            cls._current_loop = current_loop

        selected_provider = (provider or settings.DEFAULT_LLM_PROVIDER).lower()

        # If selected provider has no API key, prefer one that does
        configured = cls.get_configured_providers()
        if selected_provider not in configured and configured:
            selected_provider = configured[0]

        if selected_provider not in cls._instances:
            if selected_provider == "openai":
                cls._instances[selected_provider] = OpenAIGateway()
            elif selected_provider == "anthropic":
                cls._instances[selected_provider] = AnthropicGateway()
            elif selected_provider == "gemini":
                cls._instances[selected_provider] = GeminiGateway()
            elif selected_provider == "groq":
                cls._instances[selected_provider] = GroqGateway()
            elif selected_provider == "perplexity":
                cls._instances[selected_provider] = PerplexityGateway()
            else:
                # Default fallback to OpenAIGateway
                cls._instances[selected_provider] = OpenAIGateway()

        return cls._instances[selected_provider]

    @classmethod
    def get_gateway(cls, provider: str | None = None) -> BaseLLMGateway:
        selected_provider = (provider or settings.DEFAULT_LLM_PROVIDER).lower()
        configured = cls.get_configured_providers()
        if selected_provider not in configured and configured:
            selected_provider = configured[0]
        return ResilientGateway(primary_provider=selected_provider)

llm_factory = LLMGatewayFactory()
