from __future__ import annotations

import pytest
from sci_etl_core import AsyncOpenAICompatibleClient, AsyncSqliteStateManager, PipelineMetadata
from sci_etl_core.exceptions import ConfigurationError
from sci_etl_core.extractors.async_base import AsyncExtractor
from sci_etl_core.models import RawRecord

from sci_etl_cli.assembly import (
    build_http_client,
    build_llm_client,
    build_state_manager,
    read_prompt,
    read_state,
)
from sci_etl_cli.reporting import ListingReporter
from sci_etl_cli.settings import load_cli_config


def test_missing_prompt_is_reported(tmp_path):
    with pytest.raises(ConfigurationError, match="Prompt file not found"):
        read_prompt(tmp_path / "missing.txt")


def test_unreadable_prompt_is_reported(tmp_path):
    with pytest.raises(ConfigurationError, match="could not be read"):
        read_prompt(tmp_path)


def test_prompt_that_is_not_utf8_is_reported(tmp_path):
    prompt = tmp_path / "latin1.txt"
    prompt.write_bytes(b"Donn\xe9es en JSON")
    with pytest.raises(ConfigurationError, match="could not be read"):
        read_prompt(prompt)


def test_blank_prompt_is_reported(tmp_path):
    prompt = tmp_path / "blank.txt"
    prompt.write_text("  \n", encoding="utf-8")
    with pytest.raises(ConfigurationError, match="empty"):
        read_prompt(prompt)


@pytest.mark.asyncio
async def test_http_client_sends_the_configured_user_agent(make_project):
    config = load_cli_config(make_project())
    client = build_http_client(config)
    try:
        assert client.headers["User-Agent"] == config.http.user_agent
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_llm_client_uses_the_openai_compatible_client(make_project):
    client = build_llm_client(load_cli_config(make_project()))
    try:
        assert isinstance(client, AsyncOpenAICompatibleClient)
    finally:
        await client.aclose()


@pytest.mark.parametrize(
    ("backend", "manager_type"),
    [("file", "AsyncFileStateManager"), ("sqlite", "AsyncSqliteStateManager")],
)
def test_state_manager_matches_the_backend(make_project, backend, manager_type):
    manager = build_state_manager(load_cli_config(make_project({"state": {"backend": backend}})))
    assert type(manager).__name__ == manager_type


@pytest.mark.asyncio
async def test_reading_missing_sqlite_state_creates_nothing(make_project):
    config = load_cli_config(make_project({"state": {"backend": "sqlite"}}))
    processed_ids, metadata = await read_state(config)
    assert (processed_ids, metadata.last_start_index) == (set(), 0)
    assert not config.state.database.exists()


@pytest.mark.asyncio
async def test_reading_existing_sqlite_state_releases_the_database(make_project):
    config = load_cli_config(make_project({"state": {"backend": "sqlite"}}))
    writer = AsyncSqliteStateManager(config.state.database)
    await writer.mark_processed("2609.00001v1")
    await writer.save_metadata(PipelineMetadata(last_start_index=100))
    await writer.aclose()
    processed_ids, metadata = await read_state(config)
    assert processed_ids == {"2609.00001v1"}
    assert metadata.last_start_index == 100
    config.state.database.unlink()


@pytest.mark.asyncio
async def test_listing_reporter_logs_pages_and_delegates(mocker):
    record = RawRecord("2609.00001v1", "WASP-12 b", "Tidal decay")
    inner = mocker.Mock(spec=AsyncExtractor)
    inner.search = mocker.AsyncMock(return_value=b"<feed/>")
    inner.parse_listing = mocker.Mock(side_effect=[([record], 3), ([], 0)])
    inner.fetch_full_text = mocker.AsyncMock(return_value="full text")
    messages: list[str] = []
    reporter = ListingReporter(inner, messages.append)

    assert await reporter.search("abs:WASP-12", 3, 100) == b"<feed/>"
    assert reporter.parse_listing(b"<feed/>", set()) == ([record], 3)
    assert reporter.parse_listing(b"<feed/>", set()) == ([], 0)
    assert await reporter.fetch_full_text(record) == "full text"
    assert messages == ["Listing page at offset 100: 3 entries, 1 to process"]
