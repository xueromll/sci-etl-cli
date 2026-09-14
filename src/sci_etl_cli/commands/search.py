from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass
from pathlib import Path

import click
from rich.markup import escape
from rich.table import Table

from sci_etl_cli import assembly
from sci_etl_cli.options import config_argument, require_query
from sci_etl_cli.output import discard, print_json, stdout_console
from sci_etl_cli.settings import CliConfig, load_cli_config

_ARXIV_MAX_RESULTS = 2000


@dataclass(frozen=True, slots=True)
class ListedRecord:
    record_id: str
    title: str
    url: str | None
    processed: bool


@click.command("search", short_help="Preview arXiv results without calling the LLM.")
@config_argument
@click.option("--query", help="Search this instead of pipeline.search_query.")
@click.option(
    "--limit",
    type=click.IntRange(1, _ARXIV_MAX_RESULTS),
    default=10,
    show_default=True,
    help="Number of entries to request.",
)
@click.option(
    "--start-index",
    type=click.IntRange(min=0),
    default=0,
    show_default=True,
    help="Listing offset to start from.",
)
@click.option("--json", "as_json", is_flag=True, help="Print JSON instead of a table.")
def search_command(config_path: Path, query: str | None, limit: int, start_index: int, as_json: bool) -> None:
    """Show one page of arXiv results for CONFIG without calling the LLM.

    Each entry is marked new or processed according to the saved state, so a
    query can be tuned before spending tokens. Nothing is written.
    """
    config = load_cli_config(config_path)
    search_query = require_query(query or config.pipeline.search_query)
    listed = asyncio.run(fetch_page(config, search_query, limit, start_index))
    if as_json:
        print_json([asdict(record) for record in listed])
        return
    console = stdout_console()
    if not listed:
        console.print(f"No entries at offset {start_index}.")
        return
    table = Table("id", "status", "title")
    for record in listed:
        status = "[yellow]processed[/]" if record.processed else "[green]new[/]"
        table.add_row(record.record_id, status, escape(record.title))
    console.print(table)


async def fetch_page(config: CliConfig, query: str, limit: int, start_index: int) -> list[ListedRecord]:
    processed_ids, _metadata = await assembly.read_state(config)
    http_client = assembly.build_http_client(config)
    try:
        extractor = assembly.build_extractor(config, http_client, discard)
        raw_listing = await extractor.search(query, limit, start_index)
        records, _entries = extractor.parse_listing(raw_listing or b"", set())
    finally:
        await http_client.aclose()
    return [
        ListedRecord(record.record_id, record.title, record.source_url, record.record_id in processed_ids)
        for record in records
    ]
