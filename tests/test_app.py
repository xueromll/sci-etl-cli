from __future__ import annotations

import runpy
import sys
from importlib.metadata import version

import pytest

from sci_etl_cli.commands import parse


def test_version_names_the_cli_and_the_library(run_cli):
    result = run_cli("--version")
    assert result.exit_code == 0
    assert result.stdout.strip() == f"sci-etl {version('sci-etl-cli')} (sci-etl-core {version('sci-etl-core')})"


def test_help_lists_every_command_and_the_exit_codes(run_cli):
    result = run_cli("--help")
    assert result.exit_code == 0
    for command in ("init", "validate", "search", "run", "status", "parse"):
        assert command in result.stdout
    assert "130  interrupted after saving state" in result.stdout


def test_module_entry_point_runs_the_cli(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["sci-etl", "--version"])
    with pytest.raises(SystemExit) as exit_info:
        runpy.run_module("sci_etl_cli", run_name="__main__")
    assert exit_info.value.code == 0
    assert capsys.readouterr().out.startswith("sci-etl ")


def test_missing_config_file_is_a_configuration_error(run_cli, tmp_path):
    result = run_cli("status", str(tmp_path / "missing.yaml"))
    assert result.exit_code == 3
    assert "Config file not found" in result.stderr


def test_missing_package_exits_four_with_an_install_hint(run_cli, tmp_path, monkeypatch):
    page = tmp_path / "page.html"
    page.write_text("<p>WASP-12 b</p>", encoding="utf-8")

    def unavailable(_file_format):
        raise ModuleNotFoundError("No module named 'pdfplumber'", name="pdfplumber")

    monkeypatch.setattr(parse, "build_parser", unavailable)
    result = run_cli("parse", str(page))
    assert result.exit_code == 4
    assert 'pip install "sci-etl-core[pdf]"' in result.stderr
