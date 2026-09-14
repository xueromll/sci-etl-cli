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
PLUGIN_SOURCE = '''from sci_etl_core.processors import DefaultKeyNormalizer, KeyNormalizer, NumericRangeValidator

NOT_CALLABLE = 42


class DesignationNormalizer(KeyNormalizer):
    def normalize(self, raw_value):
        key = DefaultKeyNormalizer().normalize(raw_value)
        return "wasp" + key[len("superwasp"):] if key.startswith("superwasp") else key


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
    ) -> None:
        self.relevant = relevant
        self.entities = entities if entities is not None else []
        self.error = error
        self.token_usage = usage
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
        return {"planets": self.entities}

    async def aclose(self) -> None:
        self.closed = True


def atom_feed(records: list[tuple[str, str, str]]) -> bytes:
    entries = "".join(
        _ENTRY.format(record_id=record_id, title=title, abstract=abstract) for record_id, title, abstract in records
    )
    return _FEED.format(entries=entries).encode("utf-8")


def _template(name: str) -> str:
    return _TEMPLATES.joinpath(name).read_text(encoding="utf-8")


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
    def make(updates: dict[str, Any] | None = None, directory: str = "project") -> Path:
        root = tmp_path / directory
        (root / "prompts").mkdir(parents=True, exist_ok=True)
        raw = yaml.safe_load(_template("config.yaml"))
        raw["pipeline"].update({"search_delay": 0, "sleep_between": 0})
        raw["http"].update({"backoff_factor": 0, "max_retries": 1})
        for section, values in (updates or {}).items():
            if values is None:
                raw.pop(section, None)
            elif isinstance(values, dict) and isinstance(raw.get(section), dict):
                raw[section].update(values)
            else:
                raw[section] = values
        (root / "config.yaml").write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
        for name in ("relevance.txt", "extraction.txt"):
            (root / "prompts" / name).write_text(_template(name), encoding="utf-8")
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
