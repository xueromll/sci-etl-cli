from __future__ import annotations

import sys
from collections.abc import Callable, Iterator
from importlib import resources
from pathlib import Path
from typing import Any

import httpx
import pytest
import yaml
from click.testing import CliRunner, Result
from sci_etl_core.llm.async_base import AsyncLLMClient
from sci_etl_core.models import TokenUsage

from sci_etl_cli import assembly
from sci_etl_cli.app import cli

Listing = dict[int, list[tuple[str, str, str]]]

_TEMPLATES = resources.files("sci_etl_cli").joinpath("templates")
_FEED = '<?xml version="1.0" encoding="UTF-8"?>\n<feed xmlns="http://www.w3.org/2005/Atom">{entries}</feed>'
_ENTRY = (
    "<entry><id>http://arxiv.org/abs/{record_id}</id><title>{title}</title>"
    "<summary>{abstract}</summary>"
    '<link href="http://arxiv.org/abs/{record_id}" rel="alternate" type="text/html"/></entry>'
)
PLUGIN_SOURCE = '''from sci_etl_core.processors import NumericRangeValidator, RecordValidator

NOT_CALLABLE = 42


class NamedPlanets(RecordValidator):
    def is_valid(self, record):
        return bool(str(record.get("planet_name") or "").strip())


class NotAValidator:
    pass


def short_period_planets():
    return NumericRangeValidator({"orbital_period_days": (0.0, 10.0)})


def broken_factory():
    raise RuntimeError("needs a catalogue file")
'''


class ScriptedLLM(AsyncLLMClient):
    def __init__(
        self,
        relevant: bool = True,
        entities: list[dict[str, Any]] | None = None,
        error: Exception | None = None,
        usage: TokenUsage | None = None,
        on_extraction: Callable[[], None] | None = None,
        result_key: str = "planets",
    ) -> None:
        self.relevant = relevant
        self.entities = entities if entities is not None else []
        self.result_key = result_key
        self.error = error
        self.token_usage = usage
        self.on_extraction = on_extraction
        self.requests: list[str] = []
        self.closed = False

    @property
    def usage(self) -> TokenUsage | None:
        return self.token_usage

    async def complete_json(self, system_prompt: str, user_content: str, timeout: int | None = None) -> dict[str, Any]:
        self.requests.append(user_content)
        if self.error is not None:
            raise self.error
        if '"relevant"' in system_prompt:
            return {"relevant": self.relevant}
        if self.on_extraction is not None:
            self.on_extraction()
        return {self.result_key: self.entities}

    async def aclose(self) -> None:
        self.closed = True


def atom_feed(records: list[tuple[str, str, str]]) -> bytes:
    entries = "".join(
        _ENTRY.format(record_id=record_id, title=title, abstract=abstract) for record_id, title, abstract in records
    )
    return _FEED.format(entries=entries).encode("utf-8")


def _template(name: str) -> str:
    return _TEMPLATES.joinpath(name).read_text(encoding="utf-8")


_EFETCH = (
    '<?xml version="1.0" ?>\n<PubmedArticleSet>{articles}</PubmedArticleSet>'
)
_PUBMED_ARTICLE = (
    "<PubmedArticle><MedlineCitation><PMID>{record_id}</PMID><Article>"
    "<Journal><JournalIssue><PubDate><Year>2024</Year></PubDate></JournalIssue><Title>Diabetes Care</Title></Journal>"
    "<ArticleTitle>{title}</ArticleTitle><Abstract><AbstractText>{abstract}</AbstractText></Abstract>"
    "</Article></MedlineCitation><PubmedData><ArticleIdList>"
    '<ArticleId IdType="pubmed">{record_id}</ArticleId><ArticleId IdType="pmc">PMC{record_id}</ArticleId>'
    "</ArticleIdList></PubmedData></PubmedArticle>"
)
JATS_ARTICLE = (
    '<?xml version="1.0" encoding="UTF-8"?><pmc-articleset><article article-type="research-article"><front>'
    "<article-meta><title-group><article-title>{title}</article-title></title-group>"
    "<abstract><p>{abstract}</p></abstract></article-meta></front>"
    "<body><sec><title>Results</title><p>{body}</p></sec></body></article></pmc-articleset>"
)


