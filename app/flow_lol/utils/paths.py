"""Central path helpers."""

from __future__ import annotations

import sys
from pathlib import Path


def is_frozen() -> bool:
    """True when running inside a PyInstaller bundle."""
    return getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")


def app_root() -> Path:
    """Directory containing the application code or the frozen bundle."""
    if is_frozen():
        return Path(sys.executable).parent
    return Path(__file__).resolve().parents[2]


def default_data_dir() -> Path:
    """Writable directory for recordings, DB, and logs.

    Inside a bundle we place data next to the executable so the lab setup
    does not depend on roaming app-data folders. For development the
    ``app/data`` folder is used.
    """
    if is_frozen():
        return app_root() / "FlowLoLData"
    return app_root() / "data"


def config_file() -> Path:
    """User config JSON path."""
    if is_frozen():
        return default_data_dir() / "config.json"
    return app_root() / "config.json"


def ensure_directories() -> None:
    data = default_data_dir()
    (data / "ecg").mkdir(parents=True, exist_ok=True)
    (data / "webcam").mkdir(parents=True, exist_ok=True)
    (data / "logs").mkdir(parents=True, exist_ok=True)


def models_dir() -> Path:
    return app_root() / "models"
