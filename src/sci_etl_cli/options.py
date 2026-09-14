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
