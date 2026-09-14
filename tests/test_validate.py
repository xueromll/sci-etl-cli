from __future__ import annotations

from sci_etl_core.exceptions import LLMError

from sci_etl_cli.commands import validate


def test_valid_project_passes_every_offline_check(run_cli, make_project):
    result = run_cli("validate", str(make_project()))
    assert result.exit_code == 0
    assert "fail" not in result.stdout
    assert "LLM_API_KEY is set" in result.stdout
    assert "test-key" not in result.stdout


def test_missing_api_key_exits_three(run_cli, make_project, monkeypatch):
    monkeypatch.delenv("LLM_API_KEY")
    result = run_cli("validate", str(make_project()))
    assert result.exit_code == 3
    assert "LLM_API_KEY is not set" in result.stdout


def test_prompts_missing_required_terms_are_reported(run_cli, make_project):
    config_path = make_project()
    prompts = config_path.parent / "prompts"
    (prompts / "relevance.txt").write_text("Is this paper about hot Jupiters?", encoding="utf-8")
    (prompts / "extraction.txt").write_text("Return JSON with planets and planet_name.", encoding="utf-8")
    result = run_cli("validate", str(config_path))
    assert result.exit_code == 3
    assert "never mentions: JSON, relevant" in result.stdout
    assert "never mentions: orbital_period_days, mass_jupiter, radius_jupiter" in result.stdout


def test_missing_prompt_and_empty_query_are_reported(run_cli, make_project):
    config_path = make_project({"pipeline": {"search_query": ""}})
    (config_path.parent / "prompts" / "relevance.txt").unlink()
    result = run_cli("validate", str(config_path))
    assert result.exit_code == 3
    assert "Prompt file not found" in result.stdout
    assert "pipeline.search_query is empty" in result.stdout


def test_missing_package_takes_precedence_with_exit_code_four(run_cli, make_project, monkeypatch):
    monkeypatch.delenv("LLM_API_KEY")
    monkeypatch.setattr(validate, "find_spec", lambda name: None if name == "pdfplumber" else object())
    result = run_cli("validate", str(make_project()))
    assert result.exit_code == 4
    assert "missing: pdfplumber (sci-etl-core[pdf])" in result.stdout


def test_online_checks_reach_arxiv_and_the_llm(run_cli, make_project, arxiv, llm):
    requests = arxiv({0: [("2609.00001v1", "Tidal decay of WASP-12 b", "We measure WASP-12 b.")]})
    client = llm()
    result = run_cli("validate", str(make_project()), "--online")
    assert result.exit_code == 0, result.stdout
    assert "listing request succeeded" in result.stdout
    assert "gpt-4o-mini answered in JSON mode" in result.stdout
    assert requests[0].url.params["max_results"] == "1"
    assert len(client.requests) == 1
    assert client.closed


def test_online_failures_exit_one(run_cli, make_project, arxiv, llm):
    arxiv({}, listing_status=503)
    llm(error=LLMError("401 invalid api key"))
    result = run_cli("validate", str(make_project()), "--online")
    assert result.exit_code == 1
    assert "arXiv search failed after 1 attempts" in result.stdout
    assert "401 invalid api key" in result.stdout


def test_query_matching_nothing_fails_the_online_check(run_cli, make_project, arxiv, llm):
    arxiv({})
    llm()
    result = run_cli("validate", str(make_project()), "--online")
    assert result.exit_code == 1
    assert "the search query matched no entries" in result.stdout


def test_online_checks_wait_for_offline_checks_to_pass(run_cli, make_project, arxiv, monkeypatch):
    requests = arxiv({})
    monkeypatch.delenv("LLM_API_KEY")
    result = run_cli("validate", str(make_project()), "--online")
    assert result.exit_code == 3
    assert requests == []
