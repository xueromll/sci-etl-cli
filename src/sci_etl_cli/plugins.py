from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

from sci_etl_core.exceptions import ConfigurationError


def load_plugin(reference: str, search_path: Path) -> object:
    """Build the object a ``module:attribute`` reference names.

    A module or package whose top-level name matches a file or folder in
    ``search_path``, normally the config file's folder, is loaded from that
    file, so a project's own rules work without being installed. The folder is
    never added to ``sys.path``, so a file in it cannot shadow a module that
    other code imports. Any other name is imported as an installed module. The
    attribute may be a class or a factory function; it is called with no
    arguments and the result returned.

    Raises:
        ConfigurationError: The module cannot be imported, its top-level name
            beside the config is also a standard-library module, the attribute
            does not exist or cannot be called, or calling it fails.
    """
    module_name, _, attribute_path = reference.partition(":")
    try:
        target: Any = _import(module_name, search_path)
    except ConfigurationError:
        raise
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


def _import(module_name: str, folder: Path) -> ModuleType:
    top = module_name.partition(".")[0]
    local = _local_source(folder, top)
    if local is None:
        return importlib.import_module(module_name)
    if top in sys.stdlib_module_names:
        raise ConfigurationError(
            f"Plug-in module {top!r} beside the config has the name of a standard-library module; rename it"
        )
    if top not in sys.modules:
        _load_from_file(top, local)
    return importlib.import_module(module_name)


def _local_source(folder: Path, name: str) -> Path | None:
    for candidate in (folder / name / "__init__.py", folder / f"{name}.py"):
        if candidate.is_file():
            return candidate
    return None


def _load_from_file(name: str, source: Path) -> None:
    package_folders = [str(source.parent)] if source.name == "__init__.py" else None
    spec = importlib.util.spec_from_file_location(name, source, submodule_search_locations=package_folders)
    if spec is None or spec.loader is None:  # pragma: no cover
        raise ImportError(f"cannot load {source}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        del sys.modules[name]
        raise
