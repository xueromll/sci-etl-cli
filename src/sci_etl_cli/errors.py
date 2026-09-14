from __future__ import annotations

from enum import IntEnum
from typing import IO, Any

import click
from rich.console import Console
from rich.markup import escape
from sci_etl_core.exceptions import ConfigurationError, PipelineAborted, SciEtlError

_EXTRA_FOR_PACKAGE: dict[str, str] = {
    "aiofiles": "async",
    "aiolimiter": "async",
    "httpx": "async",
    "openai": "llm",
    "pdfplumber": "pdf",
    "tiktoken": "llm",
}


class ExitCode(IntEnum):
    OK = 0
    FAILURE = 1
    USAGE = 2
    CONFIGURATION = 3
    MISSING_DEPENDENCY = 4
    INTERRUPTED = 130


class CliFailure(click.ClickException):
    """A failure shown as a single error line on stderr."""

    exit_code = ExitCode.FAILURE

    def show(self, file: IO[Any] | None = None) -> None:
        console = Console(file=file, stderr=file is None, highlight=False)
        console.print(f"[bold red]Error:[/] {escape(self.format_message())}")


class ConfigurationFailure(CliFailure):
    exit_code = ExitCode.CONFIGURATION


class MissingDependencyFailure(CliFailure):
    exit_code = ExitCode.MISSING_DEPENDENCY


def describe_abort(aborted: PipelineAborted) -> str:
    """Summarize an aborted run, naming the underlying cause when there is one."""
    cause = aborted.__cause__
    return str(aborted) if cause is None else f"{aborted}; cause: {cause!r}"


def missing_dependency_message(module_name: str | None) -> str:
    package = (module_name or "").partition(".")[0] or "unknown"
    extra = _EXTRA_FOR_PACKAGE.get(package)
    if extra is None:
        return f"Missing Python package {package!r}. Reinstall with: pip install --force-reinstall sci-etl-cli"
    return f'Missing Python package {package!r}. Install it with: pip install "sci-etl-core[{extra}]"'


def to_cli_failure(error: SciEtlError | ModuleNotFoundError) -> CliFailure:
    if isinstance(error, ModuleNotFoundError):
        return MissingDependencyFailure(missing_dependency_message(error.name))
    if isinstance(error, ConfigurationError):
        return ConfigurationFailure(str(error))
    return CliFailure(str(error))
