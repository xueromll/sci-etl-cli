from __future__ import annotations

import asyncio
import json
import re

from sci_etl_core import AsyncFileStateManager, AsyncSqliteStateManager
from sci_etl_core.state.async_base import AsyncStateManager

from sci_etl_cli import assembly
from sci_etl_cli.commands.run import describe_count
from sci_etl_cli.settings import load_cli_config

PAGE = {
    0: [
        ("2609.00001v1", "Tidal decay of WASP-12 b", "We measure the orbital period of WASP-12 b."),
        ("2609.00002v1", "Phase curve of HAT-P-7 b", "We observe the phase curve of HAT-P-7 b."),
    ]
}
ENTITIES = [{"planet_name": "WASP-12 b", "orbital_period_days": 1.09, "mass_jupiter": 1.47, "radius_jupiter": 1.9}]


async def _seed_file_state(config) -> None:
    manager = AsyncFileStateManager(config.state.processed_ids, config.state.metadata)
    await manager.mark_processed("2609.00001v1")
    await manager.mark_processed("2609.00002v1")
    await manager.record_failure("2609.00003v1", "parse failed")


async def _seed_sqlite_state(config) -> None:
    manager = AsyncSqliteStateManager(config.state.database)
    try:
        await manager.mark_processed("2609.00001v1")
        await manager.record_failure("2609.00003v1", "parse failed")
    finally:
        await manager.aclose()


async def _sqlite_state(config) -> tuple[set[str], dict[str, int]]:
    manager = AsyncSqliteStateManager(config.state.database)
    try:
        return await manager.load_processed_ids(), await manager.failure_counts()
    finally:
        await manager.aclose()


def test_forget_clears_processed_marks_and_failed_attempts_in_file_state(run_cli, make_project):
    config_path = make_project()
    config = load_cli_config(config_path)
    asyncio.run(_seed_file_state(config))

    result = run_cli("forget", str(config_path), "2609.00001v1", "2609.00003v1", "2609.00009v1", "2609.00001v1")

    assert result.exit_code == 0, result.stderr
    assert re.search(r"^2609\.00001v1\s+forgotten\s*$", result.stdout, re.MULTILINE)
    assert re.search(r"^2609\.00003v1\s+forgotten\s*$", result.stdout, re.MULTILINE)
    assert re.search(r"^2609\.00009v1\s+not tracked\s*$", result.stdout, re.MULTILINE)
    assert result.stdout.count("2609.00001v1") == 1
    assert "Forgot 2 of 3 records." in result.stdout
    assert f"Next: sci-etl run {config_path} --rescan" in result.stdout
    assert config.state.processed_ids.read_text(encoding="utf-8").split() == ["2609.00002v1"]
    manager = AsyncFileStateManager(config.state.processed_ids, config.state.metadata)
    assert asyncio.run(manager.failure_counts()) == {}


def test_forget_json_reports_sqlite_state_and_releases_the_database(run_cli, make_project):
    config_path = make_project({"state": {"backend": "sqlite"}})
    config = load_cli_config(config_path)
    asyncio.run(_seed_sqlite_state(config))

    result = run_cli("forget", str(config_path), "2609.00003v1", "2609.00002v1", "2609.00001v1", "--json")

    assert result.exit_code == 0, result.stderr
    assert json.loads(result.stdout) == {"forgotten": ["2609.00003v1", "2609.00001v1"], "untracked": ["2609.00002v1"]}
    assert asyncio.run(_sqlite_state(config)) == (set(), {})
    config.state.database.unlink()


def test_forget_in_a_fresh_sqlite_project_creates_no_database(run_cli, make_project):
    config_path = make_project({"state": {"backend": "sqlite"}})
    result = run_cli("forget", str(config_path), "2609.00001v1")
    assert result.exit_code == 0, result.stderr
    assert re.search(r"^2609\.00001v1\s+not tracked\s*$", result.stdout, re.MULTILINE)
    assert "Forgot 0 of 1 record." in result.stdout
    assert not (config_path.parent / "state" / "state.db").exists()


def test_forget_in_a_fresh_file_project_creates_no_state(run_cli, make_project):
    config_path = make_project()
    result = run_cli("forget", str(config_path), "2609.00001v1")
    assert result.exit_code == 0, result.stderr
    assert "Forgot 0 of 1 record." in result.stdout
    assert not (config_path.parent / "state").exists()


def test_forget_with_newest_first_explains_the_rescan(run_cli, make_project):
    config_path = make_project({"pipeline": {"newest_first": True}})
    result = run_cli("forget", str(config_path), "2609.00001v1")
    assert result.exit_code == 0, result.stderr
    assert "pipeline.newest_first is set" in result.stdout
    assert f"turn it off for one run and use: sci-etl run {config_path} --rescan" in result.stdout


def test_forget_without_ids_is_a_usage_error(run_cli, make_project):
    result = run_cli("forget", str(make_project()))
    assert result.exit_code == 2
    assert "RECORD_ID" in result.stderr


def test_forget_with_a_state_manager_that_cannot_forget_exits_one(run_cli, make_project, monkeypatch):
    class Plain(AsyncStateManager):
        closed = False

        async def load_processed_ids(self) -> set[str]:
            return {"2609.00001v1"}

        async def mark_processed(self, record_id: str) -> None:
            raise AssertionError("not called")

        async def load_metadata(self):
            raise AssertionError("not called")

        async def save_metadata(self, metadata) -> None:
            raise AssertionError("not called")

        async def aclose(self) -> None:
            self.closed = True

    manager = Plain()
    monkeypatch.setattr(assembly, "build_state_manager", lambda config: manager)
    result = run_cli("forget", str(make_project()), "2609.00001v1")
    assert result.exit_code == 1
    assert "The file state backend cannot forget records" in result.stderr
    assert manager.closed


def test_a_forgotten_record_is_processed_again_by_the_next_rescan(run_cli, make_project, arxiv, llm):
    config_path = make_project({"llm": {"cache": None}})
    arxiv(PAGE)
    client = llm(entities=ENTITIES)
    assert run_cli("run", str(config_path)).exit_code == 0
    assert len(client.requests) == 4

    assert run_cli("forget", str(config_path), "2609.00002v1").exit_code == 0
    result = run_cli("run", str(config_path), "--rescan")

    assert result.exit_code == 0, result.stderr
    assert f"Processed {describe_count(1)}" in result.stderr
    assert len(client.requests) == 6
    processed = set((config_path.parent / "state" / "processed_ids.txt").read_text(encoding="utf-8").split())
    assert processed == {"2609.00001v1", "2609.00002v1"}
