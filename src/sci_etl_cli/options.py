from __future__ import annotations

from pathlib import Path

import click

from sci_etl_cli.errors import ConfigurationFailure
from sci_etl_cli.settings import CliConfig

config_argument = click.argument(
    "config_path",
    metavar="CONFIG",
    type=click.Path(dir_okay=False, path_type=Path),
)


def api_key_hint(config: CliConfig) -> str:
    return (
        f"{config.llm.api_key_env} is not set; add it to the .env file beside the config "
        "or to the environment"
    )


def require_api_key(config: CliConfig) -> None:
    if not config.llm.api_key.get_secret_value():
        raise ConfigurationFailure(api_key_hint(config))


def require_query(query: str) -> str:
    if not query.strip():
        raise ConfigurationFailure("No search query: set pipeline.search_query in the config or pass --query")
    return query


def require_offset_paging_for_newest_first(config: CliConfig) -> None:
    """Refuse ``pipeline.newest_first`` with a source that pages by opaque cursor, before any request.

    Raises:
        click.UsageError: The source is not an ``OffsetListing``, so the run
            would raise ``ValueError`` in sci-etl-core.
    """
    if config.pipeline.newest_first and not config.source.pages_by_offset:
        raise click.UsageError(newest_first_message(config))


def require_offset_paging_for_start_index(config: CliConfig, start_index: int | None) -> None:
    """Refuse a listing offset above 0 with a source that pages by opaque cursor, before any request.

    Offset 0 is the first page for every source, so ``--rescan`` stays available.

    Raises:
        click.UsageError: The source is not an ``OffsetListing``.
    """
    if start_index and not config.source.pages_by_offset:
        raise click.UsageError(
            f"--start-index needs a source that pages by offset; {config.source.kind} pages by cursor. "
            "Use --rescan to start from the first page."
        )


def newest_first_message(config: CliConfig) -> str:
    return f"pipeline.newest_first needs a source that pages by offset; {config.source.kind} pages by cursor."
