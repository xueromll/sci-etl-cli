from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import click
from sci_etl_core.exceptions import PipelineAborted, PipelineInterrupted
from sci_etl_core.signals import ShutdownSignal

from sci_etl_cli import assembly
from sci_etl_cli.errors import ExitCode, describe_abort
from sci_etl_cli.options import config_argument, require_api_key, require_query
from sci_etl_cli.output import run_logger, stderr_console
from sci_etl_cli.settings import CliConfig, load_cli_config
from sci_etl_cli.usage import describe_usage


@click.command("run")
@config_argument
@click.option(
    "--limit",
    type=click.IntRange(min=0),
    help="Stop after this many relevant records. Overrides pipeline.total_limit.",
)
@click.option(
    "--page-size",
    type=click.IntRange(min=1),
    help="Listing entries per request. Overrides pipeline.page_size.",
)
@click.option(
    "--workers",
    type=click.IntRange(min=1),
    help="Records processed at once. Overrides pipeline.max_concurrency.",
)
@click.option(
    "--rescan",
    is_flag=True,
    help="Start at offset 0 to pick up new submissions; processed records are skipped.",
)
@click.option(
    "--start-index",
    type=click.IntRange(min=0),
    help="Start at this listing offset instead of the saved one.",
)
@click.option(
    "--log-file",
    type=click.Path(dir_okay=False, path_type=Path),
    help="Write the log to this file. Overrides logging.file.",
)
def run_command(
    config_path: Path,
    limit: int | None,
    page_size: int | None,
    workers: int | None,
    rescan: bool,
    start_index: int | None,
    log_file: Path | None,
) -> None:
    """Run the pipeline for CONFIG, resuming from its saved state.

    Searches arXiv, asks the LLM which papers are relevant, extracts entities
    from their full text, and writes them to the export CSV, one row per entity
    tagged with its paper's arXiv id. Press Ctrl+C
    once to let the papers in progress finish and save state; the next run
    continues with the rest. Press it again to stop at once.
    """
    if rescan and start_index is not None:
        raise click.UsageError("Use either --rescan or --start-index, not both.")
    config = apply_overrides(
        load_cli_config(config_path), limit=limit, page_size=page_size, workers=workers, log_file=log_file
    )
    if config.pipeline.newest_first and (rescan or start_index is not None):
        raise click.UsageError("--rescan and --start-index cannot be combined with pipeline.newest_first.")
    require_query(config.pipeline.search_query)
    require_api_key(config)
    parts = assembly.load_project_parts(config)

    ctx = click.get_current_context()
    with run_logger(config.logging.level, config.logging.file, stderr_console()) as log:
        try:
            processed = asyncio.run(execute(config, log, parts, 0 if rescan else start_index))
        except PipelineInterrupted as interrupted:
            log.warning(
                f"Interrupted after {describe_count(interrupted.partial_count)}; state was saved. "
                "Run the same command again to continue."
            )
            ctx.exit(ExitCode.INTERRUPTED)
        except PipelineAborted as aborted:
            log.error(f"Run aborted: {describe_abort(aborted)}")
            ctx.exit(ExitCode.FAILURE)
        log.info(f"Processed {describe_count(processed)} into {config.export.destination}")


def apply_overrides(
    config: CliConfig,
    *,
    limit: int | None,
    page_size: int | None,
    workers: int | None,
    log_file: Path | None,
) -> CliConfig:
    requested = {"total_limit": limit, "page_size": page_size, "max_concurrency": workers}
    pipeline = config.pipeline.model_copy(
        update={name: value for name, value in requested.items() if value is not None}
    )
    logging_config = config.logging if log_file is None else config.logging.model_copy(update={"file": log_file})
    return config.model_copy(update={"pipeline": pipeline, "logging": logging_config})


def describe_count(count: int) -> str:
    return f"{count} relevant record{'' if count == 1 else 's'}"


async def execute(
    config: CliConfig,
    log: logging.Logger,
    parts: assembly.ProjectParts,
    start_index: int | None,
) -> int:
    """Run the pipeline with every ``run()`` argument taken from ``pipeline``.

    Raises:
        PipelineInterrupted: Ctrl+C stopped the run after the records in
            flight finished; state is flushed.
        PipelineAborted: The run failed; state is flushed.
    """
    http_client = assembly.build_http_client(config)
    llm_client = assembly.build_llm_client(config)
    llm_cache = assembly.build_llm_cache(config)
    state_manager = assembly.build_state_manager(config)
    pipeline = assembly.build_pipeline(
        config, log.info, http_client, llm_client, llm_cache, state_manager, parts, ShutdownSignal()
    )
    arguments = config.pipeline.run_arguments()
    if start_index is not None:
        arguments["start_index"] = start_index
    log.info(
        f"Starting run for {config.pipeline.search_query!r}, up to {describe_count(config.pipeline.total_limit)}"
    )
    try:
        async with pipeline:
            return await pipeline.run(**arguments)
    finally:
        summary = describe_usage(llm_client.usage, config.llm)
        if summary is not None:
            log.info(summary)
