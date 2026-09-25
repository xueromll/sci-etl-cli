# Changelog

All notable changes to sci-etl-cli are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/). Until 1.0, a minor release may
change behavior; each such change is listed under **Changed**.

## [Unreleased]

### Changed

- Requires sci-etl-core 0.5 and Python 3.11. The config keys
  `pipeline.max_records` and `pipeline.max_workers` are renamed
  `pipeline.total_limit` and `pipeline.max_concurrency`, and `init` writes the
  new names. A config that still uses an old name, or any key the
  sci-etl-core sections do not declare, now fails validation and the error
  names the key.
- `run` skips a paper that failed in three runs, on pages where other papers
  were processed, as sci-etl-core 0.5 quarantines it; the next runs log it
  once each.
- The per-page log line reads `Listing page at offset N: M entries` and no
  longer counts the entries to process; the run's progress lines report them.

## [0.2.1] - 2026-09-14

### Changed

- Republishes 0.2.0 unchanged under a new version number, because PyPI does
  not accept a second upload of a published version.

## [0.2.0] - 2026-09-14

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
[0.2.1]: https://github.com/xueromll/sci-etl-cli/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/xueromll/sci-etl-cli/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/xueromll/sci-etl-cli/releases/tag/v0.1.0
