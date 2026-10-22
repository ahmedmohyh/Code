"""Application logging setup."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from flow_lol.utils.paths import default_data_dir

_current_log_file: Optional[Path] = None


def get_current_log_file() -> Optional[Path]:
    """Return the log file currently being written by the app."""
    return _current_log_file


def setup_logging(level: int = logging.INFO, logs_dir: str | None = None) -> None:
    global _current_log_file
    log_dir = Path(logs_dir) if logs_dir else default_data_dir() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_file = log_dir / f"flow_lol_{timestamp}.log"
    _current_log_file = log_file

    root = logging.getLogger()
    root.setLevel(level)
    # Remove any existing handlers so a fresh path takes effect.
    for handler in list(root.handlers):
        root.removeHandler(handler)

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    )
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    root.addHandler(file_handler)
    root.addHandler(console_handler)
