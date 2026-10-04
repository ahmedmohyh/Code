"""Application entry point."""

import sys

from PyQt6.QtWidgets import QApplication

from flow_lol.config.settings import AppSettings
from flow_lol.ui.main_window import MainWindow
from flow_lol.utils import logging as app_logging
from flow_lol.utils.paths import ensure_directories


def main() -> int:
    app_logging.setup_logging()
    ensure_directories()

    settings = AppSettings.load()
    settings.save()  # write back with any missing defaults

    app = QApplication(sys.argv)
    app.setApplicationName("Flow-LoL")
    app.setOrganizationName("FlowLoL")

    window = MainWindow(settings)
    window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
