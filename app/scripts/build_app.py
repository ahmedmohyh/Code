"""Build the Flow-LoL Windows app with PyInstaller.

Usage (from the app folder):
    python scripts\build_app.py

Prerequisites:
    pip install -r requirements.txt
    python scripts\export_models.py
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


def main() -> int:
    here = Path(__file__).resolve().parent
    app_root = here.parent
    spec = here / "FlowLoL.spec"

    if not spec.exists():
        print(f"Spec file not found: {spec}", file=sys.stderr)
        return 1

    # Optional: ensure models exist and warn if missing.
    models_dir = app_root / "models"
    if not models_dir.exists() or not any(models_dir.iterdir()):
        print(
            "WARNING: app/models/ is empty. Run scripts/export_models.py first "
            "or the app will have no classifiers to load.",
            file=sys.stderr,
        )

    pyinstaller = shutil.which("pyinstaller") or "pyinstaller"
    cmd = [pyinstaller, "--noconfirm", str(spec)]
    print("Running:", " ".join(cmd))
    result = subprocess.run(cmd, cwd=str(app_root))
    if result.returncode != 0:
        print("PyInstaller build failed.", file=sys.stderr)
        return result.returncode

    print("\nBuild complete. Output is in dist/FlowLoL/")
    print("Next step: open scripts/installer.iss in Inno Setup and compile, or run iscc.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
