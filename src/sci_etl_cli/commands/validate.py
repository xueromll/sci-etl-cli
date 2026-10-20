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
from sci_etl_cli.options import api_key_hint, config_argument, newest_first_message
from sci_etl_cli.output import stdout_console
from sci_etl_cli.settings import CliConfig, SourceKind, load_cli_config

_COMMON_PACKAGES: tuple[tuple[str, str], ...] = (("yaml", "config"), ("httpx", "async"), ("openai", "llm"))
_SOURCE_PACKAGES: dict[SourceKind, tuple[tuple[str, str], ...]] = {
    "arxiv": (("bs4", "arxiv"), ("lxml", "arxiv"), ("pdfplumber", "pdf")),
    "pubmed": (("lxml", "xml"),),
    "semantic_scholar": (("pdfplumber", "pdf"),),
    "openalex": (("pdfplumber", "pdf"),),
}
_PING_CONTENT = "Title: Connectivity check\nAbstract: A test request sent by sci-etl validate --online."


@dataclass(frozen=True, slots=True)
class Check:
    name: str
    passed: bool
    detail: str
    failure_code: ExitCode = ExitCode.CONFIGURATION


@click.command("validate")
@config_argument
@click.option("--online", is_flag=True, help="Also send one listing request to the source and one LLM request.")
def validate_command(config_path: Path, online: bool) -> None:
    """Check CONFIG and its prompts without running the pipeline.

    The packages checked are the ones the configured source needs. Exits 3
    when a configuration check fails, 4 when a required package is missing,
    and 1 when an online check fails. Online checks run only after every
    offline check passes.
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
        _source_check(config),
        _query_check(config),
        _prompt_check("relevance prompt", config.prompts.relevance, ("JSON", "relevant")),
        _prompt_check("extraction prompt", config.prompts.extraction, extraction_terms),
        _plugin_check(config),
        _api_key_check(config),
        _package_check(config),
    ]


async def online_checks(config: CliConfig) -> list[Check]:
    return [await _listing_check(config), await _llm_check(config)]


def render(checks: list[Check]) -> None:
    table = Table(show_header=False, box=None, pad_edge=False)
    table.add_column(no_wrap=True)
    table.add_column(no_wrap=True)
    table.add_column(overflow="fold")
    for check in checks:
        status = "[green]ok[/]" if check.passed else "[red]fail[/]"
        table.add_row(status, check.name, escape(check.detail))
    stdout_console().print(table)


def _source_check(config: CliConfig) -> Check:
    """Name the source and its API key, and refuse ``newest_first`` with a source that pages by cursor."""
    source = config.source
    if config.pipeline.newest_first and not source.pages_by_offset:
        return Check("source", False, newest_first_message(config))
    if source.kind == "arxiv":
        return Check("source", True, f"{source.label}, no API key needed")
    if source.api_key.get_secret_value():
        return Check("source", True, f"{source.label}, {source.api_key_env} is set")
    return Check("source", True, f"{source.label}, no API key ({source.api_key_env} is not set)")


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


def _plugin_check(config: CliConfig) -> Check:
    references = list(config.export.validators)
    if not references:
        return Check("plug-ins", True, "none configured")
    try:
        assembly.build_validators(config)
    except ConfigurationError as exc:
        return Check("plug-ins", False, str(exc))
    return Check("plug-ins", True, ", ".join(references))


def _api_key_check(config: CliConfig) -> Check:
    if config.llm.api_key.get_secret_value():
        return Check("API key", True, f"{config.llm.api_key_env} is set")
    return Check("API key", False, api_key_hint(config))


def _package_check(config: CliConfig) -> Check:
    """Check the packages the configured source needs, naming the sci-etl-core extras that install the missing ones."""
    required = (*_COMMON_PACKAGES, *_SOURCE_PACKAGES[config.source.kind])
    missing = [(package, extra) for package, extra in required if find_spec(package) is None]
    if missing:
        extras = ",".join(dict.fromkeys(extra for _package, extra in missing))
        packages = ", ".join(package for package, _extra in missing)
        detail = f'missing: {packages}; install with: pip install "sci-etl-core[{extras}]"'
        return Check("packages", False, detail, ExitCode.MISSING_DEPENDENCY)
    return Check("packages", True, ", ".join(package for package, _extra in required))


async def _listing_check(config: CliConfig) -> Check:
    name = config.source.label
    http_client = assembly.build_http_client(config)
    try:
        extractor = assembly.build_extractor(config, http_client)
        entries = (await extractor.fetch_page(config.pipeline.search_query, None, 1)).entries
    except SciEtlError as exc:
        return Check(name, False, str(exc), ExitCode.FAILURE)
    finally:
        await http_client.aclose()
    if entries == 0:
        return Check(name, False, "the search query matched no entries", ExitCode.FAILURE)
    return Check(name, True, "listing request succeeded")


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
