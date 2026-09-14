from __future__ import annotations

import csv
import io

from sci_etl_core.exceptions import LLMError

from sci_etl_cli import shutdown

PAGE = {
    0: [
        ("2609.00001v1", "Tidal decay of WASP-12 b", "We measure the orbital period of WASP-12 b."),
        ("2609.00002v1", "Phase curve of HAT-P-7 b", "We observe the phase curve of HAT-P-7 b."),
    ]
}
ENTITIES = [{"planet_name": "WASP-12 b", "orbital_period_days": 1.09, "mass_jupiter": 1.47, "radius_jupiter": 1.9}]


def _csv_rows(path):
    return list(csv.DictReader(io.StringIO(path.read_text(encoding="utf-8"))))


def test_run_exports_entities_saves_state_and_logs(run_cli, make_project, arxiv, llm):
    config_path = make_project()
    root = config_path.parent
    arxiv(PAGE)
    client = llm(entities=ENTITIES)

    result = run_cli("run", str(config_path))

    assert result.exit_code == 0, result.stderr
    rows = _csv_rows(root / "out" / "planets.csv")
    assert [(row["planet_name"], row["orbital_period_days"]) for row in rows] == [("WASP-12 b", "1.09")]
    processed = set((root / "state" / "processed_ids.txt").read_text(encoding="utf-8").split())
    assert processed == {"2609.00001v1", "2609.00002v1"}
    assert "Processed 2 relevant records" in result.stderr
    log_text = (root / "logs" / "run.log").read_text(encoding="utf-8")
    assert "Listing page at offset 0: 2 entries, 2 to process" in log_text
    assert "Processed 2 relevant records" in log_text
    assert client.closed


def test_run_applies_overrides_with_sqlite_state(run_cli, make_project, arxiv, llm, tmp_path):
    config_path = make_project({"state": {"backend": "sqlite"}})
    requests = arxiv(PAGE)
    llm(entities=ENTITIES)
    log_file = tmp_path / "custom" / "run.log"

    result = run_cli(
        "run", str(config_path), "--limit", "1", "--page-size", "2", "--workers", "1",
        "--start-index", "0", "--log-file", str(log_file),
    )

    assert result.exit_code == 0, result.stderr
    assert requests[0].url.params["max_results"] == "2"
    assert "Processed 1 relevant record into" in log_file.read_text(encoding="utf-8")
    database = config_path.parent / "state" / "state.db"
    assert database.is_file()
    database.unlink()


def test_aborted_run_exits_one_and_logs_the_cause(run_cli, make_project, arxiv, llm):
    arxiv(PAGE)
    llm(error=LLMError("401 invalid api key"))
    result = run_cli("run", str(make_project()))
    assert result.exit_code == 1
    assert "Run aborted" in result.stderr
    assert "401 invalid api key" in result.stderr


def test_missing_api_key_exits_three_before_any_request(run_cli, make_project, arxiv, monkeypatch):
    requests = arxiv(PAGE)
    monkeypatch.delenv("LLM_API_KEY")
    result = run_cli("run", str(make_project()))
    assert result.exit_code == 3
    assert "LLM_API_KEY is not set" in result.stderr
    assert requests == []


def test_rescan_and_start_index_together_are_a_usage_error(run_cli, make_project):
    result = run_cli("run", str(make_project()), "--rescan", "--start-index", "5")
    assert result.exit_code == 2
    assert "--rescan or --start-index" in result.stderr


def test_interrupted_run_exits_130(run_cli, make_project, arxiv, llm, monkeypatch):
    arxiv(PAGE)
    llm(entities=ENTITIES)

    async def interrupted(run, _shutdown, state_manager):
        run.close()
        await state_manager.flush()
        return None

    monkeypatch.setattr(shutdown, "run_until_interrupted", interrupted)
    result = run_cli("run", str(make_project()), "--rescan")
    assert result.exit_code == 130
    assert "state was saved" in result.stderr
