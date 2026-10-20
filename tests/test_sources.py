from __future__ import annotations

import csv
import io
import json

import pytest
import yaml
from sci_etl_core import (
    AsyncArxivExtractor,
    AsyncOpenAlexExtractor,
    AsyncPubMedExtractor,
    AsyncSemanticScholarExtractor,
)
from sci_etl_core.exceptions import ConfigurationError
from sci_etl_core.extractors.async_base import OffsetListing
from sci_etl_core.rate_limiter import SemaphoreRateLimiter

from sci_etl_cli.assembly import build_extractor, build_http_client
from sci_etl_cli.commands import validate
from sci_etl_cli.settings import load_cli_config

SOURCES = ("pubmed", "semantic_scholar", "openalex")
RECORDS = {
    "pubmed": [
        ("38000001", "Metformin versus placebo", "A randomized trial of metformin in type 2 diabetes."),
        ("38000002", "Metformin dose comparison", "Two doses of metformin were compared."),
    ],
    "semantic_scholar": [
        ("0123456789abcdef0123456789abcdef01234567", "Metformin versus placebo", "A randomized trial."),
        ("89abcdef0123456789abcdef0123456789abcdef", "Metformin dose comparison", "Two doses compared."),
    ],
    "openalex": [
        ("W2741809807", "Metformin versus placebo", "A randomized trial of metformin"),
        ("W2741809808", "Metformin dose comparison", "Two doses of metformin were compared"),
    ],
}
ID_LABELS = {"pubmed": "PMID", "semantic_scholar": "S2 paper id", "openalex": "OpenAlex work id"}
LABELS = {"pubmed": "PubMed", "semantic_scholar": "Semantic Scholar", "openalex": "OpenAlex"}
EXTRACTOR_TYPES = {
    "pubmed": AsyncPubMedExtractor,
    "semantic_scholar": AsyncSemanticScholarExtractor,
    "openalex": AsyncOpenAlexExtractor,
}
ARMS = [
    {"intervention": "metformin", "participants": 120, "duration_weeks": 24, "hba1c_change_percent": -1.1},
    {"intervention": "placebo", "participants": 118, "duration_weeks": 24, "hba1c_change_percent": -0.2},
]


def _csv_rows(path):
    return list(csv.DictReader(io.StringIO(path.read_text(encoding="utf-8"))))


def test_a_config_without_a_source_section_searches_arxiv(make_project):
    config = load_cli_config(make_project({"source": None}))
    assert (config.source.kind, config.source.label, config.source.pages_by_offset) == ("arxiv", "arXiv", True)


@pytest.mark.parametrize("source", SOURCES)
def test_each_starter_config_validates_and_names_its_kind(make_project, source):
    config = load_cli_config(make_project(source=source))
    assert config.source.kind == source
    assert config.source.api_key.get_secret_value() == ""


@pytest.mark.parametrize(
    ("source", "updates", "message"),
    [
        ("arxiv", {"source": {"kind": "arxiv", "mailto": "x"}}, "source.arxiv.mailto"),
        ("pubmed", {"source": {"kind": "pubmed", "year": "2020-"}}, "source.pubmed.year"),
        ("openalex", {"source": {"kind": "openalex", "tool": "x"}}, "source.openalex.tool"),
        ("arxiv", {"source": {"kind": "crossref"}}, "expected tags: 'arxiv', 'pubmed', 'semantic_scholar', 'openalex'"),
    ],
)
def test_a_key_another_source_takes_is_rejected_with_the_source_name(make_project, source, updates, message):
    with pytest.raises(ConfigurationError, match=message):
        load_cli_config(make_project(updates, source=source))


def test_the_source_api_key_comes_from_the_named_variable_in_the_dotenv(make_project, monkeypatch):
    config_path = make_project({"source": {"api_key_env": "NCBI_KEY"}}, source="pubmed")
    (config_path.parent / ".env").write_text("NCBI_KEY=ncbi-secret\n", encoding="utf-8")
    monkeypatch.delenv("NCBI_KEY", raising=False)
    config = load_cli_config(config_path)
    assert config.source.api_key.get_secret_value() == "ncbi-secret"
    assert "ncbi-secret" not in repr(config.source)


def test_the_source_api_key_in_the_environment_wins_over_the_file(make_project, monkeypatch):
    config_path = make_project({"source": {"api_key": "from-file"}}, source="openalex")
    monkeypatch.setenv("SOURCE_API_KEY", "from-env")
    assert load_cli_config(config_path).source.api_key.get_secret_value() == "from-env"
    monkeypatch.delenv("SOURCE_API_KEY")
    assert load_cli_config(config_path).source.api_key.get_secret_value() == "from-file"


