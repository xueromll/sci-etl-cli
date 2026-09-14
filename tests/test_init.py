from __future__ import annotations

_WRITTEN = ("config.yaml", "prompts/relevance.txt", "prompts/extraction.txt", ".env.example")


def test_init_writes_a_project_that_validates(run_cli, tmp_path):
    target = tmp_path / "hot-jupiters"
    result = run_cli("init", str(target))
    assert result.exit_code == 0
    for relative in _WRITTEN:
        assert (target / relative).is_file()
    assert "sci-etl validate" in result.stdout
    validated = run_cli("validate", str(target / "config.yaml"))
    assert validated.exit_code == 0, validated.stdout


def test_init_refuses_to_overwrite_without_force(run_cli, tmp_path):
    (tmp_path / "config.yaml").write_text("mine", encoding="utf-8")
    result = run_cli("init", str(tmp_path))
    assert result.exit_code == 2
    assert "--force" in result.stderr
    assert (tmp_path / "config.yaml").read_text(encoding="utf-8") == "mine"
    assert not (tmp_path / "prompts").exists()


def test_init_force_replaces_existing_files(run_cli, tmp_path):
    (tmp_path / "config.yaml").write_text("mine", encoding="utf-8")
    result = run_cli("init", str(tmp_path), "--force")
    assert result.exit_code == 0
    assert "search_query" in (tmp_path / "config.yaml").read_text(encoding="utf-8")


def test_init_defaults_to_the_current_folder(run_cli, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert run_cli("init").exit_code == 0
    assert (tmp_path / "prompts" / "extraction.txt").is_file()
