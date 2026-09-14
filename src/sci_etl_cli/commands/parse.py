from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import click
from sci_etl_core.parsers.reference_trimmer import trim_after_references

from sci_etl_cli.errors import CliFailure, ExitCode

if TYPE_CHECKING:
    from sci_etl_core.parsers.base import Parser

_FORMATS = ("auto", "pdf", "latex", "html")
_PDF_MAGIC = b"%PDF"
_GZIP_MAGIC = b"\x1f\x8b"
_TAR_MAGIC = b"ustar"
_TAR_MAGIC_OFFSET = 257


@click.command("parse", short_help="Print the text extracted from a PDF, e-print or HTML file.")
@click.argument("file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--format",
    "file_format",
    type=click.Choice(_FORMATS),
    default="auto",
    show_default=True,
    help="How to read FILE. auto recognizes PDFs, arXiv e-prints and HTML.",
)
@click.option("--trim-references", is_flag=True, help="Cut the text at the references or acknowledgments.")
def parse_command(file: Path, file_format: str, trim_references: bool) -> None:
    """Print the text a bundled parser extracts from FILE.

    Accepts a PDF, an arXiv e-print (a tarball or gzipped TeX file) or an HTML
    page. Use it to check full-text quality without running a pipeline.
    """
    content = file.read_bytes()
    parser = build_parser(detect_format(content) if file_format == "auto" else file_format)
    text = parser.extract_text(content)
    if trim_references:
        text = trim_after_references(text) or text
    if not text.strip():
        raise CliFailure(f"No text could be extracted from {file}", ExitCode.FAILURE)
    click.echo(text)


def detect_format(content: bytes) -> str:
    stripped = content.lstrip()
    if stripped.startswith(_PDF_MAGIC):
        return "pdf"
    tar_magic = content[_TAR_MAGIC_OFFSET : _TAR_MAGIC_OFFSET + len(_TAR_MAGIC)]
    if content.startswith(_GZIP_MAGIC) or tar_magic == _TAR_MAGIC:
        return "latex"
    if stripped.startswith(b"<"):
        return "html"
    raise click.UsageError("Could not tell the file's format; pass --format pdf, latex or html.")


def build_parser(file_format: str) -> Parser:
    if file_format == "pdf":
        from sci_etl_core.parsers.pdf import PdfPlumberParser

        return PdfPlumberParser()
    if file_format == "latex":
        from sci_etl_core.parsers.latex import LatexTarballParser

        return LatexTarballParser()
    from sci_etl_core.parsers.html import HtmlTextParser

    return HtmlTextParser()
