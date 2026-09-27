from __future__ import annotations

import io
import logging

from rich.console import Console

from sci_etl_cli.output import CORE_LOGGER_NAME, LOGGER_NAME, run_logger


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


def test_sci_etl_core_lines_reach_the_same_handlers_and_the_loggers_are_restored(tmp_path):
    log_file = tmp_path / "run.log"
    console = Console(file=io.StringIO(), width=200)
    core = logging.getLogger(f"{CORE_LOGGER_NAME}.pipeline_async")
    before = (logging.getLogger(CORE_LOGGER_NAME).level, logging.getLogger(CORE_LOGGER_NAME).propagate)
    with run_logger("INFO", log_file, console):
        core.warning("Record processing failed: LLMError('outage')")
        core.debug("hidden at INFO")
    written = log_file.read_text(encoding="utf-8")
    assert "[WARNING] Record processing failed: LLMError('outage')" in written
    assert "hidden at INFO" not in written
    assert "Record processing failed" in console.file.getvalue()
    core_logger = logging.getLogger(CORE_LOGGER_NAME)
    assert (core_logger.level, core_logger.propagate) == before
    assert core_logger.handlers == []
    log_file.unlink()
