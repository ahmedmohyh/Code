"""Central path helpers."""

from __future__ import annotations

import os
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

    Inside a bundle we use the current user's ``%LOCALAPPDATA%\FlowLoL\Data``
    so recordings are writable without admin rights. For development the
    ``app/data`` folder is used.
    """
    if is_frozen():
        local_appdata = os.environ.get("LOCALAPPDATA")
        if local_appdata:
            return Path(local_appdata) / "FlowLoL" / "Data"
        return Path.home() / "FlowLoL" / "Data"
    return app_root() / "data"


def config_file() -> Path:
    """User config JSON path."""
    if is_frozen():
        return default_data_dir() / "config.json"
    return app_root() / "config.json"


def database_path() -> Path:
    return default_data_dir() / "flow_lol.db"


def ensure_directories() -> None:
    data = default_data_dir()
    data.mkdir(parents=True, exist_ok=True)
    (data / "ecg").mkdir(parents=True, exist_ok=True)
    (data / "webcam").mkdir(parents=True, exist_ok=True)
    (data / "logs").mkdir(parents=True, exist_ok=True)


def models_dir() -> Path:
    return app_root() / "models"
