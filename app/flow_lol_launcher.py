"""Launcher used by PyInstaller to start the Flow-LoL GUI."""

import logging
import os
import sys
import tempfile
import traceback
from pathlib import Path


def _ensure_project_root() -> None:
    """When running from a PyInstaller bundle, add the bundled code to sys.path."""
    if getattr(sys, "frozen", False):
        bundle_dir = Path(sys._MEIPASS)  # type: ignore[attr-defined]
        package_dir = bundle_dir / "flow_lol"
        if package_dir.is_dir() and str(package_dir.parent) not in sys.path:
            sys.path.insert(0, str(package_dir.parent))


def _setup_comtypes_cache() -> None:
    """Force comtypes to use a stable, writable cache dir before any COM call.

    In a PyInstaller onefile bundle the default comtypes gen_dir may be inside
    the read-only MEIPASS temp folder. This causes fatal COM wrapper generation
    failures (silent crashes). Point it to the user's local temp directory.
    """
    try:
        import comtypes.client

        cache_dir = Path(tempfile.gettempdir()) / "comtypes_cache" / "FlowLoL"
        cache_dir.mkdir(parents=True, exist_ok=True)
        comtypes.client.gen_dir = str(cache_dir)
        os.environ["COMTYPES_CACHE_DIR"] = str(cache_dir)
    except Exception:
        pass


def _install_crash_handler() -> None:
    """Log unhandled exceptions and fatal aborts to the FlowLoL data directory.

    PyInstaller onefile crashes that bypass the Python logger are written to a
    plain-text crash file so we can diagnose them without running from console.
    """
    try:
        from flow_lol.utils.paths import default_data_dir

        crash_dir = default_data_dir() / "logs"
        crash_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        crash_dir = Path(tempfile.gettempdir())

    def _excepthook(exc_type, exc_value, exc_tb):
        try:
            stamp = logging.Formatter().formatTime(logging.LogRecord(
                None, 0, "", 0, "", (), None
            ))
        except Exception:
            import datetime
            stamp = datetime.datetime.now().isoformat()
        crash_file = crash_dir / f"crash_{stamp.replace(':', '-')}.txt"
        msg = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        try:
            crash_file.write_text(f"Unhandled exception at {stamp}\n{msg}", encoding="utf-8")
        except Exception:
            pass
        # Also print to stderr so console-mode runs show it too.
        sys.stderr.write(msg)
        sys.__excepthook__(exc_type, exc_value, exc_tb)

    sys.excepthook = _excepthook


if __name__ == "__main__":
    _ensure_project_root()
    _setup_comtypes_cache()
    _install_crash_handler()
    from flow_lol.main import main

    raise SystemExit(main())
