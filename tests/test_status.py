from __future__ import annotations

import json
import re


def test_status_of_a_fresh_project(run_cli, make_project):
    result = run_cli("status", str(make_project()))
    assert result.exit_code == 0
    assert "0 records" in result.stdout
    assert "never" in result.stdout
    assert "not created yet" in result.stdout


def test_status_reports_state_and_export_rows(run_cli, make_project):
    config_path = make_project()
    root = config_path.parent
    (root / "state").mkdir()
    (root / "state" / "processed_ids.txt").write_text("2609.00001v1\n2609.00002v1\n", encoding="utf-8")
    (root / "state" / "metadata.json").write_text(
        json.dumps({"last_run_date": "2026-09-14T18:02:41+00:00", "last_start_index": 100}), encoding="utf-8"
    )
    (root / "out").mkdir()
    (root / "out" / "planets.csv").write_text(
        'planet_name,orbital_period_days\n"WASP-12 b",1.09\n"HAT-P-7 b",2.2\n', encoding="utf-8"
    )

    report = json.loads(run_cli("status", str(config_path), "--json").stdout)
    assert report["backend"] == "file"
    assert len(report["state"]) == 2
    assert report["config"].endswith("config.yaml")
    assert (report["processed"], report["saved_offset"], report["export_rows"]) == (2, 100, 2)
    assert report["last_run"] == "2026-09-14T18:02:41+00:00"

    text = run_cli("status", str(config_path)).stdout
    assert "2 records" in text
    assert re.search(r"^rows\s+2\s*$", text, re.MULTILINE)
    assert "2026-09-14T18:02:41+00:00" in text


def test_status_of_a_sqlite_project_names_the_database(run_cli, make_project):
    result = run_cli("status", str(make_project({"state": {"backend": "sqlite"}})), "--json")
    report = json.loads(result.stdout)
    assert report["backend"] == "sqlite"
    assert report["state"][0].endswith("state.db")


def test_unreadable_export_exits_one(run_cli, make_project):
    config_path = make_project()
    (config_path.parent / "out").mkdir()
    (config_path.parent / "out" / "planets.csv").write_bytes(b"planet_name\n\xff\xfe\n")
    result = run_cli("status", str(config_path))
    assert result.exit_code == 1
    assert "Export file could not be read" in result.stderr
