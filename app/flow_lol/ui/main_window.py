"""Main application window."""

from __future__ import annotations

import logging

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QComboBox,
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
from flow_lol.ui.dashboard import DashboardWidget
from flow_lol.ui.sensor_worker import SensorWorker
from flow_lol.ui.settings_dialog import SettingsDialog

logger = logging.getLogger(__name__)

GAME_MODES = ["Ranked Solo/Duo", "Ranked Flex", "Normal", "ARAM", "Custom", "Other"]


class MainWindow(QMainWindow):
    def __init__(self, settings: AppSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Flow-LoL")
        self.setMinimumSize(900, 650)

        self.worker: SensorWorker | None = None
        self._prediction_count = 0
        self._in_match = False

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
        self.start_button.clicked.connect(self._start_session)
        self.stop_button = QPushButton("Stop session")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self._stop_session)

        toolbar.addWidget(self.start_button)
        toolbar.addWidget(self.stop_button)
        toolbar.addSeparator()

        self.game_mode_combo = QComboBox()
        self.game_mode_combo.addItems(GAME_MODES)
        self.game_mode_combo.setEnabled(False)
        toolbar.addWidget(QLabel("Mode:"))
        toolbar.addWidget(self.game_mode_combo)

        self.start_match_button = QPushButton("Start match")
        self.start_match_button.setEnabled(False)
        self.start_match_button.clicked.connect(self._start_match)

        self.stop_match_button = QPushButton("Stop match")
        self.stop_match_button.setEnabled(False)
        self.stop_match_button.clicked.connect(self._stop_match)

        toolbar.addWidget(self.start_match_button)
        toolbar.addWidget(self.stop_match_button)
        toolbar.addSeparator()

        dashboard_btn = QPushButton("Dashboard")
        dashboard_btn.setCheckable(True)
        dashboard_btn.setChecked(True)
        dashboard_btn.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        toolbar.addWidget(dashboard_btn)

    def _create_central_widget(self) -> None:
        self.stack = QStackedWidget()

        self.dashboard = DashboardWidget()
        self.stack.addWidget(self.dashboard)

        # Status label sits above the dashboard
        status_container = QWidget()
        status_layout = QVBoxLayout(status_container)
        self._status_label = QLabel("Ready. Press Start session to connect sensors.")
        self._status_label.setWordWrap(True)
        status_layout.addWidget(self._status_label)
        status_layout.addWidget(self.stack, stretch=1)

        self.setCentralWidget(status_container)

    def _create_statusbar(self) -> None:
        self.status = QStatusBar()
        self.setStatusBar(self.status)

    def _open_settings(self) -> None:
        if self.worker is not None and self.worker.isRunning():
            self._status_label.setText("Stop the session before changing settings.")
            return
        dialog = SettingsDialog(self.settings, self)
        if dialog.exec():
            self.settings = dialog.settings
            self.settings.save()
            logger.info("Settings updated")
            self._update_status()

    def _start_session(self) -> None:
        if self.worker is not None and self.worker.isRunning():
            return
        self._prediction_count = 0
        self._in_match = False
        self.worker = SensorWorker(self.settings, parent=self)
        self.worker.connection_changed.connect(self._on_connection_changed)
        self.worker.prediction.connect(self._on_prediction)
        self.worker.error.connect(self._on_error)
        self.worker.match_started.connect(self._on_match_started)
        self.worker.match_ended.connect(self._on_match_ended)
        self.worker.start()
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.game_mode_combo.setEnabled(True)
        self.start_match_button.setEnabled(True)
        self._status_label.setText("Session started. Connecting sensors...")
        logger.info("Session started")

    def _stop_session(self) -> None:
        if self.worker is not None:
            self.worker.stop()
            self.worker = None
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.game_mode_combo.setEnabled(False)
        self.start_match_button.setEnabled(False)
        self.stop_match_button.setEnabled(False)
        self._in_match = False
        self.dashboard.refresh_sessions()
        self._status_label.setText("Session stopped. Dashboard updated.")
        logger.info("Session stopped")

    def _start_match(self) -> None:
        if self.worker is None:
            return
        mode = self.game_mode_combo.currentText()
        self.worker.start_match(mode)

    def _stop_match(self) -> None:
        if self.worker is None:
            return
        self.worker.end_match()

    def _on_connection_changed(self, name: str, status: str) -> None:
        self._status_label.setText(f"[{name}] {status}")
        self._update_status()

    def _on_prediction(self, name: str, prediction: object) -> None:
        self._prediction_count += 1
        pred = prediction
        label_name = "flow" if pred.get("ensemble_label") == 1 else "no-flow"
        self._status_label.setText(
            f"[{name}] prediction #{self._prediction_count}: {label_name} "
            f"({pred.get('n_for_majority')}/{pred.get('n_votes')} votes)"
        )

    def _on_error(self, name: str, exc: object) -> None:
        self._status_label.setText(f"[{name}] error: {exc}")
        logger.error("[%s] worker error: %s", name, exc)

    def _on_match_started(self, game_mode: str, detected: bool) -> None:
        self._in_match = True
        self.start_match_button.setEnabled(False)
        self.stop_match_button.setEnabled(True)
        self.game_mode_combo.setEnabled(False)
        source = "auto-detected" if detected else "manual"
        self._status_label.setText(f"Match started ({source}): {game_mode}")
        logger.info("Match started: %s (%s)", game_mode, source)

    def _on_match_ended(self) -> None:
        self._in_match = False
        self.start_match_button.setEnabled(True)
        self.stop_match_button.setEnabled(False)
        self.game_mode_combo.setEnabled(True)
        self._status_label.setText("Match ended. Session still running.")
        logger.info("Match ended")

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
        match_text = "in match" if self._in_match else "no match"

        self.status.showMessage(
            f"Sensors: {sensor_text} | Models: {model_text} | "
            f"Webcam: {'on' if self.settings.webcam_enabled else 'off'} | "
            f"Auto-detect: {'on' if self.settings.auto_detect_game else 'off'} | "
            f"Match: {match_text}"
        )
