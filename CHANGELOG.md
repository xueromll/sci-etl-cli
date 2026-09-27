# Changelog

All notable changes to sci-etl-cli are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/). Until 1.0, a minor release may
change behavior; each such change is listed under **Changed**.

## [Unreleased]

### Added

- `llm.structured_output` asks the endpoint to enforce a JSON schema.

### Changed

- **Breaking:** the export CSV has one row per extracted entity, with the
  arXiv id of its paper in a new first column, `record_id`, and any field
  outside `key_column` and `value_columns` kept as JSON in a new last column,
  `extra`. Values are written as the model returned them. Rows are no longer
  merged by name, so two papers that report the same object give two rows,
  and a later paper no longer fills a gap in an earlier paper's row. Start a
  new CSV file: `run` refuses a file with the old header.
- **Breaking:** `export.numeric_clip` and `export.normalizer` are removed and
  fail validation. Out-of-range values are no longer clamped; reject them with
  a validator plug-in instead.
- The CSV file is written when a run ends. During a run, finished pages go to
  `<destination>.journal`, which the next run applies if a run crashed.
- A rejected entity is logged with every reason its validators give, such as
  `Entity rejected by validation: 'KELT-9 b' (orbital_period_days is 40,
  outside [0, 10])`.
- sci-etl-core's own log lines, such as record failures and retries, go to the
  console and the log file at `logging.level`.
- Plug-in modules beside the config are loaded from their files instead of
  putting the config's folder first on the import path, so a file there can no
  longer replace a module that other code imports. A plug-in module named like
  a standard-library module is rejected with an error naming it.
- Requires sci-etl-core 0.6.

## [0.3.0] - 2026-09-26

### Added

- `pipeline.newest_first`, `pipeline.max_attempts`, and the `full_text`
  section take effect. `newest_first` was accepted but ignored; `run` now
  looks for new submissions at the head of the listing first. `max_attempts`
  sets how many failed runs quarantine a paper, and `full_text` limits arXiv
  requests in flight.
- `llm.cache` keeps LLM answers in a SQLite file, `state/llm_cache.db` by
  default, so repeated questions cost no tokens. Set it to `null` to turn the
  cache off.

### Changed

- Ctrl+C lets the papers in flight finish and saves them, then exits with 130
  and logs how many papers the run processed. It cancelled them, and the next
  run paid for their LLM calls again.
- `--rescan` and `--start-index` fail as a usage error when
  `pipeline.newest_first` is set.
- `init` writes a `full_text` section that allows two arXiv requests at once.
- Requires sci-etl-core 0.5.1 and Python 3.11. The config keys
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

[Unreleased]: https://github.com/xueromll/sci-etl-cli/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/xueromll/sci-etl-cli/compare/v0.2.1...v0.3.0
[0.2.1]: https://github.com/xueromll/sci-etl-cli/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/xueromll/sci-etl-cli/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/xueromll/sci-etl-cli/releases/tag/v0.1.0
