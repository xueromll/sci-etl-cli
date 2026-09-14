from __future__ import annotations

import io
import logging

from rich.console import Console

from sci_etl_cli.output import LOGGER_NAME, run_logger


def test_run_logger_writes_the_file_and_releases_it(tmp_path):
    log_file = tmp_path / "logs" / "run.log"
    console = Console(file=io.StringIO(), width=200)
    with run_logger("INFO", log_file, console) as log:
        log.info("Listing page at offset 0")
        log.debug("hidden at INFO")
    written = log_file.read_text(encoding="utf-8")
    assert "[INFO] Listing page at offset 0" in written
    assert "hidden at INFO" not in written
    assert "Listing page at offset 0" in console.file.getvalue()
    assert logging.getLogger(LOGGER_NAME).handlers == []
    log_file.unlink()


def test_run_logger_without_a_file_only_uses_the_console():
    console = Console(file=io.StringIO(), width=200)
    with run_logger("WARNING", None, console) as log:
        log.warning("Record processing failed")
        assert not any(isinstance(handler, logging.FileHandler) for handler in log.handlers)
    assert "Record processing failed" in console.file.getvalue()
