from __future__ import annotations

import asyncio
import csv
from pathlib import Path
from typing import Any

import click
from rich.markup import escape
from rich.table import Table

from sci_etl_cli import assembly
from sci_etl_cli.errors import CliFailure, ExitCode
from sci_etl_cli.options import config_argument
from sci_etl_cli.output import print_json, stdout_console
from sci_etl_cli.settings import CliConfig, load_cli_config


@click.command("status", short_help="Show processed records, saved offset and export rows.")
@config_argument
@click.option("--json", "as_json", is_flag=True, help="Print JSON instead of a table.")
def status_command(config_path: Path, as_json: bool) -> None:
    """Show CONFIG's progress: processed records, saved offset, last run and export rows.

    Reads state without creating it, so this is safe before the first run.
    """
    config = load_cli_config(config_path)
    processed_ids, metadata = asyncio.run(assembly.read_state(config))
    report: dict[str, Any] = {
        "config": str(config_path.resolve()),
        "backend": config.state.backend,
        "state": [str(path) for path in state_paths(config)],
        "processed": len(processed_ids),
        "saved_offset": metadata.last_start_index,
        "last_run": metadata.last_run_at,
        "export": str(config.export.destination),
        "export_rows": count_rows(config.export.destination),
    }
    if as_json:
        print_json(report)
        return

    rows = report["export_rows"]
    table = Table(show_header=False, box=None, pad_edge=False)
    table.add_column(no_wrap=True)
    table.add_column(overflow="fold")
    table.add_row("config", escape(report["config"]))
    table.add_row("backend", report["backend"])
    table.add_row("state", escape("\n".join(report["state"])))
    table.add_row("processed", f"{report['processed']} records")
    table.add_row("saved offset", str(report["saved_offset"]))
    table.add_row("last run", escape(report["last_run"] or "never"))
    table.add_row("export", escape(report["export"]))
    table.add_row("rows", "not created yet" if rows is None else str(rows))
    stdout_console().print(table)


def state_paths(config: CliConfig) -> tuple[Path, ...]:
    if config.state.backend == "sqlite":
        return (config.state.database,)
    return (config.state.processed_ids, config.state.metadata)


def count_rows(path: Path) -> int | None:
    """Count data rows in the export CSV, or return ``None`` when it does not exist yet.

    Raises:
        CliFailure: The file exists but cannot be read as UTF-8 CSV.
    """
    if not path.is_file():
        return None
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            return max(sum(1 for _row in csv.reader(handle)) - 1, 0)
    except (OSError, UnicodeDecodeError, csv.Error) as exc:
        raise CliFailure(f"Export file could not be read: {path}: {exc}", ExitCode.FAILURE) from exc
