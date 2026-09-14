from __future__ import annotations

import json


def test_search_marks_processed_records(run_cli, make_project, arxiv):
    config_path = make_project()
    state = config_path.parent / "state"
    state.mkdir()
    (state / "processed_ids.txt").write_text("2609.00002v1\n", encoding="utf-8")
    arxiv(
        {
            0: [
                ("2609.00001v1", "TOI-6255 b: an ultra-short-period hot Jupiter", "We report TOI-6255 b."),
                ("2609.00002v1", "Tidal decay of WASP-12 b", "We measure WASP-12 b."),
            ]
        }
    )
    result = run_cli("search", str(config_path), "--limit", "2")
    assert result.exit_code == 0
    lines = result.stdout.splitlines()
    assert any("2609.00001v1" in line and "new" in line for line in lines)
    assert any("2609.00002v1" in line and "processed" in line for line in lines)


def test_search_json_honors_query_limit_and_offset(run_cli, make_project, arxiv):
    requests = arxiv({5: [("2609.00003v1", "Phase curve of HAT-P-7 b", "We observe HAT-P-7 b.")]})
    result = run_cli(
        "search", str(make_project()), "--query", "abs:HAT-P-7", "--limit", "3", "--start-index", "5", "--json"
    )
    assert result.exit_code == 0
    assert json.loads(result.stdout) == [
        {
            "record_id": "2609.00003v1",
            "title": "Phase curve of HAT-P-7 b",
            "url": "http://arxiv.org/abs/2609.00003v1",
            "processed": False,
        }
    ]
    params = requests[0].url.params
    assert (params["search_query"], params["max_results"], params["start"]) == ("abs:HAT-P-7", "3", "5")


def test_search_without_entries_says_so(run_cli, make_project, arxiv):
    arxiv({})
    result = run_cli("search", str(make_project()))
    assert result.exit_code == 0
    assert "No entries at offset 0." in result.stdout


def test_search_without_a_query_exits_three_before_any_request(run_cli, make_project, arxiv):
    requests = arxiv({})
    result = run_cli("search", str(make_project({"pipeline": {"search_query": ""}})))
    assert result.exit_code == 3
    assert "No search query" in result.stderr
    assert requests == []


def test_upstream_failure_exits_one(run_cli, make_project, arxiv):
    arxiv({}, listing_status=503)
    result = run_cli("search", str(make_project()))
    assert result.exit_code == 1
    assert "arXiv search failed after 1 attempts" in result.stderr
