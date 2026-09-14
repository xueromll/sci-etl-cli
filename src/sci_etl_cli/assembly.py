from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Callable

from sci_etl_core.exceptions import ConfigurationError

if TYPE_CHECKING:
    import logging

    import httpx
    from sci_etl_core import (
        AsyncETLPipeline,
        AsyncExporter,
        AsyncExtractor,
        AsyncLLMClient,
        AsyncOpenAICompatibleClient,
        AsyncStateManager,
        PipelineMetadata,
    )

    from sci_etl_cli.settings import CliConfig


def read_prompt(path: Path) -> str:
    """Return a prompt file's text.

    Raises:
        ConfigurationError: The file is missing, unreadable, not UTF-8, or blank.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ConfigurationError(f"Prompt file not found: {path}") from exc
    except (OSError, UnicodeDecodeError) as exc:
        raise ConfigurationError(f"Prompt file could not be read: {path}: {exc}") from exc
    if not text.strip():
        raise ConfigurationError(f"Prompt file is empty: {path}")
    return text


def build_http_client(config: CliConfig) -> httpx.AsyncClient:
    from sci_etl_core.http_async import build_async_client

    return build_async_client(timeout=config.http.timeout, user_agent=config.http.user_agent)


def build_llm_client(config: CliConfig) -> AsyncOpenAICompatibleClient:
    from sci_etl_core import AsyncOpenAICompatibleClient

    return AsyncOpenAICompatibleClient(
        api_key=config.llm.api_key,
        base_url=config.llm.base_url,
        model=config.llm.model,
        default_timeout=config.llm.timeout,
    )


def build_extractor(
    config: CliConfig, http_client: httpx.AsyncClient, log: Callable[[str], None]
) -> AsyncExtractor:
    from sci_etl_core import AsyncArxivExtractor
    from sci_etl_core.parsers import LatexTarballParser, PdfPlumberParser

    return AsyncArxivExtractor(
        client=http_client,
        pdf_parser=PdfPlumberParser(),
        latex_parser=LatexTarballParser(),
        max_retries=config.http.max_retries,
        backoff_factor=config.http.backoff_factor,
        sleep_before_search=config.pipeline.search_delay,
        logger=log,
    )


def build_state_manager(config: CliConfig) -> AsyncStateManager:
    if config.state.backend == "sqlite":
        from sci_etl_core import AsyncSqliteStateManager

        return AsyncSqliteStateManager(config.state.database)
    from sci_etl_core import AsyncFileStateManager

    return AsyncFileStateManager(config.state.processed_ids, config.state.metadata)


def build_exporter(config: CliConfig) -> AsyncExporter:
    from sci_etl_core import AsyncCsvUpsertExporter
    from sci_etl_core.processors import DefaultKeyNormalizer

    export = config.export
    return AsyncCsvUpsertExporter(
        key_column=export.key_column,
        value_columns=list(export.value_columns),
        normalizer=DefaultKeyNormalizer(),
        numeric_clip=dict(export.numeric_clip),
        escape_formulas=export.escape_formulas,
    )


def build_pipeline(
    config: CliConfig,
    log: logging.Logger,
    http_client: httpx.AsyncClient,
    llm_client: AsyncLLMClient,
    state_manager: AsyncStateManager,
    relevance_prompt: str,
    extraction_prompt: str,
) -> AsyncETLPipeline:
    from sci_etl_core import AsyncETLPipeline, AsyncLLMEntityExtractor, AsyncLLMRelevanceFilter

    from sci_etl_cli.reporting import ListingReporter

    return AsyncETLPipeline(
        extractor=ListingReporter(build_extractor(config, http_client, log.info), log.info),
        relevance_filter=AsyncLLMRelevanceFilter(llm_client=llm_client, system_prompt=relevance_prompt),
        entity_extractor=AsyncLLMEntityExtractor(
            llm_client=llm_client,
            system_prompt=extraction_prompt,
            result_key=config.prompts.result_key,
            timeout=config.llm.timeout,
        ),
        exporter=build_exporter(config),
        state_manager=state_manager,
        destination=str(config.export.destination),
        max_concurrency=config.pipeline.max_workers,
        logger=log.warning,
        closeables=[http_client, llm_client, state_manager],
    )


async def read_state(config: CliConfig) -> tuple[set[str], PipelineMetadata]:
    """Load processed ids and metadata without creating state that does not exist yet."""
    from sci_etl_core.models import PipelineMetadata

    if config.state.backend == "sqlite" and not config.state.database.exists():
        return set(), PipelineMetadata()
    manager = build_state_manager(config)
    try:
        return await manager.load_processed_ids(), await manager.load_metadata()
    finally:
        aclose = getattr(manager, "aclose", None)
        if aclose is not None:
            await aclose()
