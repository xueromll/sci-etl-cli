# sci-etl-cli

`sci-etl` runs [sci-etl-core](https://github.com/xueromll/sci-etl-core)
extraction pipelines from a single YAML file, with no wiring code. It searches
arXiv, asks an LLM which papers are relevant, extracts structured entities from
their full text, and upserts them into a CSV. Runs resume where the last one
stopped.

**Documentation: https://xueromll.github.io/sci-etl-core/latest/cli/**

```text
$ sci-etl init hot-jupiters
$ sci-etl validate hot-jupiters/config.yaml
$ sci-etl search hot-jupiters/config.yaml --limit 5
$ sci-etl run hot-jupiters/config.yaml --limit 20
$ sci-etl status hot-jupiters/config.yaml
```

## Installation

Python 3.11 or newer is required.

```bash
pip install sci-etl-cli
```

This installs the `sci-etl` command along with `sci-etl-core[async,llm,pdf]`,
`click`, and `rich`. `pipx install sci-etl-cli` keeps it in an environment of
its own.

## Quick start

1. `sci-etl init hot-jupiters` writes a working example project.
2. Copy `.env.example` to `.env` beside the config and set `LLM_API_KEY`.
3. `sci-etl validate hot-jupiters/config.yaml` checks the config, prompts, key,
   and packages.
4. `sci-etl search hot-jupiters/config.yaml` previews matching papers without
   calling the LLM.
5. `sci-etl run hot-jupiters/config.yaml` exports entities to `out/planets.csv`.
   Run it again to continue where it stopped.

## Documentation

| Topic | Where |
|-------|-------|
| A first project, step by step | [Quick start](https://xueromll.github.io/sci-etl-core/latest/cli/quick-start/) |
| Every command and option, stopping, resuming, token usage | [Commands](https://xueromll.github.io/sci-etl-core/latest/cli/commands/) |
| Every config key and its default | [Config file](https://xueromll.github.io/sci-etl-core/latest/cli/config-file/) |
| Domain rules written in Python | [Plug-ins](https://xueromll.github.io/sci-etl-core/latest/cli/plugins/) |
| What each exit code means | [Exit codes](https://xueromll.github.io/sci-etl-core/latest/cli/exit-codes/) |

## Development

```bash
git clone https://github.com/xueromll/sci-etl-cli.git
cd sci-etl-cli
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev,lint]"
pytest --cov=sci_etl_cli --cov-report=term-missing
ruff check .
mypy
```

To work against a local sci-etl-core checkout, install it first with
`pip install -e "../sci-etl-core[async,llm,pdf]"`.

The suite runs offline: arXiv is served by an `httpx.MockTransport` and the LLM
by a scripted client, so `run` is exercised end to end against real CSV and
state files. Coverage must stay at 100%.

### Documentation

The pages under `docs/` are published as the CLI section of the
[sci-etl-core site](https://xueromll.github.io/sci-etl-core/), which reads this
repository's `docs/` folder and the `nav` in `mkdocs.yml`. Preview them on
their own with:

```bash
pip install -e ".[docs]"
mkdocs serve
```

Link to sci-etl-core pages with absolute URLs, since the pages are also built
on their own. `mkdocs build --strict` runs in CI. Publishing a release asks
sci-etl-core to rebuild the site when the `DOCS_DISPATCH_TOKEN` secret is set;
otherwise run sci-etl-core's Docs workflow by hand.

## License

Released under the MIT License. See [LICENSE](LICENSE).
