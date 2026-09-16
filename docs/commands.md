# Commands

| Command | What it does | Network | Writes |
|---------|--------------|---------|--------|
| `sci-etl init [DIRECTORY]` | Creates a starter project. Refuses to overwrite existing files unless given `--force`. | none | project files |
| `sci-etl validate CONFIG` | Checks the config, prompts, API key, and packages. `--online` adds one arXiv and one LLM request once the offline checks pass. | only with `--online` | nothing |
| `sci-etl search CONFIG` | Shows one page of arXiv results, each marked `new` or `processed`. | arXiv | nothing |
| `sci-etl run CONFIG` | Runs the pipeline, resuming from saved state, and logs token usage at the end. | arXiv and the LLM | export CSV, state, log |
| `sci-etl status CONFIG` | Shows processed records, the saved offset, the last run time, and export rows. | none | nothing |
| `sci-etl parse FILE` | Prints the text a bundled parser extracts from a PDF, arXiv e-print, or HTML file. | none | nothing |

Every command accepts `--help`. Logs and errors go to stderr; `search --json`,
`status --json`, and `parse` print their results to stdout, so they can be
piped.

## Running pipelines

**Stopping a run.** Press Ctrl+C once: records in flight are cancelled and left
unmarked, state is saved, and the command exits with 130. The next run retries
those records. A second Ctrl+C exits immediately.

**Resuming.** A run starts at the listing offset saved by the previous one.
arXiv lists the newest submissions first, so new papers push older ones to
higher offsets; `--rescan` starts again at offset 0 and skips processed papers
by id, which costs listing requests but no LLM calls.

**Throttling.** When arXiv or the LLM provider answers `429` with a
`Retry-After` header, the request waits as long as it asks, up to 60 seconds,
and each retry is logged.

**Token usage.** When a run finishes, aborts, or is interrupted, `run` logs how
many LLM requests it made and the prompt and completion tokens they used. Set
`llm.input_cost_per_million` and `llm.output_cost_per_million` to your
provider's prices to add an estimated cost, in the currency of those prices:

```text
LLM usage: 42 requests, 1,204,388 prompt and 9,112 completion tokens, estimated cost 0.1861
```

## Reference

This reference is generated from the command definitions, so it always matches
`sci-etl --help` for this release.

::: mkdocs-click
    :module: sci_etl_cli.app
    :command: cli
    :prog_name: sci-etl
    :depth: 1
    :style: table
    :list_subcommands: true