@pytest.mark.parametrize("source", SOURCES)
@pytest.mark.asyncio
async def test_build_extractor_matches_the_source_and_takes_http_and_rate_settings(make_project, source):
    updates = {"http": {"max_retries": 5}, "full_text": {"max_concurrency": 3}}
    config = load_cli_config(make_project(updates, source=source))
    client = build_http_client(config)
    try:
        extractor = build_extractor(config, client)
        assert isinstance(extractor, EXTRACTOR_TYPES[source])
        assert isinstance(extractor, OffsetListing) == config.source.pages_by_offset
        assert extractor._fetcher._max_retries == 5
        assert isinstance(extractor._fetcher._rate_limiter, SemaphoreRateLimiter)
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_build_extractor_passes_the_source_options_and_key(make_project, monkeypatch):
    monkeypatch.setenv("SOURCE_API_KEY", "s2-secret")
    updates = {"source": {"year": "2020-", "fields_of_study": "Medicine"}}
    config = load_cli_config(make_project(updates, source="semantic_scholar"))
    client = build_http_client(config)
    try:
        extractor = build_extractor(config, client)
        assert extractor._filters == {"year": "2020-", "fieldsOfStudy": "Medicine"}
        assert extractor._fetcher._headers == {"x-api-key": "s2-secret"}
    finally:
        await client.aclose()
    arxiv = load_cli_config(make_project(directory="arxiv"))
    client = build_http_client(arxiv)
    try:
        assert isinstance(build_extractor(arxiv, client), AsyncArxivExtractor)
    finally:
        await client.aclose()


@pytest.mark.parametrize("source", SOURCES)
def test_validate_passes_each_starter_and_names_the_source(run_cli, make_project, source):
    result = run_cli("validate", str(make_project(source=source)))
    assert result.exit_code == 0, result.stdout
    assert f"{LABELS[source]}, no API key (SOURCE_API_KEY is not set)" in result.stdout
    assert "fail" not in result.stdout


def test_validate_reports_the_source_key_and_the_extras_the_source_needs(run_cli, make_project, monkeypatch):
    monkeypatch.setenv("SOURCE_API_KEY", "ncbi-secret")
    result = run_cli("validate", str(make_project(source="pubmed")))
    assert result.exit_code == 0, result.stdout
    assert "PubMed, SOURCE_API_KEY is set" in result.stdout
    assert "ncbi-secret" not in result.stdout
    assert "yaml, httpx, openai, lxml" in result.stdout

    monkeypatch.setattr(validate, "find_spec", lambda name: None if name in {"lxml", "httpx"} else object())
    result = run_cli("validate", str(make_project(source="pubmed", directory="again")))
    assert result.exit_code == 4
    assert 'missing: httpx, lxml; install with: pip install "sci-etl-core[async,xml]"' in result.stdout


def test_validate_refuses_newest_first_with_a_cursor_paged_source(run_cli, make_project):
    result = run_cli("validate", str(make_project({"pipeline": {"newest_first": True}}, source="openalex")))
    assert result.exit_code == 3
    assert "pipeline.newest_first needs a source that pages by offset; openalex pages by cursor" in result.stdout


@pytest.mark.parametrize("source", SOURCES)
def test_validate_online_reaches_each_source(run_cli, make_project, source_api, llm, source):
    api = source_api(source, RECORDS[source])
    llm()
    result = run_cli("validate", str(make_project(source=source)), "--online")
    assert result.exit_code == 0, result.stdout
    assert f"{LABELS[source]}" in result.stdout
    assert "listing request succeeded" in result.stdout
    assert api.requests


@pytest.mark.parametrize("source", SOURCES)
def test_validate_online_reports_a_source_failure(run_cli, make_project, source_api, llm, source):
    source_api(source, [], listing_status=503)
    llm()
    result = run_cli("validate", str(make_project(source=source)), "--online")
    assert result.exit_code == 1
    assert f"{LABELS[source]} search failed after 1 attempts" in result.stdout


@pytest.mark.parametrize("source", SOURCES)
def test_search_labels_the_id_column_by_source_and_marks_processed_records(run_cli, make_project, source_api, source):
    config_path = make_project(source=source)
    state = config_path.parent / "state"
    state.mkdir()
    (state / "processed_ids.txt").write_text(f"{RECORDS[source][1][0]}\n", encoding="utf-8")
    source_api(source, RECORDS[source])

    result = run_cli("search", str(config_path), "--limit", "2")

    assert result.exit_code == 0, result.stderr
    assert ID_LABELS[source] in result.stdout
    first, second = RECORDS[source][0][0], RECORDS[source][1][0]
    assert any(first in line and "new" in line for line in result.stdout.splitlines())
    assert any(second in line and "processed" in line for line in result.stdout.splitlines())
    listed = json.loads(run_cli("search", str(config_path), "--limit", "2", "--json").stdout)
    assert [(record["record_id"], record["processed"]) for record in listed] == [(first, False), (second, True)]


def test_search_start_index_pages_an_offset_source_and_is_refused_for_a_cursor_source(
    run_cli, make_project, source_api
):
    api = source_api("pubmed", RECORDS["pubmed"])
    result = run_cli("search", str(make_project(source="pubmed")), "--start-index", "1", "--limit", "1", "--json")
    assert result.exit_code == 0, result.stderr
    assert [record["record_id"] for record in json.loads(result.stdout)] == ["38000002"]
    assert api.requests[0].url.params["retstart"] == "1"

    api = source_api("openalex", RECORDS["openalex"])
    result = run_cli("search", str(make_project(source="openalex", directory="alex")), "--start-index", "1")
    assert result.exit_code == 2
    assert "--start-index needs a source that pages by offset; openalex pages by cursor" in result.stderr
    assert api.requests == []


