"""Launcher used by PyInstaller to start the Flow-LoL GUI."""

import sys
from pathlib import Path


def _ensure_project_root() -> None:
    """When running from a PyInstaller bundle, add the bundled code to sys.path."""
    if getattr(sys, "frozen", False):
        bundle_dir = Path(sys._MEIPASS)  # type: ignore[attr-defined]
        package_dir = bundle_dir / "flow_lol"
        if package_dir.is_dir() and str(package_dir.parent) not in sys.path:
            sys.path.insert(0, str(package_dir.parent))


if __name__ == "__main__":
    _ensure_project_root()
    from flow_lol.main import main

    raise SystemExit(main())
