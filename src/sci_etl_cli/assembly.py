from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from sci_etl_core.exceptions import ConfigurationError

from sci_etl_cli.errors import CliFailure

if TYPE_CHECKING:
    import httpx
    from sci_etl_core import (
        AsyncArxivExtractor,
        AsyncCsvExporter,
        AsyncETLPipeline,
        AsyncOpenAICompatibleClient,
        AsyncSqliteLLMResponseCache,
        AsyncSqliteStateManager,
        AsyncStateManager,
        PipelineMetadata,
    )
    from sci_etl_core.processors import RecordValidator
    from sci_etl_core.signals import ShutdownSignal

    from sci_etl_cli.settings import CliConfig


@dataclass(frozen=True, slots=True)
class ProjectParts:
    """What a run loads from the project folder before touching the network."""

    relevance_prompt: str
    extraction_prompt: str
    validators: tuple[RecordValidator, ...]


def load_project_parts(config: CliConfig) -> ProjectParts:
    """Read both prompts and build the plug-ins.

    Raises:
        ConfigurationError: A prompt file or a plug-in cannot be loaded.
    """
    return ProjectParts(
        relevance_prompt=read_prompt(config.prompts.relevance),
        extraction_prompt=read_prompt(config.prompts.extraction),
        validators=tuple(build_validators(config)),
    )


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


def build_validators(config: CliConfig) -> list[RecordValidator]:
    """Return the ``export.validators`` plug-ins in the order they are listed."""
    from sci_etl_core.processors import RecordValidator

    from sci_etl_cli.plugins import load_plugin, wrong_type

    validators: list[RecordValidator] = []
    for reference in config.export.validators:
        plugin = load_plugin(reference, config.project_root)
        if not isinstance(plugin, RecordValidator):
            raise wrong_type(reference, plugin, "RecordValidator")
        validators.append(plugin)
    return validators


def build_http_client(config: CliConfig) -> httpx.AsyncClient:
    return config.http.build_client()


def build_llm_client(config: CliConfig) -> AsyncOpenAICompatibleClient:
    from sci_etl_core import AsyncOpenAICompatibleClient

    return AsyncOpenAICompatibleClient.from_config(config.llm)


def build_llm_cache(config: CliConfig) -> AsyncSqliteLLMResponseCache | None:
    """Return the SQLite response cache at ``llm.cache``, or ``None`` when caching is off."""
    if config.llm.cache is None:
        return None
    from sci_etl_core import AsyncSqliteLLMResponseCache

    return AsyncSqliteLLMResponseCache(config.llm.cache)


def build_extractor(config: CliConfig, http_client: httpx.AsyncClient) -> AsyncArxivExtractor:
    """Build the arXiv extractor from the ``http``, ``pipeline``, and ``full_text`` sections."""
    from sci_etl_core import AsyncArxivExtractor
    from sci_etl_core.parsers import LatexTarballParser, PdfPlumberParser

    return AsyncArxivExtractor.from_config(
        config.http,
        config.pipeline,
        client=http_client,
        pdf_parser=PdfPlumberParser(),
        latex_parser=LatexTarballParser(),
        full_text=config.full_text,
    )


def build_state_manager(config: CliConfig) -> AsyncStateManager:
    if config.state.backend == "sqlite":
        from sci_etl_core import AsyncSqliteStateManager

        return AsyncSqliteStateManager(config.state.database)
    from sci_etl_core import AsyncFileStateManager

    return AsyncFileStateManager(config.state.processed_ids, config.state.metadata)


def build_exporter(config: CliConfig) -> AsyncCsvExporter:
    """Write one CSV row per entity: ``record_id``, the key and value columns, and ``extra``."""
    from sci_etl_core import AsyncCsvExporter

    export = config.export
    return AsyncCsvExporter(
        export.destination,
        [export.key_column, *export.value_columns],
        escape_formulas=export.escape_formulas,
    )


