from __future__ import annotations

import sys

import pytest
from sci_etl_core.exceptions import ConfigurationError

from sci_etl_cli.plugins import load_plugin


def test_classes_and_factories_are_built_from_the_project_folder(tmp_path, write_plugins):
    module = write_plugins(tmp_path, "rules_built")
    named = load_plugin(f"{module}:NamedPlanets", tmp_path)
    assert named.is_valid({"planet_name": "WASP-12 b"})
    assert not named.is_valid({"planet_name": " "})
    validator = load_plugin(f"{module}:short_period_planets", tmp_path)
    assert validator.is_valid({"orbital_period_days": 1.09})
    assert not validator.is_valid({"orbital_period_days": 40.0})
    assert str(tmp_path) not in sys.path


@pytest.mark.parametrize(
    ("attribute", "message"),
    [
        ("Missing", "has no attribute 'Missing'"),
        ("NOT_CALLABLE", "is not a class or factory function"),
        ("broken_factory", "could not be created: RuntimeError"),
    ],
)
def test_bad_attributes_are_configuration_errors(tmp_path, write_plugins, attribute, message):
    module = write_plugins(tmp_path, "rules_bad")
    with pytest.raises(ConfigurationError, match=message):
        load_plugin(f"{module}:{attribute}", tmp_path)
    assert str(tmp_path) not in sys.path


def test_unimportable_module_is_a_configuration_error(tmp_path):
    with pytest.raises(ConfigurationError, match="could not be imported"):
        load_plugin("no_such_rules_module:Anything", tmp_path)


def test_a_local_module_cannot_shadow_what_the_plugin_imports(tmp_path, write_plugins):
    (tmp_path / "decimal.py").write_text("raise RuntimeError('local decimal was imported')\n", encoding="utf-8")
    module = write_plugins(tmp_path, "rules_shadowed")
    (tmp_path / f"{module}.py").write_text(
        "import decimal\n\n\ndef exact():\n    return decimal.Decimal('1.5')\n", encoding="utf-8"
    )
    assert str(load_plugin(f"{module}:exact", tmp_path)) == "1.5"
    assert str(tmp_path) not in sys.path


def test_a_plugin_named_like_a_standard_library_module_is_rejected(tmp_path):
    (tmp_path / "csv.py").write_text("def build():\n    return 1\n", encoding="utf-8")
    with pytest.raises(ConfigurationError, match="'csv' beside the config has the name of a standard-library module"):
        load_plugin("csv:build", tmp_path)


def test_a_local_package_and_its_submodules_are_loaded_from_their_files(tmp_path):
    package = tmp_path / "local_rules_pkg"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    checks = "from . import limits\n\n\ndef build():\n    return limits.LIMIT\n"
    (package / "checks.py").write_text(checks, encoding="utf-8")
    (package / "limits.py").write_text("LIMIT = 10\n", encoding="utf-8")
    try:
        assert load_plugin("local_rules_pkg.checks:build", tmp_path) == 10
        assert load_plugin("local_rules_pkg.checks:build", tmp_path) == 10
    finally:
        for name in ("local_rules_pkg", "local_rules_pkg.checks", "local_rules_pkg.limits"):
            sys.modules.pop(name, None)


def test_a_local_module_that_fails_to_load_leaves_no_half_imported_module(tmp_path):
    (tmp_path / "broken_local_rules.py").write_text("raise ValueError('syntax of the rules')\n", encoding="utf-8")
    with pytest.raises(ConfigurationError, match="could not be imported: syntax of the rules"):
        load_plugin("broken_local_rules:anything", tmp_path)
    assert "broken_local_rules" not in sys.modules


def test_an_installed_module_is_imported_when_no_local_file_matches(tmp_path):
    assert load_plugin("collections:OrderedDict", tmp_path) == {}
