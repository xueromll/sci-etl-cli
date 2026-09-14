from __future__ import annotations

import sys

import pytest
from sci_etl_core.exceptions import ConfigurationError

from sci_etl_cli.plugins import load_plugin


def test_classes_and_factories_are_built_from_the_project_folder(tmp_path, write_plugins):
    module = write_plugins(tmp_path, "rules_built")
    normalizer = load_plugin(f"{module}:DesignationNormalizer", tmp_path)
    assert normalizer.normalize("SuperWASP-12 b") == "wasp12b"
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
