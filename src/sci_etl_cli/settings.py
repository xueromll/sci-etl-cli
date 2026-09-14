from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from sci_etl_core.config import (
    BaseAppConfig,
    HttpConfig,
    LLMConfig,
    PipelineConfig,
    RateLimitConfig,
    apply_api_key,
    load_yaml,
)
from sci_etl_core.exceptions import ConfigurationError

DEFAULT_API_KEY_ENV = "LLM_API_KEY"
_STRICT = ConfigDict(extra="forbid")


class CliLLMConfig(LLMConfig):
    model_config = _STRICT

    api_key_env: str = Field(default=DEFAULT_API_KEY_ENV, min_length=1)


class CliHttpConfig(HttpConfig):
    model_config = _STRICT


class CliRateLimitConfig(RateLimitConfig):
    model_config = _STRICT


class CliPipelineConfig(PipelineConfig):
    model_config = _STRICT


class PromptsConfig(BaseModel):
    model_config = _STRICT

    relevance: Path = Path("prompts/relevance.txt")
    extraction: Path = Path("prompts/extraction.txt")
    result_key: str = Field(default="items", min_length=1)


class ExportConfig(BaseModel):
    model_config = _STRICT

    destination: Path = Path("out/results.csv")
    key_column: str = Field(default="name", min_length=1)
    value_columns: list[str] = Field(min_length=1)
    numeric_clip: dict[str, tuple[float, float]] = Field(default_factory=dict)
    escape_formulas: bool = True

    @model_validator(mode="after")
    def _check_columns(self) -> "ExportConfig":
        if self.key_column in self.value_columns:
            raise ValueError(f"key_column {self.key_column!r} must not also be a value column")
        if len(set(self.value_columns)) != len(self.value_columns):
            raise ValueError("value_columns must not repeat a column")
        unknown = sorted(set(self.numeric_clip) - set(self.value_columns))
        if unknown:
            raise ValueError(f"numeric_clip names columns that are not value columns: {', '.join(unknown)}")
        for column, (low, high) in self.numeric_clip.items():
            if low > high:
                raise ValueError(f"numeric_clip for {column!r} has a lower bound above its upper bound")
        return self


class StateConfig(BaseModel):
    model_config = _STRICT

    backend: Literal["file", "sqlite"] = "file"
    processed_ids: Path = Path("state/processed_ids.txt")
    metadata: Path = Path("state/metadata.json")
    database: Path = Path("state/state.db")


class LoggingConfig(BaseModel):
    model_config = _STRICT

    file: Path | None = Path("logs/run.log")
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"


class CliConfig(BaseAppConfig):
    """The library's config sections plus the CLI's own, with unknown keys rejected."""

    model_config = _STRICT

    llm: CliLLMConfig = Field(default_factory=CliLLMConfig)
    http: CliHttpConfig = Field(default_factory=CliHttpConfig)
    full_text: CliRateLimitConfig = Field(default_factory=CliRateLimitConfig)
    pipeline: CliPipelineConfig = Field(default_factory=CliPipelineConfig)
    prompts: PromptsConfig = Field(default_factory=PromptsConfig)
    export: ExportConfig
    state: StateConfig = Field(default_factory=StateConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)


def load_cli_config(config_path: Path) -> CliConfig:
    """Load a CLI config file.

    The ``.env`` file beside the config is loaded, the API key is read from the
    variable named by ``llm.api_key_env``, and relative paths are resolved from
    the config file's folder, so a project behaves the same from any working
    directory.

    Raises:
        ConfigurationError: The file is missing, is not valid YAML, or fails
            validation, including unknown keys. Validation messages name each
            failing key without echoing the values read, so an API key taken
            from the environment can never appear in the output.
    """
    resolved = Path(config_path).resolve()
    raw = load_yaml(resolved)
    load_dotenv(resolved.parent / ".env")
    apply_api_key(raw, _api_key_env(raw))
    try:
        config = CliConfig.model_validate(raw)
    except ValidationError as exc:
        raise ConfigurationError(describe_validation_error(resolved, exc)) from None
    return anchor_paths(config, resolved.parent)


def describe_validation_error(path: Path, error: ValidationError) -> str:
    problems = [
        f"  {'.'.join(str(part) for part in detail['loc']) or 'config'}: {detail['msg']}"
        for detail in error.errors(include_url=False, include_input=False)
    ]
    return "\n".join([f"Invalid configuration in {path}:", *problems])


def anchor_paths(config: CliConfig, root: Path) -> CliConfig:
    def anchored(path: Path) -> Path:
        expanded = path.expanduser()
        return expanded if expanded.is_absolute() else root / expanded

    prompts = config.prompts.model_copy(
        update={"relevance": anchored(config.prompts.relevance), "extraction": anchored(config.prompts.extraction)}
    )
    export = config.export.model_copy(update={"destination": anchored(config.export.destination)})
    state = config.state.model_copy(
        update={
            "processed_ids": anchored(config.state.processed_ids),
            "metadata": anchored(config.state.metadata),
            "database": anchored(config.state.database),
        }
    )
    log_file = config.logging.file
    logging_config = config.logging.model_copy(update={"file": None if log_file is None else anchored(log_file)})
    return config.model_copy(
        update={"prompts": prompts, "export": export, "state": state, "logging": logging_config}
    )


def _api_key_env(raw: dict[str, Any]) -> str:
    llm = raw.get("llm")
    if isinstance(llm, dict) and isinstance(llm.get("api_key_env"), str) and llm["api_key_env"]:
        return llm["api_key_env"]
    return DEFAULT_API_KEY_ENV
