"""Application entry point."""

import sys

from PyQt6.QtWidgets import QApplication

from flow_lol.config.settings import AppSettings
from flow_lol.persistence.repository import SessionRepository
from flow_lol.ui.main_window import MainWindow
from flow_lol.utils import logging as app_logging
from flow_lol.utils.paths import ensure_directories


def main() -> int:
    settings = AppSettings.load()
    settings.save()  # write back with any missing defaults

    app_logging.setup_logging(logs_dir=settings.logs_save_path)
    ensure_directories()

    # Close any sessions left open after a crash so the dashboard never shows
    # yesterday's session as "running".
    repo = SessionRepository(settings.db_path)
    n_closed = repo.close_stale_sessions()
    if n_closed:
        print(f"Closed {n_closed} stale session(s) left open from a previous run.")

    app = QApplication(sys.argv)
    app.setApplicationName("Flow-LoL")
    app.setOrganizationName("FlowLoL")

    window = MainWindow(settings)
    window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
