"""Redacted, bounded local logging with no telemetry side effects."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .paths import user_data_dir
from .persistence import ensure_private_directory
from .redaction import redact_support_text

LOG_FILE_NAME = "wolflauncher.log"
LOG_MAX_BYTES = 512 * 1024
LOG_BACKUP_COUNT = 3


class RedactingFormatter(logging.Formatter):
    def format(self, record):
        return redact_support_text(super().format(record))


def configure_local_logging(data_dir: Path | None = None) -> Path:
    """Configure a rotating local log. Nothing is sent off-device."""
    directory = data_dir or user_data_dir()
    ensure_private_directory(directory)
    path = directory / LOG_FILE_NAME
    logger = logging.getLogger("wolflauncher")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if any(getattr(handler, "baseFilename", None) == str(path) for handler in logger.handlers):
        return path
    handler = RotatingFileHandler(path, maxBytes=LOG_MAX_BYTES, backupCount=LOG_BACKUP_COUNT, encoding="utf-8")
    handler.setFormatter(RedactingFormatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logger.addHandler(handler)
    return path
