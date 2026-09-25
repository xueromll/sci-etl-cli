# Config file

A config holds the library's sections (`llm`, `http`, `pipeline`) and the
CLI's own (`prompts`, `export`, `state`, `logging`). Unknown keys are rejected,
so a typo fails validation instead of being ignored. Relative paths resolve from
the config file's folder, so a project behaves the same whichever directory it
is run from.

```yaml title="config.yaml"
llm:
  base_url: https://api.openai.com/v1
  model: gpt-4o-mini
  timeout: 120
  api_key_env: LLM_API_KEY

http:
  user_agent: "sci-etl-project/0.1 (mailto:you@example.org)"
  max_retries: 4
  backoff_factor: 5.0
  timeout: 25

pipeline:
  search_query: 'cat:astro-ph.EP AND abs:"hot Jupiter"'
  total_limit: 20
  page_size: 100
  search_delay: 3.0
  sleep_between: 5.0
  max_concurrency: 4

prompts:
  relevance: prompts/relevance.txt
  extraction: prompts/extraction.txt
  result_key: planets

export:
  destination: out/planets.csv
  key_column: planet_name
  value_columns: [orbital_period_days, mass_jupiter, radius_jupiter]
  numeric_clip:
    mass_jupiter: [0.0, 80.0]

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
| `llm.api_key_env` | `LLM_API_KEY` | Environment variable holding the API key; `.env` beside the config is loaded first. |
| `llm.input_cost_per_million`, `llm.output_cost_per_million` | none | Prices per million prompt and completion tokens. Set both, or neither, to add an estimated cost to the usage summary. |
| `http.user_agent` | `sci-etl-core/0.1` | Sent to arXiv. Include a contact address. |
| `http.max_retries`, `http.backoff_factor` | `3`, `2.0` | Attempts per arXiv request, waiting `backoff_factor ** attempt` seconds between them, or as long as arXiv's `Retry-After` header asks when that is longer (up to 60 seconds). |
| `pipeline.search_query` | required | An [arXiv API query](https://info.arxiv.org/help/api/user-manual.html#query_details). |
| `pipeline.total_limit` | `100` | Relevant records to process per run. `run --limit` overrides it. Named `max_records` before sci-etl-core 0.4. |
| `pipeline.page_size` | `100` | Listing entries per request. |
| `pipeline.search_delay` | `3.0` | Seconds to wait before each listing request, as arXiv asks. |
| `pipeline.sleep_between` | `5.0` | Seconds to wait between listing pages. |
| `pipeline.max_concurrency` | `6` | Records processed at once. `run --workers` overrides it. Named `max_workers` before sci-etl-core 0.4. |
| `prompts.relevance` | `prompts/relevance.txt` | System prompt that must ask for `{"relevant": true}` or `{"relevant": false}` in JSON. |
| `prompts.extraction` | `prompts/extraction.txt` | System prompt that must ask for a JSON object with a list under `result_key`. |
| `prompts.result_key` | `items` | Key holding the entity list in the extraction reply. |
| `export.destination` | `out/results.csv` | CSV the entities are upserted into. |
| `export.key_column` | `name` | Field that identifies an entity; one row is kept per normalized key. |
| `export.value_columns` | required | Numeric fields to keep. Later papers only fill empty cells. |
| `export.numeric_clip` | none | `[low, high]` bounds per value column. |
| `export.escape_formulas` | `true` | Prefix keys that a spreadsheet would run as formulas with an apostrophe. |
| `export.normalizer` | library default | `module:attribute` of a `KeyNormalizer` that decides which rows are the same entity. See [Plug-ins](plugins.md). |
| `export.validators` | none | `module:attribute` references to `RecordValidator`s; an entity any of them rejects is dropped and logged. |
| `state.backend` | `file` | `file` uses `processed_ids` and `metadata`; `sqlite` uses `database`. |
| `logging.file`, `logging.level` | `logs/run.log`, `INFO` | Log file for `run` (`null` for none) and the level: `DEBUG`, `INFO`, `WARNING`, or `ERROR`. |