@pytest.mark.parametrize("source", SOURCES)
def test_run_exports_entities_from_each_source(run_cli, make_project, source_api, llm, source):
    config_path = make_project({"llm": {"cache": None}}, source=source)
    api = source_api(source, RECORDS[source])
    client = llm(entities=ARMS, result_key="trials")

    result = run_cli("run", str(config_path), "--limit", "1")

    assert result.exit_code == 0, result.stderr
    first_id = RECORDS[source][0][0]
    rows = _csv_rows(config_path.parent / "out" / "trials.csv")
    assert [(row["record_id"], row["intervention"], row["hba1c_change_percent"]) for row in rows] == [
        (first_id, "metformin", "-1.1"),
        (first_id, "placebo", "-0.2"),
    ]
    assert "Processed 1 relevant record" in result.stderr
    processed = (config_path.parent / "state" / "processed_ids.txt").read_text(encoding="utf-8").split()
    assert processed == [first_id]
    assert len(client.requests) == 2
    assert {request.url.host for request in api.requests} >= {api.requests[0].url.host}


def test_run_feeds_pubmed_central_full_text_to_the_llm(run_cli, make_project, source_api, llm):
    config_path = make_project({"llm": {"cache": None}}, source="pubmed")
    source_api("pubmed", RECORDS["pubmed"][:1])
    client = llm(entities=ARMS, result_key="trials")

    result = run_cli("run", str(config_path))

    assert result.exit_code == 0, result.stderr
    assert "Full text of 38000001." in client.requests[-1]
    assert "Listing page at offset 0: 1 entries" in result.stderr


def test_run_falls_back_to_the_abstract_when_the_open_access_pdf_is_missing(run_cli, make_project, source_api, llm):
    config_path = make_project({"llm": {"cache": None}}, source="openalex")
    api = source_api("openalex", RECORDS["openalex"][:1])
    client = llm(entities=ARMS, result_key="trials")

    result = run_cli("run", str(config_path))

    assert result.exit_code == 0, result.stderr
    assert "A randomized trial of metformin" in client.requests[-1]
    assert any(request.url.host == "oa.test" for request in api.requests)
    assert "Listing page 1: 1 entries" in result.stderr
    metadata = yaml.safe_load((config_path.parent / "state" / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["cursor"] is None


def test_run_rescan_restarts_a_cursor_paged_source_from_its_first_page(run_cli, make_project, source_api, llm):
    config_path = make_project({"llm": {"cache": None}}, source="openalex")
    api = source_api("openalex", RECORDS["openalex"])
    llm(entities=ARMS, result_key="trials")

    result = run_cli("run", str(config_path), "--rescan")

    assert result.exit_code == 0, result.stderr
    assert api.requests[0].url.params["cursor"] == "*"


@pytest.mark.parametrize(
    ("updates", "options", "message"),
    [
        ({"pipeline": {"newest_first": True}}, [], "pipeline.newest_first needs a source that pages by offset"),
        ({}, ["--start-index", "5"], "--start-index needs a source that pages by offset; openalex pages by cursor"),
    ],
)
def test_run_refuses_offsets_and_newest_first_for_a_cursor_paged_source(
    run_cli, make_project, source_api, updates, options, message
):
    api = source_api("openalex", RECORDS["openalex"])
    result = run_cli("run", str(make_project(updates, source="openalex")), *options)
    assert result.exit_code == 2
    assert message in result.stderr
    assert api.requests == []


@pytest.mark.parametrize("source", SOURCES)
def test_init_source_writes_a_starter_that_validates_and_searches_offline(run_cli, tmp_path, source_api, source):
    target = tmp_path / source
    result = run_cli("init", str(target), "--source", source)
    assert result.exit_code == 0, result.stdout
    config = yaml.safe_load((target / "config.yaml").read_text(encoding="utf-8"))
    assert config["source"]["kind"] == source
    assert "SOURCE_API_KEY=" in (target / ".env.example").read_text(encoding="utf-8")
    assert "astro" not in (target / "prompts" / "relevance.txt").read_text(encoding="utf-8")

    validated = run_cli("validate", str(target / "config.yaml"))
    assert validated.exit_code == 0, validated.stdout

    source_api(source, RECORDS[source])
    searched = run_cli("search", str(target / "config.yaml"), "--json")
    assert searched.exit_code == 0, searched.stderr
    assert [record["record_id"] for record in json.loads(searched.stdout)] == [r[0] for r in RECORDS[source]]


def test_init_rejects_an_unknown_source(run_cli, tmp_path):
    result = run_cli("init", str(tmp_path / "x"), "--source", "crossref")
    assert result.exit_code == 2
    assert "crossref" in result.stderr
