"""Main application window."""

from __future__ import annotations

import logging

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QStatusBar,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from flow_lol.config.settings import AppSettings
from flow_lol.ui.dashboard import DashboardWidget
from flow_lol.ui.logs_widget import LogsWidget
from flow_lol.ui.sensor_worker import SensorWorker
from flow_lol.ui.settings_dialog import SettingsDialog
from flow_lol.ui.webcam_widget import WebcamWidget

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
        self._webcam_recording = False

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

        self.toggle_webcam_button = QPushButton("Disable webcam")
        self.toggle_webcam_button.setEnabled(False)
        self.toggle_webcam_button.clicked.connect(self._toggle_webcam)
        toolbar.addWidget(self.toggle_webcam_button)
        toolbar.addSeparator()

        self._tab_buttons: list[QPushButton] = []
        self.dashboard_btn = self._add_tab_button(toolbar, "Dashboard", 0)
        self.logs_btn = self._add_tab_button(toolbar, "Logs", 1)
        self.webcam_btn = self._add_tab_button(toolbar, "Webcam", 2)

        toolbar.addSeparator()
        exit_btn = QPushButton("Exit")
        exit_btn.clicked.connect(self._safe_exit)
        toolbar.addWidget(exit_btn)

    def _add_tab_button(self, toolbar: QToolBar, label: str, index: int) -> QPushButton:
        btn = QPushButton(label)
        btn.setCheckable(True)
        btn.setChecked(index == 0)
        btn.clicked.connect(lambda checked, i=index: self._set_tab(i))
        toolbar.addWidget(btn)
        self._tab_buttons.append(btn)
        return btn

    def _set_tab(self, index: int) -> None:
        for i, btn in enumerate(self._tab_buttons):
            btn.setChecked(i == index)
        self.stack.setCurrentIndex(index)

    def _create_central_widget(self) -> None:
        self.stack = QStackedWidget()

        self.dashboard = DashboardWidget()
        self.stack.addWidget(self.dashboard)

        self.logs = LogsWidget(logs_dir=Path(self.settings.logs_save_path))
        self.stack.addWidget(self.logs)

        self.webcam = WebcamWidget(on_toggle=self._toggle_webcam)
        self.stack.addWidget(self.webcam)

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
        self.worker.samples.connect(self._on_samples)
        self.worker.error.connect(self._on_error)
        self.worker.match_started.connect(self._on_match_started)
        self.worker.match_ended.connect(self._on_match_ended)
        self.worker.webcam_changed.connect(self._on_webcam_changed)
        self.worker.start()
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.game_mode_combo.setEnabled(True)
        self.start_match_button.setEnabled(True)
        self.toggle_webcam_button.setEnabled(False)
        self.toggle_webcam_button.setText("Disable webcam")
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
        self.toggle_webcam_button.setEnabled(False)
        self.toggle_webcam_button.setText("Disable webcam")
        self.webcam.set_recording_state(False, None)
        self._webcam_recording = False
        self._in_match = False
        self.dashboard.refresh_sessions()
        self.logs.refresh_logs()
        self.webcam.refresh_list()
        self._status_label.setText("Session stopped. Dashboard updated.")
        logger.info("Session stopped")

    def _safe_exit(self) -> None:
        """Stop any running session cleanly before closing the app."""
        if self.worker is not None and self.worker.isRunning():
            reply = QMessageBox.question(
                self,
                "Exit Flow-LoL",
                "A session is running. Stop it and exit?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
            self._stop_session()
        self.settings.save()
        self.close()

    def closeEvent(self, event: object) -> None:
        """Intercept window close to ensure clean shutdown."""
        if self.worker is not None and self.worker.isRunning():
            self._stop_session()
        self.settings.save()
        event.accept()

    def _start_match(self) -> None:
        if self.worker is None:
            return
        mode = self.game_mode_combo.currentText()
        self.worker.start_match(mode)

    def _stop_match(self) -> None:
        if self.worker is None:
            return
        self.worker.end_match()

    def _toggle_webcam(self) -> None:
        """Tell the worker to start or stop webcam recording."""
        if self.worker is None:
            return
        self.worker.toggle_webcam()

    def _on_webcam_changed(self, recording: bool, path: object) -> None:
        """Update UI when the worker reports a webcam state change."""
        self._webcam_recording = recording
        self.toggle_webcam_button.setEnabled(True)
        self.toggle_webcam_button.setText("Disable webcam" if recording else "Enable webcam")
        self.webcam.set_recording_state(recording, path)
        self._update_status()
        status = "Webcam recording started" if recording else "Webcam recording stopped"
        if path:
            self._status_label.setText(f"{status}: {path}")
        else:
            self._status_label.setText(status)

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

    def _on_samples(self, name: str, samples: object) -> None:
        self.logs.add_samples(name, samples)

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
            f"Webcam: {'recording' if self._webcam_recording else 'off'} | "
            f"Auto-detect: {'on' if self.settings.auto_detect_game else 'off'} | "
            f"Match: {match_text}"
        )
