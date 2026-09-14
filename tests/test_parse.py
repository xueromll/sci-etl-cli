from __future__ import annotations

import gzip
import io
import tarfile

from sci_etl_cli.commands.parse import build_parser, detect_format

_TEX = (
    b"\\documentclass{article}\n\\section{Results}\nWASP-12 b has an orbital period of 1.09 d.\n\n"
    b"\\begin{thebibliography}{9}\n\\bibitem{hebb} Hebb et al. 2009\n"
)


def test_html_is_detected_and_printed(run_cli, tmp_path):
    page = tmp_path / "abstract.html"
    page.write_text("<html><body><h1>WASP-12 b</h1><p>Orbital period 1.09 days.</p></body></html>", encoding="utf-8")
    result = run_cli("parse", str(page))
    assert result.exit_code == 0
    assert result.stdout.strip() == "WASP-12 b Orbital period 1.09 days."


def test_gzipped_tex_is_parsed_with_and_without_references(run_cli, tmp_path):
    eprint = tmp_path / "2609.00001v1"
    eprint.write_bytes(gzip.compress(_TEX))
    trimmed = run_cli("parse", str(eprint), "--trim-references")
    assert trimmed.exit_code == 0
    assert "orbital period of 1.09 d." in trimmed.stdout
    assert "bibitem" not in trimmed.stdout
    full = run_cli("parse", str(eprint), "--format", "latex")
    assert "bibitem" in full.stdout


def test_tarballs_are_detected_as_latex():
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        member = tarfile.TarInfo("main.tex")
        member.size = len(_TEX)
        archive.addfile(member, io.BytesIO(_TEX))
    assert detect_format(buffer.getvalue()) == "latex"


def test_pdfs_are_detected_and_get_the_pdf_parser():
    assert detect_format(b"\n%PDF-1.7\n") == "pdf"
    assert type(build_parser("pdf")).__name__ == "PdfPlumberParser"


def test_unrecognized_content_asks_for_a_format(run_cli, tmp_path):
    notes = tmp_path / "notes.txt"
    notes.write_text("WASP-12 b orbital period 1.09 d", encoding="utf-8")
    result = run_cli("parse", str(notes))
    assert result.exit_code == 2
    assert "--format" in result.stderr


def test_parser_failure_exits_one(run_cli, tmp_path):
    notes = tmp_path / "notes.txt"
    notes.write_text("WASP-12 b orbital period 1.09 d", encoding="utf-8")
    result = run_cli("parse", str(notes), "--format", "latex")
    assert result.exit_code == 1
    assert "neither a tarball nor gzipped TeX" in result.stderr


def test_empty_text_exits_one(run_cli, tmp_path):
    page = tmp_path / "empty.html"
    page.write_text("<html><body></body></html>", encoding="utf-8")
    result = run_cli("parse", str(page))
    assert result.exit_code == 1
    assert "No text could be extracted" in result.stderr
