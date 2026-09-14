from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import click
from sci_etl_core.exceptions import PipelineAborted
from sci_etl_core.signals import ShutdownSignal

from sci_etl_cli import assembly, shutdown
from sci_etl_cli.errors import ExitCode, describe_abort
from sci_etl_cli.options import config_argument, require_api_key, require_query
from sci_etl_cli.output import run_logger, stderr_console
from sci_etl_cli.settings import CliConfig, load_cli_config


@click.command("run")
@config_argument
@click.option(
    "--limit",
    type=click.IntRange(min=0),
    help="Stop after this many relevant records. Overrides pipeline.max_records.",
)
@click.option(
    "--page-size",
    type=click.IntRange(min=1),
    help="Listing entries per request. Overrides pipeline.page_size.",
)
@click.option(
    "--workers",
    type=click.IntRange(min=1),
    help="Records processed at once. Overrides pipeline.max_workers.",
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
    from their full text and upserts them into the export CSV. Press Ctrl+C
    once to stop after saving state; the next run retries unfinished records.
    """
    if rescan and start_index is not None:
        raise click.UsageError("Use either --rescan or --start-index, not both.")
    config = apply_overrides(
        load_cli_config(config_path), limit=limit, page_size=page_size, workers=workers, log_file=log_file
    )
    require_query(config.pipeline.search_query)
    require_api_key(config)
    relevance_prompt = assembly.read_prompt(config.prompts.relevance)
    extraction_prompt = assembly.read_prompt(config.prompts.extraction)

    ctx = click.get_current_context()
    with run_logger(config.logging.level, config.logging.file, stderr_console()) as log:
        try:
            processed = asyncio.run(
                execute(config, log, relevance_prompt, extraction_prompt, 0 if rescan else start_index)
            )
        except PipelineAborted as aborted:
            log.error(f"Run aborted: {describe_abort(aborted)}")
            ctx.exit(ExitCode.FAILURE)
        if processed is None:
            log.warning("Interrupted; state was saved. Run the same command again to continue.")
            ctx.exit(ExitCode.INTERRUPTED)
        log.info(f"Processed {describe_count(processed)} into {config.export.destination}")


def apply_overrides(
    config: CliConfig,
    *,
    limit: int | None,
    page_size: int | None,
    workers: int | None,
    log_file: Path | None,
) -> CliConfig:
    requested = {"max_records": limit, "page_size": page_size, "max_workers": workers}
    pipeline = config.pipeline.model_copy(update={name: value for name, value in requested.items() if value is not None})
    logging_config = config.logging if log_file is None else config.logging.model_copy(update={"file": log_file})
    return config.model_copy(update={"pipeline": pipeline, "logging": logging_config})


def describe_count(count: int) -> str:
    return f"{count} relevant record{'' if count == 1 else 's'}"


async def execute(
    config: CliConfig,
    log: logging.Logger,
    relevance_prompt: str,
    extraction_prompt: str,
    start_index: int | None,
) -> int | None:
    http_client = assembly.build_http_client(config)
    llm_client = assembly.build_llm_client(config)
    state_manager = assembly.build_state_manager(config)
    pipeline = assembly.build_pipeline(
        config, log, http_client, llm_client, state_manager, relevance_prompt, extraction_prompt
    )
    log.info(
        f"Starting run for {config.pipeline.search_query!r}, up to {describe_count(config.pipeline.max_records)}"
    )
    async with pipeline:
        return await shutdown.run_until_interrupted(
            pipeline.run(
                query=config.pipeline.search_query,
                page_size=config.pipeline.page_size,
                total_limit=config.pipeline.max_records,
                sleep_between=config.pipeline.sleep_between,
                start_index=start_index,
            ),
            ShutdownSignal(logger=log.warning),
            state_manager,
        )
