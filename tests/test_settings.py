from __future__ import annotations

import os

import pytest
from sci_etl_core.exceptions import ConfigurationError

from sci_etl_cli.settings import load_cli_config


def test_relative_paths_resolve_from_the_config_folder(make_project):
    config_path = make_project()
    root = config_path.resolve().parent
    config = load_cli_config(config_path)
    assert config.prompts.relevance == root / "prompts" / "relevance.txt"
    assert config.prompts.extraction == root / "prompts" / "extraction.txt"
    assert config.export.destination == root / "out" / "planets.csv"
    assert config.state.processed_ids == root / "state" / "processed_ids.txt"
    assert config.state.database == root / "state" / "state.db"
    assert config.logging.file == root / "logs" / "run.log"


def test_project_root_is_the_config_folder(make_project):
    config_path = make_project()
    assert load_cli_config(config_path).project_root == config_path.resolve().parent


def test_absolute_paths_are_kept_and_logging_can_be_disabled(make_project, tmp_path):
    destination = tmp_path / "elsewhere" / "planets.csv"
    config = load_cli_config(make_project({"export": {"destination": str(destination)}, "logging": {"file": None}}))
    assert config.export.destination == destination
    assert config.logging.file is None


def test_api_key_comes_from_the_named_variable_in_the_dotenv_beside_the_config(make_project, monkeypatch):
    config_path = make_project({"llm": {"api_key_env": "SCI_ETL_CLI_TEST_KEY"}})
    monkeypatch.delenv("SCI_ETL_CLI_TEST_KEY", raising=False)
    (config_path.parent / ".env").write_text("SCI_ETL_CLI_TEST_KEY=from-dotenv\n", encoding="utf-8")
    try:
        config = load_cli_config(config_path)
    finally:
        os.environ.pop("SCI_ETL_CLI_TEST_KEY", None)
    assert config.llm.api_key.get_secret_value() == "from-dotenv"
    assert config.llm.api_key_env == "SCI_ETL_CLI_TEST_KEY"


def test_pipeline_keys_renamed_in_core_0_4_are_rejected_and_named(make_project):
    config_path = make_project()
    text = config_path.read_text(encoding="utf-8")
    config_path.write_text(
        text.replace("total_limit:", "max_records:").replace("max_concurrency:", "max_workers:"), encoding="utf-8"
    )
    with pytest.raises(ConfigurationError) as error:
        load_cli_config(config_path)
    assert "pipeline.max_records: Extra inputs are not permitted" in str(error.value)
    assert "pipeline.max_workers: Extra inputs are not permitted" in str(error.value)


def test_default_variable_is_used_without_an_llm_section(make_project):
    config = load_cli_config(make_project({"llm": None}))
    assert config.llm.api_key_env == "LLM_API_KEY"
    assert config.llm.api_key.get_secret_value() == "test-key"


def test_validation_errors_name_each_key_without_echoing_values(make_project, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "sk-live-do-not-print")
    with pytest.raises(ConfigurationError) as error:
        load_cli_config(make_project({"export": None, "pipeline": {"max_concurrency": 0}}))
    message = str(error.value)
    assert "sk-live-do-not-print" not in message
    assert "pipeline.max_concurrency: Input should be greater than or equal to 1" in message
    assert "export: Field required" in message
    assert message.startswith("Invalid configuration in ")


@pytest.mark.parametrize(
    ("updates", "message"),
    [
        ({"exports": {"destination": "planets.csv"}}, "exports"),
        ({"pipeline": {"max_worker": 2}}, "max_worker"),
        ({"pipeline": {"max_concurrency": 0}}, "max_concurrency"),
        ({"export": {"key_column": "mass_jupiter"}}, "must not also be a value column"),
        ({"export": {"value_columns": ["mass_jupiter", "mass_jupiter"]}}, "must not repeat"),
        ({"export": {"numeric_clip": {"density": [0, 1]}}}, "not value columns: density"),
        ({"export": {"numeric_clip": {"mass_jupiter": [80, 0]}}}, "lower bound above"),
        ({"export": None}, "export"),
        ({"state": {"backend": "postgres"}}, "backend"),
        ({"logging": {"level": "LOUD"}}, "level"),
        ({"llm": {"input_cost_per_million": 0.15}}, "or neither"),
        ({"export": {"normalizer": "rules.py"}}, "export.normalizer"),
        ({"export": {"validators": ["no reference"]}}, "export.validators"),
    ],
)
def test_invalid_configs_are_configuration_errors(make_project, updates, message):
    with pytest.raises(ConfigurationError, match=message):
        load_cli_config(make_project(updates))
