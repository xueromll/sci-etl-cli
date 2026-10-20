from __future__ import annotations

from dataclasses import dataclass
from importlib import resources
from pathlib import Path

import click
from rich.markup import escape

from sci_etl_cli.output import stdout_console
from sci_etl_cli.settings import SourceKind


@dataclass(frozen=True, slots=True)
class Starter:
    """The template files a starter project is written from."""

    config: str
    relevance: str
    extraction: str

    def files(self) -> tuple[tuple[str, str], ...]:
        return (
            (self.config, "config.yaml"),
            (self.relevance, "prompts/relevance.txt"),
            (self.extraction, "prompts/extraction.txt"),
            ("env.example", ".env.example"),
        )


STARTERS: dict[SourceKind, Starter] = {
    "arxiv": Starter("config.yaml", "relevance.txt", "extraction.txt"),
    "pubmed": Starter("config-pubmed.yaml", "relevance-trials.txt", "extraction-trials.txt"),
    "semantic_scholar": Starter("config-semantic_scholar.yaml", "relevance-trials.txt", "extraction-trials.txt"),
    "openalex": Starter("config-openalex.yaml", "relevance-trials.txt", "extraction-trials.txt"),
}


@click.command("init", short_help="Create a starter project.")
@click.argument("directory", required=False, default=".", type=click.Path(file_okay=False, path_type=Path))
@click.option(
    "--source",
    type=click.Choice(list(STARTERS)),
    default="arxiv",
    show_default=True,
    help="Literature source the starter searches.",
)
@click.option("--force", is_flag=True, help="Overwrite files that already exist.")
def init_command(directory: Path, source: SourceKind, force: bool) -> None:
    """Create a starter project in DIRECTORY (default: the current folder).

    Writes config.yaml, prompts/relevance.txt, prompts/extraction.txt and
    .env.example. The arXiv example collects hot Jupiter measurements; the
    PubMed, Semantic Scholar and OpenAlex examples collect the arms of
    metformin trials. Change the query, prompts and export columns for your
    own subject.
    """
    targets = [(template, directory / relative) for template, relative in STARTERS[source].files()]
    existing = [path for _template, path in targets if path.exists()]
    if existing and not force:
        names = ", ".join(str(path) for path in existing)
        raise click.UsageError(f"Refusing to overwrite {names}; pass --force to replace them.")

    templates = resources.files("sci_etl_cli").joinpath("templates")
    console = stdout_console()
    for template, path in targets:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(templates.joinpath(template).read_text(encoding="utf-8"), encoding="utf-8")
        console.print(f"[green]wrote[/] {escape(str(path))}", soft_wrap=True)
    console.print(
        "\nNext: copy .env.example to .env, set LLM_API_KEY, then run "
        f"[bold]sci-etl validate {escape(str(directory / 'config.yaml'))}[/]",
        soft_wrap=True,
    )
