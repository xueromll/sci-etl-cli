from __future__ import annotations

import json
import logging
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

import click
from rich.console import Console
from rich.logging import RichHandler

LOGGER_NAME = "sci_etl_cli"
_FILE_FORMAT = "[%(asctime)s] [%(levelname)s] %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def stdout_console() -> Console:
    return Console(highlight=False)


def stderr_console() -> Console:
    return Console(stderr=True, highlight=False)


def print_json(payload: Any) -> None:
    click.echo(json.dumps(payload, indent=2, ensure_ascii=False))


def discard(_message: str) -> None:
    return None


@contextmanager
def run_logger(level: str, log_file: Path | None, console: Console) -> Iterator[logging.Logger]:
    """Log to ``console`` and, when given, to ``log_file`` for the duration of the block.

    The log file's folder is created when missing, and every handler is closed
    when the block exits so the file is never left locked.
    """
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(level)
    logger.propagate = False
    handlers: list[logging.Handler] = [RichHandler(console=console, show_path=False, markup=False)]
    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(logging.Formatter(_FILE_FORMAT, _DATE_FORMAT))
        handlers.append(file_handler)
    for handler in handlers:
        logger.addHandler(handler)
    try:
        yield logger
    finally:
        for handler in handlers:
            logger.removeHandler(handler)
            handler.close()
