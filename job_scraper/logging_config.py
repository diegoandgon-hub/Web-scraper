"""F10.1 — Logging configuration: console (INFO) + rotating file (DEBUG)."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from job_scraper.config import LOG_BACKUP_COUNT, LOG_DIR, LOG_FILE, LOG_LEVEL, LOG_MAX_BYTES

_CONSOLE_FORMAT = "%(levelname)s | %(name)s | %(message)s"
_FILE_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"


def setup_logging(log_dir=None, log_file=None) -> None:
    """Configure the root logger with console and rotating file handlers.

    Args:
        log_dir: Override for the log directory (useful for testing).
        log_file: Override for the log file path (useful for testing).
    """
    resolved_dir = log_dir if log_dir is not None else LOG_DIR
    resolved_file = log_file if log_file is not None else LOG_FILE

    resolved_dir.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    # Avoid adding our handlers twice in production usage
    if any(getattr(h, "_job_scraper", False) for h in root.handlers):
        return
    root.setLevel(logging.DEBUG)

    # Console handler — INFO level, concise format
    console = logging.StreamHandler()
    console.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
    console.setFormatter(logging.Formatter(_CONSOLE_FORMAT))
    console._job_scraper = True  # type: ignore[attr-defined]
    root.addHandler(console)

    # Rotating file handler — DEBUG level, detailed format
    file_handler = RotatingFileHandler(
        str(resolved_file),
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(_FILE_FORMAT))
    file_handler._job_scraper = True  # type: ignore[attr-defined]
    root.addHandler(file_handler)
