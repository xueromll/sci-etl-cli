from __future__ import annotations

from sci_etl_core.models import TokenUsage

from sci_etl_cli.settings import load_cli_config
from sci_etl_cli.usage import describe_usage


def test_nothing_is_reported_without_tracked_requests(make_project):
    llm = load_cli_config(make_project()).llm
    assert describe_usage(None, llm) is None
    assert describe_usage(TokenUsage(), llm) is None


def test_usage_is_summarized_without_prices(make_project):
    llm = load_cli_config(make_project()).llm
    usage = TokenUsage(requests=1, prompt_tokens=1200, completion_tokens=80)
    assert describe_usage(usage, llm) == "LLM usage: 1 request, 1,200 prompt and 80 completion tokens"


def test_cost_is_estimated_from_configured_prices(make_project):
    config_path = make_project({"llm": {"input_cost_per_million": 0.15, "output_cost_per_million": 0.6}})
    llm = load_cli_config(config_path).llm
    usage = TokenUsage(requests=3, prompt_tokens=2_000_000, completion_tokens=500_000)
    assert describe_usage(usage, llm) == (
        "LLM usage: 3 requests, 2,000,000 prompt and 500,000 completion tokens, estimated cost 0.6000"
    )
