# sci-etl CLI

`sci-etl` runs [sci-etl-core](https://xueromll.github.io/sci-etl-core/latest/)
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

## Installation

Python 3.11 or newer is required.

```bash
pip install sci-etl-cli
```

This installs the `sci-etl` command along with `sci-etl-core[async,llm,pdf]`,
`click`, and `rich`. `pipx install sci-etl-cli` keeps it in an environment of
its own. `sci-etl --version` prints the CLI and library versions.

## Compatibility

Each CLI release is tested against a range of sci-etl-core releases, and pip
installs a matching one:

| sci-etl-cli | sci-etl-core |
|-------------|--------------|
| 0.1.x | 0.1.2 or newer 0.1 releases |
| 0.2.x | 0.2 |
| next release | 0.4 |

## Where to go next

- [Quick start](quick-start.md) walks through a first project.
- [Commands](commands.md) lists every command and option.
- [Config file](config-file.md) documents every key.
- [Plug-ins](plugins.md) add domain rules written in Python.
- [Exit codes](exit-codes.md) help scripts react to failures.

Need a source other than arXiv, a different exporter, or search over what you
collected? Build the pipeline in Python with
[sci-etl-core](https://xueromll.github.io/sci-etl-core/latest/getting-started/quick-start/)
instead.
