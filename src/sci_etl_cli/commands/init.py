from __future__ import annotations

from importlib import resources
from pathlib import Path

import click
from rich.markup import escape

from sci_etl_cli.output import stdout_console

_TEMPLATES: tuple[tuple[str, str], ...] = (
    ("config.yaml", "config.yaml"),
    ("relevance.txt", "prompts/relevance.txt"),
    ("extraction.txt", "prompts/extraction.txt"),
    ("env.example", ".env.example"),
)


@click.command("init", short_help="Create a starter project.")
@click.argument("directory", required=False, default=".", type=click.Path(file_okay=False, path_type=Path))
@click.option("--force", is_flag=True, help="Overwrite files that already exist.")
def init_command(directory: Path, force: bool) -> None:
    """Create a starter project in DIRECTORY (default: the current folder).

    Writes config.yaml, prompts/relevance.txt, prompts/extraction.txt and
    .env.example. The example collects hot Jupiter measurements from arXiv;
    change the query, prompts and export columns for your own subject.
    """
    targets = [(template, directory / relative) for template, relative in _TEMPLATES]
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
