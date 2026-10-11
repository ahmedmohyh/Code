"""Main application window with a modern sidebar + header layout."""

from __future__ import annotations

import logging

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from flow_lol.config.settings import AppSettings
from flow_lol.ui.components import (
    CardWidget,
    CompactActionBar,
    SidebarButton,
    StatusPill,
    ToggleActionButton,
)
from flow_lol.ui.dashboard import DashboardWidget
from flow_lol.ui.logs_widget import LogsWidget
from flow_lol.ui.sensor_worker import SensorWorker
from flow_lol.ui.settings_dialog import SettingsDialog
from flow_lol.ui.styles import Colors, Spacing, stylesheet
from flow_lol.ui.webcam_widget import WebcamWidget

logger = logging.getLogger(__name__)

GAME_MODES = ["Ranked Solo/Duo", "Ranked Flex", "Normal", "ARAM", "Custom", "Other"]


class MainWindow(QMainWindow):
    def __init__(self, settings: AppSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Flow-LoL")
        self.setMinimumSize(1000, 720)

        self.worker: SensorWorker | None = None
        self._prediction_count = 0
        self._in_match = False
        self._webcam_recording = False
        self._sensor_status = "idle"

        self._apply_stylesheet()
        self._create_menu()
        self._create_central_layout()
        self._create_statusbar()

        self._update_status()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _apply_stylesheet(self) -> None:
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(stylesheet())

    def _create_menu(self) -> None:
        menu = self.menuBar()
        file_menu = menu.addMenu("File")

        settings_action = QAction("Settings", self)
        settings_action.setShortcut("Ctrl+,")
        settings_action.triggered.connect(self._open_settings)
        file_menu.addAction(settings_action)

        file_menu.addSeparator()

        exit_action = QAction("Exit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self._safe_exit)
        file_menu.addAction(exit_action)

    def _create_central_layout(self) -> None:
        central = QWidget()
        central.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Sidebar
        self._sidebar = self._create_sidebar()
        layout.addWidget(self._sidebar)

        # Main area
        main = QWidget()
        main.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        main_layout = QVBoxLayout(main)
        main_layout.setContentsMargins(Spacing.LG, Spacing.LG, Spacing.LG, Spacing.LG)
        main_layout.setSpacing(Spacing.LG)

        # Header / control bar
        header = self._create_header()
        main_layout.addWidget(header)

        # Status card
        self._status_card = self._create_status_card()
        main_layout.addWidget(self._status_card)

        # Content stack
        self._content_card = CardWidget()
        self._content_card.content_layout().setSpacing(0)
        self._content_card.content_layout().setContentsMargins(0, 0, 0, 0)
        self.stack = QStackedWidget()

        self.dashboard = DashboardWidget()
        self.stack.addWidget(self.dashboard)

        self.logs = LogsWidget(logs_dir=Path(self.settings.logs_save_path))
        self.stack.addWidget(self.logs)

        self.webcam = WebcamWidget(on_toggle=self._toggle_webcam)
        self.stack.addWidget(self.webcam)

        self._content_card.content_layout().addWidget(self.stack)
        main_layout.addWidget(self._content_card, stretch=1)

        layout.addWidget(main, stretch=1)
        self.setCentralWidget(central)

    def _create_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setFixedWidth(180)
        sidebar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        sidebar.setStyleSheet(f"background: {Colors.SURFACE};")

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(Spacing.MD, Spacing.LG, Spacing.MD, Spacing.LG)
        layout.setSpacing(Spacing.XS)

        brand = QLabel("Flow-LoL")
        brand.setProperty("role", "title")
        brand.setStyleSheet(f"color: {Colors.PRIMARY};")
        layout.addWidget(brand)

        tagline = QLabel("Flow state companion")
        tagline.setProperty("role", "muted")
        layout.addWidget(tagline)
        layout.addSpacing(Spacing.XL)

        self._tab_buttons: list[SidebarButton] = []
        pages = [
            ("📊", "Dashboard", 0),
            ("📈", "Live ECG", 1),
            ("📹", "Webcam", 2),
        ]
        for icon, label, index in pages:
            btn = SidebarButton(icon, label)
            btn.setChecked(index == 0)
            btn.clicked.connect(lambda checked, i=index: self._set_tab(i))
            layout.addWidget(btn)
            self._tab_buttons.append(btn)

        layout.addStretch(1)

        self._settings_btn = SidebarButton("⚙️", "Settings")
        self._settings_btn.clicked.connect(self._open_settings)
        layout.addWidget(self._settings_btn)

        return sidebar

    def _create_header(self) -> QWidget:
        header = QWidget()
        header.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        layout = QHBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(Spacing.MD)

        title = QLabel("Session control")
        title.setProperty("role", "heading")
        layout.addWidget(title)

        layout.addStretch(1)

        # Session toggle
        self.session_toggle = ToggleActionButton(
            idle_text="▶  Start session",
            active_text="■  Stop session",
            idle_role="primary",
            active_role="danger",
        )
        self.session_toggle.clicked.connect(self._on_session_toggle)
        layout.addWidget(self.session_toggle)

        # Match control
        self.match_toggle = ToggleActionButton(
            idle_text="▶  Start match",
            active_text="■  End match",
            idle_role="primary",
            active_role="danger",
        )
        self.match_toggle.clicked.connect(self._on_match_toggle)
        layout.addWidget(self.match_toggle)

        self.game_mode_combo = QComboBox()
        self.game_mode_combo.addItems(GAME_MODES)
        self.game_mode_combo.setEnabled(False)
        layout.addWidget(self.game_mode_combo)

        # Webcam toggle
        self.webcam_toggle = ToggleActionButton(
            idle_text="▶  Enable webcam",
            active_text="■  Disable webcam",
            idle_role="primary",
            active_role="danger",
        )
        self.webcam_toggle.clicked.connect(self._on_webcam_toggle)
        layout.addWidget(self.webcam_toggle)

        self._update_header_controls(False)
        return header

    def _create_status_card(self) -> CardWidget:
        card = CardWidget()
        layout = card.content_layout()
        layout.setSpacing(Spacing.SM)

        self._status_label = QLabel("Ready. Press Start session to connect sensors.")
        self._status_label.setWordWrap(True)
        self._status_label.setProperty("role", "muted")
        layout.addWidget(self._status_label)

        return card

    def _create_statusbar(self) -> None:
        self.status = QStatusBar()
        self.setStatusBar(self.status)

        self.pill_sensor = StatusPill("H10: idle")
        self.pill_models = StatusPill("models: —")
        self.pill_webcam = StatusPill("webcam: off")
        self.pill_auto = StatusPill("auto-detect: on", active=self.settings.auto_detect_game)
        self.pill_match = StatusPill("match: —")

        for pill in (
            self.pill_sensor,
            self.pill_models,
            self.pill_webcam,
            self.pill_auto,
            self.pill_match,
        ):
            self.status.addWidget(pill)

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def _set_tab(self, index: int) -> None:
        for i, btn in enumerate(self._tab_buttons):
            btn.setChecked(i == index)
        self.stack.setCurrentIndex(index)

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    def _open_settings(self) -> None:
        if self.worker is not None and self.worker.isRunning():
            self._status_label.setText("Stop the session before changing settings.")
            return
        dialog = SettingsDialog(self.settings, self)
        if dialog.exec():
            self.settings = dialog.settings
            self.settings.save()
            logger.info("Settings updated")
            self.logs.set_logs_dir(Path(self.settings.logs_save_path))
            self._update_status()

    # ------------------------------------------------------------------
    # Session / match / webcam actions
    # ------------------------------------------------------------------

    def _on_session_toggle(self) -> None:
        if self.session_toggle.is_active():
            self._start_session()
        else:
            self._stop_session()

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
        self.worker.game_event.connect(self._on_game_event)
        self.worker.webcam_changed.connect(self._on_webcam_changed)
        self.worker.start()

        self._update_header_controls(True)
        self.session_toggle.set_active(True)
        self._status_label.setText("Session started. Connecting sensors...")
        logger.info("Session started")

    def _stop_session(self) -> None:
        if self.worker is not None:
            self.worker.stop()
            self.worker = None

        self._in_match = False
        self._webcam_recording = False
        self._sensor_status = "idle"
        self._update_header_controls(False)
        self.session_toggle.set_active(False)
        self.match_toggle.set_active(False)
        self.webcam_toggle.set_active(False)
        self.webcam.set_recording_state(False, None)

        self.dashboard.refresh_sessions()
        self.logs.refresh_logs()
        self.webcam.refresh_list()
        self._status_label.setText("Session stopped. Dashboard updated.")
        logger.info("Session stopped")

    def _on_match_toggle(self) -> None:
        if self.match_toggle.is_active():
            self._start_match()
        else:
            self._stop_match()

    def _start_match(self) -> None:
        if self.worker is None:
            return
        mode = self.game_mode_combo.currentText()
        self.worker.start_match(mode)

    def _stop_match(self) -> None:
        if self.worker is None:
            return
        self.worker.end_match()

    def _on_webcam_toggle(self) -> None:
        if self.worker is None:
            return
        self.worker.toggle_webcam()

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

    # ------------------------------------------------------------------
    # Worker signal handlers
    # ------------------------------------------------------------------

    def _on_webcam_changed(self, recording: bool, path: object) -> None:
        """Update UI when the worker reports a webcam state change."""
        self._webcam_recording = recording
        self.webcam_toggle.setEnabled(True)
        self.webcam_toggle.set_active(recording)
        self.webcam.set_recording_state(recording, path)
        self._update_status()
        status = "Webcam recording started" if recording else "Webcam recording stopped"
        if path:
            self._status_label.setText(f"{status}: {path}")
        else:
            self._status_label.setText(status)

    def _on_connection_changed(self, name: str, status: str) -> None:
        self._sensor_status = status.lower()
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
        self.match_toggle.set_active(True)
        self.game_mode_combo.setEnabled(False)
        source = "auto-detected" if detected else "manual"
        self._status_label.setText(f"Match started ({source}): {game_mode}")
        logger.info("Match started: %s (%s)", game_mode, source)
        self._update_status()

    def _on_match_ended(self) -> None:
        self._in_match = False
        self.match_toggle.set_active(False)
        self.game_mode_combo.setEnabled(self.worker is not None and self.worker.isRunning())
        self._status_label.setText("Match ended. Session still running.")
        logger.info("Match ended")
        self._update_status()

    def _on_game_event(self, event: object) -> None:
        etype = event.get("event_type", "event") if isinstance(event, dict) else "event"
        self._status_label.setText(f"Game event: {etype}")

    # ------------------------------------------------------------------
    # Header / status helpers
    # ------------------------------------------------------------------

    def _update_header_controls(self, session_running: bool) -> None:
        self.match_toggle.setEnabled(session_running and not self._in_match)
        self.game_mode_combo.setEnabled(session_running and not self._in_match)
        # Webcam toggle is enabled only when a sensor has connected; until then
        # the worker keeps it disabled via _on_webcam_changed.
        self.webcam_toggle.setEnabled(False)

    def _update_status(self) -> None:
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

        # Sensor pill
        if "connected" in self._sensor_status:
            self.pill_sensor.set_text("H10: connected")
            self.pill_sensor.set_active(True)
        elif "connecting" in self._sensor_status or "scan" in self._sensor_status:
            self.pill_sensor.set_text("H10: connecting")
            self.pill_sensor.set_active(False, warning=True)
        else:
            self.pill_sensor.set_text("H10: idle")
            self.pill_sensor.set_active(False)

        self.pill_models.set_text(f"models: {len(enabled_models)}/5")
        self.pill_models.set_active(bool(enabled_models))

        if self._webcam_recording:
            self.pill_webcam.set_text("webcam: recording")
            self.pill_webcam.set_active(True)
        else:
            self.pill_webcam.set_text("webcam: off")
            self.pill_webcam.set_active(False)

        self.pill_auto.set_text(f"auto-detect: {'on' if self.settings.auto_detect_game else 'off'}")
        self.pill_auto.set_active(self.settings.auto_detect_game)

        if self._in_match:
            self.pill_match.set_text("match: active")
            self.pill_match.set_active(True)
        else:
            self.pill_match.set_text("match: —")
            self.pill_match.set_active(False)
