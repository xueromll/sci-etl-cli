# sci-etl-cli

`sci-etl` runs [sci-etl-core](https://github.com/xueromll/sci-etl-core)
extraction pipelines from a single YAML file, with no wiring code. It searches
arXiv, asks an LLM which papers are relevant, extracts structured entities from
their full text, and upserts them into a CSV. Runs resume where the last one
stopped.

```text
$ sci-etl init hot-jupiters
$ sci-etl validate hot-jupiters/config.yaml
$ sci-etl search hot-jupiters/config.yaml --limit 5
$ sci-etl run hot-jupiters/config.yaml --limit 20
$ sci-etl status hot-jupiters/config.yaml
```

- [Installation](#installation)
- [Quick start](#quick-start)
- [Commands](#commands)
- [Config file](#config-file)
- [Exit codes](#exit-codes)
- [Development](#development)
- [License](#license)

## Installation

Python 3.10 or newer is required.

```bash
pip install sci-etl-cli
```

This installs the `sci-etl` command along with `sci-etl-core[async,llm,pdf]`
0.1.2 or newer, `click`, and `rich`. `pipx install sci-etl-cli` keeps it in an
environment of its own.

## Quick start

1. **Create a project.** `sci-etl init hot-jupiters` writes a working example
   that collects hot Jupiter measurements: `config.yaml`, a relevance prompt, an
   extraction prompt, and `.env.example`.
2. **Add your API key.** Copy `.env.example` to `.env` beside the config and set
   `LLM_API_KEY`. The key is read from the environment or that file, never
   printed, and never written to the config.
3. **Check the project.** `sci-etl validate hot-jupiters/config.yaml` checks the
   config, the prompts, the key, and the installed packages. Add `--online` to
   also send one arXiv request and one LLM request.
4. **Tune the query.** `sci-etl search hot-jupiters/config.yaml` lists a page of
   matching papers without calling the LLM.
5. **Run it.** `sci-etl run hot-jupiters/config.yaml` exports entities to
   `out/planets.csv` and records progress under `state/`. Run the same command
   again to continue; add `--rescan` to pick up papers submitted since.

To use the CLI for another subject, change `pipeline.search_query`, both
prompts, and the `export` columns. The extraction prompt has to ask for JSON
containing `result_key`, `key_column`, and every value column; `validate` checks
this.

## Commands

| Command | What it does | Network | Writes |
|---------|--------------|---------|--------|
| `sci-etl init [DIRECTORY]` | Creates a starter project. Refuses to overwrite existing files unless given `--force`. | none | project files |
| `sci-etl validate CONFIG` | Checks the config, prompts, API key, and packages. `--online` adds one arXiv and one LLM request once the offline checks pass. | only with `--online` | nothing |
| `sci-etl search CONFIG` | Shows one page of arXiv results, each marked `new` or `processed`. Options: `--query`, `--limit`, `--start-index`, `--json`. | arXiv | nothing |
| `sci-etl run CONFIG` | Runs the pipeline, resuming from saved state. Options: `--limit`, `--page-size`, `--workers`, `--rescan` or `--start-index`, `--log-file`. | arXiv and the LLM | export CSV, state, log |
| `sci-etl status CONFIG` | Shows processed records, the saved offset, the last run time, and export rows. `--json` prints JSON. | none | nothing |
| `sci-etl parse FILE` | Prints the text a bundled parser extracts from a PDF, arXiv e-print, or HTML file. Options: `--format`, `--trim-references`. | none | nothing |

Every command accepts `--help`. Logs and errors go to stderr; `search --json`,
`status --json`, and `parse` print their results to stdout, so they can be
piped.

**Stopping a run.** Press Ctrl+C once: records in flight are cancelled and left
unmarked, state is saved, and the command exits with 130. The next run retries
those records. A second Ctrl+C exits immediately.

**Resuming.** A run starts at the listing offset saved by the previous one.
arXiv lists the newest submissions first, so new papers push older ones to
higher offsets; `--rescan` starts again at offset 0 and skips processed papers
by id, which costs listing requests but no LLM calls.

## Config file

A config holds the library's sections (`llm`, `http`, `pipeline`) and the
CLI's own (`prompts`, `export`, `state`, `logging`). Unknown keys are rejected,
so a typo fails validation instead of being ignored. Relative paths resolve from
the config file's folder, so a project behaves the same whichever directory it
is run from.

```yaml
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
  max_records: 20
  page_size: 100
  search_delay: 3.0
  sleep_between: 5.0
  max_workers: 4

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

| Key | Default | Meaning |
|-----|---------|---------|
| `llm.base_url`, `llm.model` | `https://api.openai.com/v1`, `gpt-4o-mini` | Any OpenAI-compatible chat endpoint that supports JSON mode. |
| `llm.timeout` | `120` | Seconds allowed for each LLM request. |
| `llm.api_key_env` | `LLM_API_KEY` | Environment variable holding the API key; `.env` beside the config is loaded first. |
| `http.user_agent` | `sci-etl-core/0.1` | Sent to arXiv. Include a contact address. |
| `http.max_retries`, `http.backoff_factor` | `3`, `2.0` | Attempts per arXiv request, waiting `backoff_factor ** attempt` seconds between them. arXiv throttles for longer than the defaults allow, so the example uses `4` and `5.0`. |
| `pipeline.search_query` | required | An [arXiv API query](https://info.arxiv.org/help/api/user-manual.html#query_details). |
| `pipeline.max_records` | `100` | Relevant records to process per run. `run --limit` overrides it. |
| `pipeline.page_size` | `100` | Listing entries per request. |
| `pipeline.search_delay` | `3.0` | Seconds to wait before each listing request, as arXiv asks. |
| `pipeline.sleep_between` | `5.0` | Seconds to wait between listing pages. |
| `pipeline.max_workers` | `6` | Records processed at once. |
| `prompts.relevance` | `prompts/relevance.txt` | System prompt that must ask for `{"relevant": true}` or `{"relevant": false}` in JSON. |
| `prompts.extraction` | `prompts/extraction.txt` | System prompt that must ask for a JSON object with a list under `result_key`. |
| `prompts.result_key` | `items` | Key holding the entity list in the extraction reply. |
| `export.destination` | `out/results.csv` | CSV the entities are upserted into. |
| `export.key_column` | `name` | Field that identifies an entity; one row is kept per normalized key. |
| `export.value_columns` | required | Numeric fields to keep. Later papers only fill empty cells. |
| `export.numeric_clip` | none | `[low, high]` bounds per value column. |
| `export.escape_formulas` | `true` | Prefix keys that a spreadsheet would run as formulas with an apostrophe. |
| `state.backend` | `file` | `file` uses `processed_ids` and `metadata`; `sqlite` uses `database`. |
| `logging.file`, `logging.level` | `logs/run.log`, `INFO` | Log file for `run` (`null` for none) and the level: `DEBUG`, `INFO`, `WARNING`, or `ERROR`. |

## Exit codes

| Code | Meaning |
|------|---------|
| `0` | Success, including a search with no results. |
| `1` | A run aborted, a request failed, or a file couldn't be parsed. The message names the cause. |
| `2` | Invalid command-line usage. |
| `3` | Configuration problem: missing or invalid config, missing prompt, unset API key, or a failed `validate` check. |
| `4` | A required Python package is missing; the message says what to install. |
| `130` | A run was interrupted after saving state. |

## Development

```bash
git clone https://github.com/xueromll/sci-etl-cli.git
cd sci-etl-cli
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest --cov=sci_etl_cli --cov-report=term-missing
```

To work against a local sci-etl-core checkout, install it first with
`pip install -e "../sci-etl-core[async,llm,pdf]"`.

The suite runs offline: arXiv is served by an `httpx.MockTransport` and the LLM
by a scripted client, so `run` is exercised end to end against real CSV and
state files. Coverage must stay at 100%.

## License

Released under the MIT License. See [LICENSE](LICENSE).