def pubmed_articles(records: list[tuple[str, str, str]]) -> bytes:
    articles = "".join(
        _PUBMED_ARTICLE.format(record_id=record_id, title=title, abstract=abstract)
        for record_id, title, abstract in records
    )
    return _EFETCH.format(articles=articles).encode("utf-8")


def semantic_scholar_paper(record_id: str, title: str, abstract: str) -> dict[str, Any]:
    return {
        "paperId": record_id,
        "title": title,
        "abstract": abstract,
        "year": 2023,
        "publicationDate": "2023-05-01",
        "authors": [{"name": "Grace"}],
        "externalIds": {"DOI": f"10.2/{record_id}"},
        "url": f"https://www.semanticscholar.org/paper/{record_id}",
        "venue": "Diabetes Care",
        "fieldsOfStudy": ["Medicine"],
        "openAccessPdf": {"url": f"https://oa.test/{record_id}.pdf"},
    }


def openalex_work(record_id: str, title: str, abstract: str) -> dict[str, Any]:
    return {
        "id": f"https://openalex.org/{record_id}",
        "display_name": title,
        "abstract_inverted_index": {word: [position] for position, word in enumerate(abstract.split())},
        "doi": f"https://doi.org/10.1/{record_id}",
        "publication_date": "2024-03-07",
        "publication_year": 2024,
        "authorships": [{"author": {"display_name": "Ada"}}],
        "topics": [{"display_name": "Diabetes"}],
        "primary_location": {"source": {"display_name": "Diabetes Care"}, "landing_page_url": "https://journal.test/w"},
        "best_oa_location": {"pdf_url": f"https://oa.test/{record_id}.pdf"},
    }


class SourceApi:
    """Serve one source's listing and full-text endpoints from ``records`` through an ``httpx.MockTransport``.

    PubMed full text is a small JATS article; the open-access PDFs of the
    other sources answer 404, so their full text falls back to the abstract.
    """

    def __init__(self, kind: str, records: list[tuple[str, str, str]], listing_status: int = 200) -> None:
        self.kind = kind
        self.records = records
        self.listing_status = listing_status
        self.requests: list[httpx.Request] = []

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handle)

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        host = request.url.host
        if host == "eutils.ncbi.nlm.nih.gov":
            return self._pubmed(request)
        if host == "api.semanticscholar.org":
            return self._listing(self._semantic_scholar, request)
        if host == "api.openalex.org":
            return self._listing(self._openalex, request)
        return httpx.Response(404)

    def _listing(self, build: Callable[[httpx.Request], Any], request: httpx.Request) -> httpx.Response:
        if self.listing_status != 200:
            return httpx.Response(self.listing_status)
        return httpx.Response(200, json=build(request))

    def _pubmed(self, request: httpx.Request) -> httpx.Response:
        params = request.url.params
        if request.url.path.endswith("esearch.fcgi"):
            if self.listing_status != 200:
                return httpx.Response(self.listing_status)
            start, size = int(params.get("retstart", 0)), int(params["retmax"])
            ids = [record_id for record_id, _title, _abstract in self.records][start : start + size]
            return httpx.Response(200, json={"esearchresult": {"idlist": ids, "count": str(len(self.records))}})
        if params["db"] == "pubmed":
            wanted = params["id"].split(",")
            return httpx.Response(200, content=pubmed_articles([r for r in self.records if r[0] in wanted]))
        record_id, title, abstract = next(r for r in self.records if f"PMC{r[0]}".endswith(params["id"]))
        body = JATS_ARTICLE.format(title=title, abstract=abstract, body=f"Full text of {record_id}.")
        return httpx.Response(200, content=body.encode("utf-8"))

    def _semantic_scholar(self, request: httpx.Request) -> dict[str, Any]:
        params = request.url.params
        start, limit = int(params["offset"]), int(params["limit"])
        papers = [semantic_scholar_paper(*record) for record in self.records[start : start + limit]]
        return {"total": len(self.records), "data": papers}

    def _openalex(self, request: httpx.Request) -> dict[str, Any]:
        if request.url.params["cursor"] != "*":
            return {"meta": {"next_cursor": None}, "results": []}
        works = [openalex_work(*record) for record in self.records[: int(request.url.params["per-page"])]]
        return {"meta": {"next_cursor": "next" if works else None}, "results": works}


