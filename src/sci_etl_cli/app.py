from __future__ import annotations

from importlib.metadata import version
from typing import Any

import click
from sci_etl_core.exceptions import SciEtlError

from sci_etl_cli.commands.init import init_command
from sci_etl_cli.commands.parse import parse_command
from sci_etl_cli.commands.run import run_command
from sci_etl_cli.commands.search import search_command
from sci_etl_cli.commands.status import status_command
from sci_etl_cli.commands.validate import validate_command
from sci_etl_cli.errors import to_cli_failure

_EXIT_CODES = """\b
Exit codes:
  0    success
  1    run aborted, or a request or parse failed
  2    invalid command-line usage
  3    configuration problem
  4    missing Python package
  130  interrupted after saving state"""


class SciEtlGroup(click.Group):
    """Command group that reports library errors as one line and an exit code."""

    def invoke(self, ctx: click.Context) -> Any:
        try:
            return super().invoke(ctx)
        except (SciEtlError, ModuleNotFoundError) as error:
            raise to_cli_failure(error) from error


def _print_version(ctx: click.Context, _param: click.Parameter, value: bool) -> None:
    if not value or ctx.resilient_parsing:
        return
    click.echo(f"sci-etl {version('sci-etl-cli')} (sci-etl-core {version('sci-etl-core')})")
    ctx.exit()


@click.group(
    cls=SciEtlGroup,
    context_settings={"help_option_names": ["-h", "--help"]},
    epilog=_EXIT_CODES,
)
@click.option(
    "--version",
    is_flag=True,
    expose_value=False,
    is_eager=True,
    callback=_print_version,
    help="Show the CLI and library versions and exit.",
)
def cli() -> None:
    """Run sci-etl-core extraction pipelines from a YAML config file."""


cli.add_command(init_command)
cli.add_command(validate_command)
cli.add_command(search_command)
cli.add_command(run_command)
cli.add_command(status_command)
cli.add_command(parse_command)


def main() -> None:
    cli(prog_name="sci-etl")
