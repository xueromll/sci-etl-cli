from __future__ import annotations

import asyncio
from dataclasses import dataclass
from importlib.util import find_spec
from pathlib import Path

import click
from rich.markup import escape
from rich.table import Table
from sci_etl_core.exceptions import ConfigurationError, SciEtlError

from sci_etl_cli import assembly
from sci_etl_cli.errors import ExitCode
from sci_etl_cli.options import api_key_hint, config_argument
from sci_etl_cli.output import discard, stdout_console
from sci_etl_cli.settings import CliConfig, load_cli_config

_REQUIRED_PACKAGES: tuple[tuple[str, str], ...] = (
    ("httpx", "async"),
    ("aiofiles", "async"),
    ("openai", "llm"),
    ("pdfplumber", "pdf"),
)
_PING_CONTENT = "Title: Connectivity check\nAbstract: A test request sent by sci-etl validate --online."


@dataclass(frozen=True, slots=True)
class Check:
    name: str
    passed: bool
    detail: str
    failure_code: ExitCode = ExitCode.CONFIGURATION


@click.command("validate")
@config_argument
@click.option("--online", is_flag=True, help="Also send one arXiv listing request and one LLM request.")
def validate_command(config_path: Path, online: bool) -> None:
    """Check CONFIG and its prompts without running the pipeline.

    Exits 3 when a configuration check fails, 4 when a required package is
    missing, and 1 when an online check fails. Online checks run only after
    every offline check passes.
    """
    config = load_cli_config(config_path)
    checks = offline_checks(config)
    if online and all(check.passed for check in checks):
        checks.extend(asyncio.run(online_checks(config)))
    render(checks)
    failures = [check.failure_code for check in checks if not check.passed]
    if failures:
        click.get_current_context().exit(int(max(failures)))


def offline_checks(config: CliConfig) -> list[Check]:
    export = config.export
    extraction_terms = ("JSON", config.prompts.result_key, export.key_column, *export.value_columns)
    return [
        Check("config", True, "parsed and validated"),
        _query_check(config),
        _prompt_check("relevance prompt", config.prompts.relevance, ("JSON", "relevant")),
        _prompt_check("extraction prompt", config.prompts.extraction, extraction_terms),
        _api_key_check(config),
        _package_check(),
    ]


async def online_checks(config: CliConfig) -> list[Check]:
    return [await _arxiv_check(config), await _llm_check(config)]


def render(checks: list[Check]) -> None:
    table = Table(show_header=False, box=None, pad_edge=False)
    table.add_column(no_wrap=True)
    table.add_column(no_wrap=True)
    table.add_column(overflow="fold")
    for check in checks:
        status = "[green]ok[/]" if check.passed else "[red]fail[/]"
        table.add_row(status, check.name, escape(check.detail))
    stdout_console().print(table)


def _query_check(config: CliConfig) -> Check:
    query = config.pipeline.search_query.strip()
    if not query:
        return Check("search query", False, "pipeline.search_query is empty")
    return Check("search query", True, query)


def _prompt_check(name: str, path: Path, required_terms: tuple[str, ...]) -> Check:
    try:
        text = assembly.read_prompt(path)
    except ConfigurationError as exc:
        return Check(name, False, str(exc))
    folded = text.casefold()
    missing = [term for term in required_terms if term.casefold() not in folded]
    if missing:
        return Check(name, False, f"{path.name} never mentions: {', '.join(missing)}")
    return Check(name, True, f"{path.name} mentions {', '.join(required_terms)}")


def _api_key_check(config: CliConfig) -> Check:
    if config.llm.api_key.get_secret_value():
        return Check("API key", True, f"{config.llm.api_key_env} is set")
    return Check("API key", False, api_key_hint(config))


def _package_check() -> Check:
    missing = [
        f"{package} (sci-etl-core[{extra}])" for package, extra in _REQUIRED_PACKAGES if find_spec(package) is None
    ]
    if missing:
        return Check("packages", False, f"missing: {', '.join(missing)}", ExitCode.MISSING_DEPENDENCY)
    return Check("packages", True, ", ".join(package for package, _extra in _REQUIRED_PACKAGES))


async def _arxiv_check(config: CliConfig) -> Check:
    http_client = assembly.build_http_client(config)
    try:
        extractor = assembly.build_extractor(config, http_client, discard)
        raw_listing = await extractor.search(config.pipeline.search_query, 1, 0)
        _records, entries = extractor.parse_listing(raw_listing, set())
    except SciEtlError as exc:
        return Check("arXiv", False, str(exc), ExitCode.FAILURE)
    finally:
        await http_client.aclose()
    if entries == 0:
        return Check("arXiv", False, "the search query matched no entries", ExitCode.FAILURE)
    return Check("arXiv", True, "listing request succeeded")


async def _llm_check(config: CliConfig) -> Check:
    prompt = assembly.read_prompt(config.prompts.relevance)
    llm_client = assembly.build_llm_client(config)
    try:
        await llm_client.complete_json(prompt, _PING_CONTENT, config.llm.timeout)
    except SciEtlError as exc:
        return Check("LLM", False, str(exc), ExitCode.FAILURE)
    finally:
        await llm_client.aclose()
    return Check("LLM", True, f"{config.llm.model} answered in JSON mode")
