# Config file

A config holds the library's sections (`llm`, `http`, `full_text`, `pipeline`)
and the CLI's own (`source`, `prompts`, `export`, `state`, `logging`). Every
key of the library's sections is passed on to the run. Unknown keys are
rejected, so a typo fails validation instead of being ignored. Relative paths
resolve from the config file's folder, so a project behaves the same whichever
directory it is run from.

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

source:
  kind: arxiv

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
| `http.user_agent` | `sci-etl-core/<version>` | Sent to the source. Include a contact address. |
| `http.timeout` | `25` | Seconds allowed for each request to the source. |
| `http.max_retries`, `http.backoff_factor` | `3`, `2.0` | Attempts per request to the source, waiting `backoff_factor ** attempt` seconds between them, or as long as its `Retry-After` header asks when that is longer (up to 60 seconds). |
| `full_text.max_concurrency` | `4` | Requests to the source in flight at once, listing and full text together. |
| `full_text.max_rate`, `full_text.time_period` | none, `1.0` | With `max_rate` set, at most `max_rate` requests to the source start per `time_period` seconds, instead of the concurrency cap. PubMed, Semantic Scholar and OpenAlex publish rate limits; the starters set it. |
| `pipeline.search_query` | required | The query in the source's own syntax; see [Sources](#sources). |
| `pipeline.total_limit` | `100` | Relevant records to process per run. `run --limit` overrides it. Named `max_records` before sci-etl-core 0.4; the old name fails validation. |
| `pipeline.page_size` | `100` | Listing entries per request. |
| `pipeline.search_delay` | `3.0` | Seconds to wait before each listing request, as arXiv asks; the other sources ignore it and rely on `full_text`. |
| `pipeline.sleep_between` | `5.0` | Seconds to wait between listing pages. |
| `pipeline.max_concurrency` | `6` | Records processed at once. `run --workers` overrides it. Named `max_workers` before sci-etl-core 0.4; the old name fails validation. |
| `pipeline.newest_first` | `false` | Look for new submissions at the head of the listing before continuing from the saved offset. Needs a source that pages by offset, so `openalex` rejects it. See [Commands](commands.md#running-pipelines). |
| `pipeline.max_attempts` | `3` | Runs a paper may fail in before it is skipped; `null` never skips one. |
| `source.kind` | `arxiv` | `arxiv`, `pubmed`, `semantic_scholar`, or `openalex`. The other `source` keys depend on it; see [Sources](#sources). |
| `source.api_key_env` | `SOURCE_API_KEY` | Environment variable holding the source's API key, for the sources that accept one; `.env` beside the config is loaded first. |
| `prompts.relevance` | `prompts/relevance.txt` | System prompt that must ask for `{"relevant": true}` or `{"relevant": false}` in JSON. |
| `prompts.extraction` | `prompts/extraction.txt` | System prompt that must ask for a JSON object with a list under `result_key`. |
| `prompts.result_key` | `items` | Key holding the entity list in the extraction reply. |
| `export.destination` | `out/results.csv` | CSV the entities are written to when a run ends. During a run, finished pages go to `<destination>.journal`, which the next run applies if a run crashed. |
| `export.key_column` | `name` | Field that names an entity; it gets the first column after `record_id`, the paper's id in the source. |
| `export.value_columns` | required | Fields that get their own columns, in order. Any other field the model returns is kept as JSON in the `extra` column. |
| `export.escape_formulas` | `true` | Prefix cells that a spreadsheet would run as formulas with an apostrophe. Plain numbers such as `-5.361` are left unchanged. |
| `export.validators` | none | `module:attribute` references to `RecordValidator`s; an entity any of them rejects is dropped and logged with every reason. See [Plug-ins](plugins.md). |
| `state.backend` | `file` | `file` uses `processed_ids` and `metadata`; `sqlite` uses `database`. |
| `logging.file`, `logging.level` | `logs/run.log`, `INFO` | Log file for `run` (`null` for none) and the level: `DEBUG`, `INFO`, `WARNING`, or `ERROR`. |

The CSV has one row per extracted entity. Its columns are `record_id`, the
paper's id in the source, then `key_column`, the value columns, and `extra`.
Values are written as the model returned them, and nothing is merged: two
papers that report the same object give two rows, so a disagreement between
papers stays visible. Running a paper again replaces its rows. `record_id` and
`extra` cannot be used as column names.

## Sources

`source.kind` picks the literature source; without a `source` section a
project searches arXiv, as before. Each kind accepts only its own keys, so a
key of another source fails validation and the error names the source, such as
`source.pubmed.year`. `pipeline.search_query` is written in the source's
syntax. Every source takes its retries from `http` and its rate limiter from
`full_text`, and falls back to the abstract when it has no full text for a
paper. `sci-etl init --source <kind>` writes a starter for each.

A source's API key is never written in the config: it is read from the
variable `source.api_key_env` names, `SOURCE_API_KEY` by default, from the
environment or the `.env` file beside the config, the same way `llm.api_key_env`
works. No source requires a key; one raises PubMed's and Semantic Scholar's
rate limits and is accepted by OpenAlex.

### arXiv

```yaml
source:
  kind: arxiv
```

Pages by offset, so `newest_first`, `--rescan`, and `--start-index` all work.
The query is an [arXiv API query](https://info.arxiv.org/help/api/user-manual.html#query_details),
such as `cat:astro-ph.EP AND abs:"hot Jupiter"`. Full text comes from the
LaTeX e-print, then the PDF. `record_id` is the arXiv id. Needs the
`arxiv` and `pdf` extras of sci-etl-core. No other key.

### PubMed

```yaml
source:
  kind: pubmed
  api_key_env: SOURCE_API_KEY
  tool: sci-etl-project
  email: you@example.org
  sort: pub_date
```

Pages by offset through NCBI's E-utilities, which serve the first 9,999
results of a search. The query uses PubMed's search syntax, such as
`metformin[Title/Abstract] AND "Diabetes Mellitus, Type 2"[MeSH Terms]`. Full
text comes from PubMed Central as JATS XML for papers that have a PMC id.
`record_id` is the PMID. Needs the `xml` extra.

| Key | Default | Meaning |
|-----|---------|---------|
| `source.tool`, `source.email` | none | Identify your project to NCBI, as its usage policy asks. |
| `source.sort` | `pub_date` | E-utilities sort order; `null` for relevance. |

NCBI allows 3 requests per second without a key and 10 with one; set
`full_text.max_rate` accordingly.

### Semantic Scholar

```yaml
source:
  kind: semantic_scholar
  api_key_env: SOURCE_API_KEY
  year: "2015-"
  fields_of_study: Medicine
```

Pages by offset through the relevance search, which serves the first 1,000
results, 100 per page. The query is plain keywords. Full text comes from the
open-access PDF when there is one. `record_id` is the Semantic Scholar paper
id. Needs the `pdf` extra.

| Key | Default | Meaning |
|-----|---------|---------|
| `source.year` | none | Semantic Scholar's `year` filter, such as `2020-` or `2018-2022`. |
| `source.fields_of_study` | none | Semantic Scholar's `fieldsOfStudy` filter, such as `Physics` or `Medicine,Biology`. |

Without a key, requests share the public rate limit; the starter allows one
request per second.

### OpenAlex

```yaml
source:
  kind: openalex
  api_key_env: SOURCE_API_KEY
  filter: type:article,from_publication_date:2015-01-01
  sort: publication_date:desc
  mailto: you@example.org
```

Pages by OpenAlex's opaque cursors, not by offset, so `pipeline.newest_first`
and `--start-index` above 0 are refused; `--rescan` starts again from the
first page. A finished listing starts again from its first page on the next
run, skipping processed works by id. The query is OpenAlex's full-text
`search`. Full text comes from the PDF of the best open-access location when
there is one. `record_id` is the OpenAlex work id, such as `W2741809807`.
Needs the `pdf` extra.

| Key | Default | Meaning |
|-----|---------|---------|
| `source.filter` | none | An [OpenAlex filter](https://docs.openalex.org/api-entities/works/filter-works), such as `type:article,from_publication_date:2020-01-01`. |
| `source.sort` | `publication_date:desc` | OpenAlex sort order; `null` for relevance. |
| `source.mailto` | none | Joins OpenAlex's polite pool, which allows 10 requests per second. |
