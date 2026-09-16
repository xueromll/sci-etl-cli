# Quick start

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

## Adapting it to your subject

To use the CLI for another subject, change `pipeline.search_query`, both
prompts, and the `export` columns in the [config file](config-file.md). The
extraction prompt has to ask for JSON containing `result_key`, `key_column`,
and every value column; `validate` checks this.

Rules that don't fit in a config file, such as which names refer to the same
entity, plug in as [Python code](plugins.md).