@pytest.fixture(autouse=True)
def plain_terminal(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TERM", "dumb")
    monkeypatch.setenv("COLUMNS", "240")
    for name in ("FORCE_COLOR", "TTY_COMPATIBLE", "TTY_INTERACTIVE"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("LLM_API_KEY", "test-key")


@pytest.fixture
def run_cli() -> Callable[..., Result]:
    runner = CliRunner()

    def invoke(*args: str) -> Result:
        return runner.invoke(cli, list(args), catch_exceptions=False)

    return invoke


@pytest.fixture
def make_project(tmp_path: Path) -> Callable[..., Path]:
    """Write a starter project from the templates of ``source`` (arXiv by default) with fast retries and no waits."""

    def make(updates: dict[str, Any] | None = None, directory: str = "project", source: str = "arxiv") -> Path:
        from sci_etl_cli.commands.init import STARTERS

        starter = STARTERS[source]
        root = tmp_path / directory
        (root / "prompts").mkdir(parents=True, exist_ok=True)
        raw = yaml.safe_load(_template(starter.config))
        raw["pipeline"].update({"search_delay": 0, "sleep_between": 0})
        raw["http"].update({"backoff_factor": 0, "max_retries": 1})
        raw.pop("full_text", None)
        for section, values in (updates or {}).items():
            if values is None:
                raw.pop(section, None)
            elif isinstance(values, dict) and isinstance(raw.get(section), dict):
                raw[section].update(values)
            else:
                raw[section] = values
        (root / "config.yaml").write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
        for template, relative in starter.files()[1:3]:
            (root / relative).write_text(_template(template), encoding="utf-8")
        return root / "config.yaml"

    return make


@pytest.fixture
def write_plugins() -> Iterator[Callable[..., str]]:
    written: list[str] = []

    def write(folder: Path, module_name: str) -> str:
        (folder / f"{module_name}.py").write_text(PLUGIN_SOURCE, encoding="utf-8")
        written.append(module_name)
        return module_name

    yield write
    for module_name in written:
        sys.modules.pop(module_name, None)


@pytest.fixture
def arxiv(monkeypatch: pytest.MonkeyPatch) -> Callable[..., list[httpx.Request]]:
    def install(pages: Listing, listing_status: int = 200) -> list[httpx.Request]:
        requests: list[httpx.Request] = []

        def handle(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            if request.url.host != "export.arxiv.org":
                return httpx.Response(404)
            if listing_status != 200:
                return httpx.Response(listing_status)
            return httpx.Response(200, content=atom_feed(pages.get(int(request.url.params["start"]), [])))

        transport = httpx.MockTransport(handle)
        monkeypatch.setattr(assembly, "build_http_client", lambda config: httpx.AsyncClient(transport=transport))
        return requests

    return install


@pytest.fixture
def llm(monkeypatch: pytest.MonkeyPatch) -> Callable[..., ScriptedLLM]:
    def install(**kwargs: Any) -> ScriptedLLM:
        client = ScriptedLLM(**kwargs)
        monkeypatch.setattr(assembly, "build_llm_client", lambda config: client)
        return client

    return install


@pytest.fixture
def source_api(monkeypatch: pytest.MonkeyPatch) -> Callable[..., SourceApi]:
    """Serve PubMed, Semantic Scholar, or OpenAlex from ``records`` and record every request."""

    def install(kind: str, records: list[tuple[str, str, str]], listing_status: int = 200) -> SourceApi:
        api = SourceApi(kind, records, listing_status)
        monkeypatch.setattr(assembly, "build_http_client", lambda config: httpx.AsyncClient(transport=api.transport()))
        return api

    return install
