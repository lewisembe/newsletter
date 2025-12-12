"""
Shared logging utilities for the newsletter pipeline.

Provides rotating file handlers and retention cleanup to avoid
unbounded log growth on disk.
"""

from __future__ import annotations

import logging
import sys
import shutil
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler
from pathlib import Path


DEFAULT_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


def _cleanup_old_log_dirs(log_root: Path, retention_days: int) -> None:
    """
    Remove dated log directories older than the retention window.
    Only deletes subdirectories named as YYYY-MM-DD.
    """
    if retention_days <= 0:
        return

    cutoff_date = datetime.now().date() - timedelta(days=retention_days)

    for child in log_root.iterdir():
        if not child.is_dir():
            continue
        try:
            dir_date = datetime.strptime(child.name, "%Y-%m-%d").date()
        except ValueError:
            # Skip non date-named folders
            continue

        if dir_date < cutoff_date:
            shutil.rmtree(child, ignore_errors=True)


def setup_rotating_file_logger(
    run_date: str,
    log_filename: str,
    *,
    verbose: bool = False,
    log_level: int = logging.INFO,
    max_bytes: int = 20 * 1024 * 1024,  # 20 MB per file
    backup_count: int = 5,  # Keep up to 5 rotated files alongside the active one
    retention_days: int = 14,
    stream_to_stdout: bool = True,
) -> str:
    """
    Configure root logging with a rotating file handler and retention cleanup.

    Args:
        run_date: Date string (YYYY-MM-DD) used for log directory.
        log_filename: Name of the log file inside the date directory.
        verbose: If True, set log level to DEBUG.
        log_level: Base log level when verbose is False.
        max_bytes: Maximum size per log file before rotating.
        backup_count: Number of rotated files to keep.
        retention_days: Remove log directories older than this many days.
        stream_to_stdout: Stream logs to stdout instead of stderr.

    Returns:
        Path to the active log file as string.
    """
    log_root = Path("logs")
    log_root.mkdir(exist_ok=True)

    _cleanup_old_log_dirs(log_root, retention_days)

    log_dir = log_root / run_date
    log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_dir / log_filename

    # Reset existing handlers to avoid duplicates on reconfig
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    effective_level = logging.DEBUG if verbose else log_level
    root_logger.setLevel(effective_level)

    formatter = logging.Formatter(DEFAULT_FORMAT)

    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
    )
    file_handler.setLevel(effective_level)
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler(sys.stdout if stream_to_stdout else None)
    stream_handler.setLevel(effective_level)
    stream_handler.setFormatter(formatter)

    root_logger.addHandler(file_handler)
    root_logger.addHandler(stream_handler)

    return str(log_file)
