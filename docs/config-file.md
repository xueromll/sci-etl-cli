# Config file

A config holds the library's sections (`llm`, `http`, `full_text`, `pipeline`)
and the CLI's own (`prompts`, `export`, `state`, `logging`). Every key of the
library's sections is passed on to the run. Unknown keys are rejected,
so a typo fails validation instead of being ignored. Relative paths resolve from
the config file's folder, so a project behaves the same whichever directory it
is run from.

```yaml title="config.yaml"
llm:
  base_url: https://api.openai.com/v1
  model: gpt-4o-mini
  timeout: 120
  api_key_env: LLM_API_KEY
  cache: state/llm_cache.db

http:
  user_agent: "sci-etl-project/0.1 (mailto:you@example.org)"
  max_retries: 4
  backoff_factor: 5.0
  timeout: 25

full_text:
  max_concurrency: 2

pipeline:
  search_query: 'cat:astro-ph.EP AND abs:"hot Jupiter"'
  total_limit: 20
  page_size: 100
  search_delay: 3.0
  sleep_between: 5.0
  max_concurrency: 4
  newest_first: false
  max_attempts: 3

prompts:
  relevance: prompts/relevance.txt
  extraction: prompts/extraction.txt
  result_key: planets

export:
  destination: out/planets.csv
  key_column: planet_name
  value_columns: [orbital_period_days, mass_jupiter, radius_jupiter]

state:
  backend: file
  processed_ids: state/processed_ids.txt
  metadata: state/metadata.json

logging:
  file: logs/run.log
  level: INFO
```

## Keys

| Key | Default | Meaning |
|-----|---------|---------|
| `llm.base_url`, `llm.model` | `https://api.openai.com/v1`, `gpt-4o-mini` | Any OpenAI-compatible chat endpoint that supports JSON mode. |
| `llm.timeout` | `120` | Seconds allowed for each LLM request. |
| `llm.structured_output` | `false` | Ask the endpoint to enforce a JSON schema. Leave it off for endpoints without JSON-schema support, such as DeepSeek's. |
| `llm.api_key_env` | `LLM_API_KEY` | Environment variable holding the API key; `.env` beside the config is loaded first. |
| `llm.input_cost_per_million`, `llm.output_cost_per_million` | none | Prices per million prompt and completion tokens. Set both, or neither, to add an estimated cost to the usage summary. |
| `llm.cache` | `state/llm_cache.db` | SQLite file that keeps LLM answers, so a repeated question costs no tokens. `null` turns the cache off. |
| `http.user_agent` | `sci-etl-core/<version>` | Sent to arXiv. Include a contact address. |
| `http.timeout` | `25` | Seconds allowed for each arXiv request. |
| `http.max_retries`, `http.backoff_factor` | `3`, `2.0` | Attempts per arXiv request, waiting `backoff_factor ** attempt` seconds between them, or as long as arXiv's `Retry-After` header asks when that is longer (up to 60 seconds). |
| `full_text.max_concurrency` | `4` | arXiv requests in flight at once, listing and full text together. |
| `full_text.max_rate`, `full_text.time_period` | none, `1.0` | With `max_rate` set, at most `max_rate` arXiv requests start per `time_period` seconds, instead of the concurrency cap. |
| `pipeline.search_query` | required | An [arXiv API query](https://info.arxiv.org/help/api/user-manual.html#query_details). |
| `pipeline.total_limit` | `100` | Relevant records to process per run. `run --limit` overrides it. Named `max_records` before sci-etl-core 0.4; the old name fails validation. |
| `pipeline.page_size` | `100` | Listing entries per request. |
| `pipeline.search_delay` | `3.0` | Seconds to wait before each listing request, as arXiv asks. |
| `pipeline.sleep_between` | `5.0` | Seconds to wait between listing pages. |
| `pipeline.max_concurrency` | `6` | Records processed at once. `run --workers` overrides it. Named `max_workers` before sci-etl-core 0.4; the old name fails validation. |
| `pipeline.newest_first` | `false` | Look for new submissions at the head of the listing before continuing from the saved offset. See [Commands](commands.md#running-pipelines). |
| `pipeline.max_attempts` | `3` | Runs a paper may fail in before it is skipped; `null` never skips one. |
| `prompts.relevance` | `prompts/relevance.txt` | System prompt that must ask for `{"relevant": true}` or `{"relevant": false}` in JSON. |
| `prompts.extraction` | `prompts/extraction.txt` | System prompt that must ask for a JSON object with a list under `result_key`. |
| `prompts.result_key` | `items` | Key holding the entity list in the extraction reply. |
| `export.destination` | `out/results.csv` | CSV the entities are written to when a run ends. During a run, finished pages go to `<destination>.journal`, which the next run applies if a run crashed. |
| `export.key_column` | `name` | Field that names an entity; it gets the first column after `record_id`. |
| `export.value_columns` | required | Fields that get their own columns, in order. Any other field the model returns is kept as JSON in the `extra` column. |
| `export.escape_formulas` | `true` | Prefix cells that a spreadsheet would run as formulas with an apostrophe. Plain numbers such as `-5.361` are left unchanged. |
| `export.validators` | none | `module:attribute` references to `RecordValidator`s; an entity any of them rejects is dropped and logged with every reason. See [Plug-ins](plugins.md). |

The CSV has one row per extracted entity. Its columns are `record_id`, the
arXiv id of the paper, then `key_column`, the value columns, and `extra`.
Values are written as the model returned them, and nothing is merged: two
papers that report the same object give two rows, so a disagreement between
papers stays visible. Running a paper again replaces its rows. `record_id` and
`extra` cannot be used as column names.
| `state.backend` | `file` | `file` uses `processed_ids` and `metadata`; `sqlite` uses `database`. |
| `logging.file`, `logging.level` | `logs/run.log`, `INFO` | Log file for `run` (`null` for none) and the level: `DEBUG`, `INFO`, `WARNING`, or `ERROR`. |
