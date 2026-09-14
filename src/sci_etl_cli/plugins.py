from __future__ import annotations

import importlib
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from sci_etl_core.exceptions import ConfigurationError


def load_plugin(reference: str, search_path: Path) -> object:
    """Build the object a ``module:attribute`` reference names.

    The module is imported with ``search_path``, normally the config file's
    folder, at the front of ``sys.path``, so a project's own package can be
    referenced without installing it. The attribute may be a class or a
    factory function; it is called with no arguments and the result returned.

    Raises:
        ConfigurationError: The module cannot be imported, the attribute does
            not exist or cannot be called, or calling it fails.
    """
    module_name, _, attribute_path = reference.partition(":")
    with _importable_from(search_path):
        try:
            target: Any = importlib.import_module(module_name)
        except Exception as exc:
            raise ConfigurationError(f"Plug-in {reference!r} could not be imported: {exc}") from exc
        for name in attribute_path.split("."):
            if not hasattr(target, name):
                raise ConfigurationError(f"Plug-in {reference!r} not found: {module_name} has no attribute {name!r}")
            target = getattr(target, name)
        if not callable(target):
            raise ConfigurationError(f"Plug-in {reference!r} is not a class or factory function")
        try:
            return target()
        except Exception as exc:
            raise ConfigurationError(f"Plug-in {reference!r} could not be created: {exc!r}") from exc


def wrong_type(reference: str, plugin: object, expected: str) -> ConfigurationError:
    return ConfigurationError(f"Plug-in {reference!r} produced {type(plugin).__name__}, not a {expected}")


@contextmanager
def _importable_from(folder: Path) -> Iterator[None]:
    entry = str(folder)
    sys.path.insert(0, entry)
    try:
        yield
    finally:
        sys.path.remove(entry)
