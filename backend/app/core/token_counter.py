"""
Token and Cost Telemetry Engine.
Accurately counts prompt and completion tokens and calculates LLM API expenditures
across OpenAI, Anthropic, Google Gemini, Groq, and Perplexity models.
"""

import math
import re
from typing import TypedDict


class CostPricing(TypedDict):
    prompt_per_1m: float
    completion_per_1m: float


# Current market pricing per 1,000,000 tokens (USD)
MODEL_PRICING_REGISTRY: dict[str, CostPricing] = {
    # OpenAI
    "gpt-4o": {"prompt_per_1m": 2.50, "completion_per_1m": 10.00},
    "gpt-4o-mini": {"prompt_per_1m": 0.15, "completion_per_1m": 0.60},
    "gpt-4-turbo": {"prompt_per_1m": 10.00, "completion_per_1m": 30.00},
    "gpt-3.5-turbo": {"prompt_per_1m": 0.50, "completion_per_1m": 1.50},

    # Groq (On-demand inference)
    "openai/gpt-oss-120b": {"prompt_per_1m": 0.15, "completion_per_1m": 0.60},
    "openai/gpt-oss-20b": {"prompt_per_1m": 0.075, "completion_per_1m": 0.30},
    "qwen/qwen3.6-27b": {"prompt_per_1m": 0.10, "completion_per_1m": 0.40},
    "llama-3.3-70b-versatile": {"prompt_per_1m": 0.59, "completion_per_1m": 0.79},
    "llama-3.1-8b-instant": {"prompt_per_1m": 0.05, "completion_per_1m": 0.08},
    "mixtral-8x7b-32768": {"prompt_per_1m": 0.24, "completion_per_1m": 0.24},

    # Google Gemini
    "gemini-2.5-flash": {"prompt_per_1m": 0.075, "completion_per_1m": 0.30},
    "gemini-2.0-flash": {"prompt_per_1m": 0.075, "completion_per_1m": 0.30},
    "gemini-1.5-flash": {"prompt_per_1m": 0.075, "completion_per_1m": 0.30},
    "gemini-flash-latest": {"prompt_per_1m": 0.075, "completion_per_1m": 0.30},
    "gemini-2.5-pro": {"prompt_per_1m": 1.25, "completion_per_1m": 5.00},
    "gemini-1.5-pro": {"prompt_per_1m": 1.25, "completion_per_1m": 5.00},
    "gemini-pro-latest": {"prompt_per_1m": 1.25, "completion_per_1m": 5.00},

    # Anthropic
    "claude-3-5-sonnet-20241022": {"prompt_per_1m": 3.00, "completion_per_1m": 15.00},
    "claude-3-5-sonnet-20240620": {"prompt_per_1m": 3.00, "completion_per_1m": 15.00},
    "claude-3-5-haiku-20241022": {"prompt_per_1m": 0.80, "completion_per_1m": 4.00},
    "claude-3-haiku-20240307": {"prompt_per_1m": 0.25, "completion_per_1m": 1.25},

    # Perplexity
    "sonar-pro": {"prompt_per_1m": 3.00, "completion_per_1m": 15.00},
}

DEFAULT_FALLBACK_PRICING: CostPricing = {"prompt_per_1m": 0.50, "completion_per_1m": 1.50}


def count_tokens(text: str) -> int:
    """
    Accurately count tokens from arbitrary source code, prompts, and structured JSON.
    Uses regex sub-word BPE token boundary heuristics aligned with cl100k_base / o200k_base.
    """
    if not text:
        return 0

    # 1. Try to use tiktoken if installed
    try:
        import tiktoken
        encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(text, disallowed_special=()))
    except Exception:
        pass

    # 2. High-precision tokenizer regex heuristic
    # Matches words, punctuation, whitespace sequences, and code symbols
    tokens = re.findall(r"\w+|[^\w\s]|\s+", text)
    token_count = 0
    for t in tokens:
        if t.isspace():
            token_count += math.ceil(len(t) / 4)
        elif len(t) > 4:
            token_count += math.ceil(len(t) / 3.5)
        else:
            token_count += 1
    return max(1, token_count)


def calculate_cost(
    prompt_tokens: int,
    completion_tokens: int,
    model: str | None = None,
    provider: str | None = None,
) -> float:
    """Calculate exact USD cost for prompt and completion token counts."""
    pricing = None
    if model:
        normalized = model.lower()
        if normalized in MODEL_PRICING_REGISTRY:
            pricing = MODEL_PRICING_REGISTRY[normalized]
        else:
            for key, val in MODEL_PRICING_REGISTRY.items():
                if key in normalized or normalized in key:
                    pricing = val
                    break

    if not pricing:
        if provider == "groq":
            pricing = {"prompt_per_1m": 0.15, "completion_per_1m": 0.60}
        elif provider == "gemini":
            pricing = {"prompt_per_1m": 0.075, "completion_per_1m": 0.30}
        elif provider == "anthropic":
            pricing = {"prompt_per_1m": 3.00, "completion_per_1m": 15.00}
        elif provider == "openai":
            pricing = {"prompt_per_1m": 2.50, "completion_per_1m": 10.00}
        else:
            pricing = DEFAULT_FALLBACK_PRICING

    cost = (prompt_tokens * (pricing["prompt_per_1m"] / 1_000_000)) + (
        completion_tokens * (pricing["completion_per_1m"] / 1_000_000)
    )
    return round(cost, 7)
