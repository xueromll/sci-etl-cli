# Changelog

All notable changes to sci-etl-cli are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/). Until 1.0, a minor release may
change behavior; each such change is listed under **Changed**.

## [Unreleased]

### Changed

- Accepts sci-etl-core 0.3 as well as 0.2.

## [0.2.0] - Unreleased

### Added

- Plug-ins for domain rules. `export.normalizer` names a `KeyNormalizer` and
  `export.validators` names `RecordValidator`s, each as `module:attribute`
  pointing at a class or a factory function. Modules beside the config file are
  importable without installing them. Entities a validator rejects are dropped
  and logged.
- `validate` imports and builds every configured plug-in, and `run` does so
  before any network request, so a broken plug-in exits with code 3.
- `run` logs LLM requests and tokens when it finishes, aborts, or is
  interrupted, with an estimated cost when `llm.input_cost_per_million` and
  `llm.output_cost_per_million` are set.
- ruff and mypy run in CI, and a `lint` extra installs them locally.

### Changed

- Requires sci-etl-core 0.2, which waits as long as arXiv's or the LLM
  provider's `Retry-After` header asks when throttled, and counts token usage.
- Configuration errors are formatted by sci-etl-core's `validate_config`.

## [0.1.0] - 2026-09-14

First release: the `init`, `validate`, `search`, `run`, `status`, and `parse`
commands.

[Unreleased]: https://github.com/xueromll/sci-etl-cli/compare/v0.2.1...HEAD
[0.2.0]: https://github.com/xueromll/sci-etl-cli/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/xueromll/sci-etl-cli/releases/tag/v0.1.0
