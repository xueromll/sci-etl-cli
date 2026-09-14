from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sci_etl_core.models import TokenUsage

    from sci_etl_cli.settings import CliLLMConfig

_TOKENS_PER_PRICE_UNIT = 1_000_000


def describe_usage(usage: TokenUsage | None, llm: CliLLMConfig) -> str | None:
    """Summarize a run's LLM token usage, or return ``None`` when nothing was tracked."""
    if usage is None or usage.requests == 0:
        return None
    summary = (
        f"LLM usage: {usage.requests} request{'' if usage.requests == 1 else 's'}, "
        f"{usage.prompt_tokens:,} prompt and {usage.completion_tokens:,} completion tokens"
    )
    cost = estimate_cost(usage, llm)
    return summary if cost is None else f"{summary}, estimated cost {cost:.4f}"


def estimate_cost(usage: TokenUsage, llm: CliLLMConfig) -> float | None:
    """Price the tokens at the configured per-million rates, in the currency those rates use."""
    if llm.input_cost_per_million is None or llm.output_cost_per_million is None:
        return None
    return (
        usage.prompt_tokens * llm.input_cost_per_million + usage.completion_tokens * llm.output_cost_per_million
    ) / _TOKENS_PER_PRICE_UNIT