def build_pipeline(
    config: CliConfig,
    log: Callable[[str], None],
    http_client: httpx.AsyncClient,
    llm_client: AsyncOpenAICompatibleClient,
    llm_cache: AsyncSqliteLLMResponseCache | None,
    state_manager: AsyncStateManager,
    parts: ProjectParts,
    shutdown: ShutdownSignal,
) -> AsyncETLPipeline:
    """Assemble the pipeline, answering LLM requests from ``llm_cache`` when there is one.

    ``log`` receives one line per listing page. The validators run inside the
    entity extractor, which logs each rejected entity with its reasons.
    ``shutdown`` stops a run cleanly: records in flight finish and are marked
    processed, and ``run()`` raises ``PipelineInterrupted``.
    """
    from sci_etl_core import (
        AsyncETLPipeline,
        AsyncLLMEntityExtractor,
        AsyncLLMRelevanceFilter,
        AsyncSqliteStateManager,
        CachingLLMClient,
    )

    from sci_etl_cli.reporting import ListingReporter

    answering = llm_client if llm_cache is None else CachingLLMClient(llm_client, llm_cache, model=config.llm.model)
    entity_extractor: Any = AsyncLLMEntityExtractor(
        answering,
        parts.extraction_prompt,
        result_key=config.prompts.result_key,
        timeout=config.llm.timeout,
        validator=build_validator(parts.validators),
        label_field=config.export.key_column,
    )
    return AsyncETLPipeline.from_config(
        config.pipeline,
        extractor=ListingReporter(build_extractor(config, http_client), log),
        relevance_filter=AsyncLLMRelevanceFilter(llm_client=answering, system_prompt=parts.relevance_prompt),
        entity_extractor=entity_extractor,
        exporter=build_exporter(config),
        state_manager=state_manager,
        closeables=[
            http_client,
            llm_client,
            *([] if llm_cache is None else [llm_cache]),
            *_closeable_state(state_manager, AsyncSqliteStateManager),
        ],
        shutdown=shutdown,
    )


def build_validator(validators: tuple[RecordValidator, ...]) -> RecordValidator | None:
    """Combine the ``export.validators`` plug-ins into one validator, or ``None`` when there are none."""
    if not validators:
        return None
    from sci_etl_core.processors import CompositeValidator

    return CompositeValidator(list(validators))


def _closeable_state(
    state_manager: AsyncStateManager, closeable: type[AsyncSqliteStateManager]
) -> list[AsyncSqliteStateManager]:
    return [state_manager] if isinstance(state_manager, closeable) else []


async def read_state(config: CliConfig) -> tuple[set[str], PipelineMetadata]:
    """Load processed ids and metadata without creating state that does not exist yet."""
    from sci_etl_core.models import PipelineMetadata

    if _state_is_absent(config):
        return set(), PipelineMetadata()
    manager = build_state_manager(config)
    try:
        return await manager.load_processed_ids(), await manager.load_metadata()
    finally:
        await _release_state(manager)


@dataclass(frozen=True, slots=True)
class ForgetReport:
    """Which requested ids the state tracked and so forgot, and which it did not, each in request order."""

    forgotten: tuple[str, ...]
    untracked: tuple[str, ...]

    @property
    def requested(self) -> int:
        return len(self.forgotten) + len(self.untracked)


async def forget_records(config: CliConfig, record_ids: Sequence[str]) -> ForgetReport:
    """Clear the processed mark and failed attempts of every tracked id in ``record_ids``.

    Calls the state manager's ``forget``, which the ``Forgetting`` protocol
    describes, so the next run that lists the records again processes them
    again. An id the state neither processed nor failed is reported as
    untracked, a repeated id counts once, and state that does not exist yet
    is not created.

    Raises:
        CliFailure: The configured state manager cannot forget records.
    """
    from sci_etl_core import Forgetting

    requested = tuple(dict.fromkeys(record_ids))
    if _state_is_absent(config):
        return ForgetReport(forgotten=(), untracked=requested)
    manager = build_state_manager(config)
    try:
        if not isinstance(manager, Forgetting):
            raise CliFailure(f"The {config.state.backend} state backend cannot forget records")
        tracked = await manager.load_processed_ids() | (await manager.failure_counts()).keys()
        forgotten = tuple(record_id for record_id in requested if record_id in tracked)
        await manager.forget(forgotten)
    finally:
        await _release_state(manager)
    return ForgetReport(
        forgotten=forgotten, untracked=tuple(record_id for record_id in requested if record_id not in tracked)
    )


def _state_is_absent(config: CliConfig) -> bool:
    return config.state.backend == "sqlite" and not config.state.database.exists()


async def _release_state(manager: AsyncStateManager) -> None:
    aclose = getattr(manager, "aclose", None)
    if aclose is not None:
        await aclose()
