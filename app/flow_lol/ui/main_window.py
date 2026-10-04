"""Main application window."""

from __future__ import annotations

import logging

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QStatusBar,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from flow_lol.config.settings import AppSettings
from flow_lol.ui.settings_dialog import SettingsDialog

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(self, settings: AppSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Flow-LoL")
        self.setMinimumSize(900, 650)

        self._create_menu()
        self._create_toolbar()
        self._create_central_widget()
        self._create_statusbar()

        self._update_status()

    def _create_menu(self) -> None:
        menu = self.menuBar()
        file_menu = menu.addMenu("File")

        settings_action = QAction("Settings", self)
        settings_action.setShortcut("Ctrl+,")
        settings_action.triggered.connect(self._open_settings)
        file_menu.addAction(settings_action)

        exit_action = QAction("Exit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

    def _create_toolbar(self) -> None:
        toolbar = QToolBar("Main")
        self.addToolBar(toolbar)

        self.start_button = QPushButton("Start session")
        self.stop_button = QPushButton("Stop session")
        self.stop_button.setEnabled(False)

        toolbar.addWidget(self.start_button)
        toolbar.addWidget(self.stop_button)
        toolbar.addSeparator()

        dashboard_btn = QPushButton("Dashboard")
        dashboard_btn.setCheckable(True)
        dashboard_btn.setChecked(True)
        dashboard_btn.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        toolbar.addWidget(dashboard_btn)

    def _create_central_widget(self) -> None:
        self.stack = QStackedWidget()

        # Placeholder dashboard
        dashboard = QWidget()
        layout = QVBoxLayout(dashboard)
        layout.addWidget(QLabel("Dashboard – flow timeline will appear here after a match."))
        layout.addStretch()
        self.stack.addWidget(dashboard)

        self.setCentralWidget(self.stack)

    def _create_statusbar(self) -> None:
        self.status = QStatusBar()
        self.setStatusBar(self.status)

    def _open_settings(self) -> None:
        dialog = SettingsDialog(self.settings, self)
        if dialog.exec():
            self.settings = dialog.settings
            self.settings.save()
            logger.info("Settings updated")
            self._update_status()

    def _update_status(self) -> None:
        sensors = []
        if self.settings.use_h10:
            sensors.append("H10")
        if self.settings.use_verity:
            sensors.append("Verity")
        sensor_text = " + ".join(sensors) if sensors else "none"

        enabled_models = [
            name
            for name, flag in {
                "SVM": self.settings.use_biraffe2_svm,
                "kNN": self.settings.use_biraffe2_knn,
                "B-RF": self.settings.use_biraffe2_rf,
                "I-RF": self.settings.use_irshad_rf,
                "MLP": self.settings.use_biraffe2_mlp,
            }.items()
            if flag
        ]
        model_text = f"{len(enabled_models)}/5 models" if enabled_models else "no models"

        self.status.showMessage(
            f"Sensors: {sensor_text} | Models: {model_text} | "
            f"Webcam: {'on' if self.settings.webcam_enabled else 'off'} | "
            f"Auto-detect: {'on' if self.settings.auto_detect_game else 'off'}"
        )
