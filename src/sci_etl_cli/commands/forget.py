from __future__ import annotations

import asyncio
from pathlib import Path

import click
from rich.markup import escape
from rich.table import Table

from sci_etl_cli import assembly
from sci_etl_cli.options import config_argument
from sci_etl_cli.output import print_json, stdout_console
from sci_etl_cli.settings import CliConfig, load_cli_config


@click.command("forget", short_help="Hand processed or failed records back to the next rescan.")
@config_argument
@click.argument("record_ids", metavar="RECORD_ID...", nargs=-1, required=True)
@click.option("--json", "as_json", is_flag=True, help="Print JSON instead of a table.")
def forget_command(config_path: Path, record_ids: tuple[str, ...], as_json: bool) -> None:
    """Forget RECORD_IDs in CONFIG's state so the next rescan processes them again.

    Clears each record's processed mark and failed attempts, for example after
    a prompt or model change. The saved offset is kept, so follow it with
    `run --rescan`, which starts at offset 0 and skips every other processed
    record by id. A record's rows in the export CSV stay until it is processed
    again, which replaces them. Use it between runs: a run reads the processed
    ids when it starts. An id the state does not track is reported, not an
    error.
    """
    config = load_cli_config(config_path)
    report = asyncio.run(assembly.forget_records(config, record_ids))
    if as_json:
        print_json({"forgotten": list(report.forgotten), "untracked": list(report.untracked)})
        return

    table = Table(show_header=False, box=None, pad_edge=False)
    table.add_column(no_wrap=True)
    table.add_column(no_wrap=True)
    for record_id in report.forgotten:
        table.add_row(escape(record_id), "[green]forgotten[/]")
    for record_id in report.untracked:
        table.add_row(escape(record_id), "[yellow]not tracked[/]")
    console = stdout_console()
    console.print(table)
    console.print(f"Forgot {len(report.forgotten)} of {describe_count(report.requested)}.")
    console.print(escape(next_step(config, config_path)), soft_wrap=True)


def describe_count(count: int) -> str:
    return f"{count} record{'' if count == 1 else 's'}"


def next_step(config: CliConfig, config_path: Path) -> str:
    """Name the run that processes the forgotten records again, which depends on ``pipeline.newest_first``."""
    command = f"sci-etl run {config_path} --rescan"
    if config.pipeline.newest_first:
        return (
            f"Next: pipeline.newest_first is set and a rescan cannot be combined with it, "
            f"so turn it off for one run and use: {command}"
        )
    return f"Next: {command}"
