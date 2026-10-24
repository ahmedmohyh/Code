"""Main application window with a modern sidebar + header layout."""

from __future__ import annotations

import logging

from pathlib import Path

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
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
    StatusLed,
    StatusPill,
    ToggleActionButton,
)
from flow_lol.ui.dashboard import DashboardWidget
from flow_lol.ui.logs_widget import LogsWidget
from flow_lol.ui.sensor_worker import SensorWorker
from flow_lol.ui.settings_dialog import SettingsDialog
from flow_lol.ui.styles import Colors, Fonts, Spacing, stylesheet
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
        self._sensor_connected = False
        self._h10_connecting = False
        self._session_active = False

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

        self.dashboard = DashboardWidget(webcam_dir=Path(self.settings.webcam_save_path))
        self.stack.addWidget(self.dashboard)

        self.logs = LogsWidget(logs_dir=Path(self.settings.logs_save_path))
        self.stack.addWidget(self.logs)

        self.webcam = WebcamWidget(
            on_toggle=self._toggle_webcam,
            webcam_dir=Path(self.settings.webcam_save_path),
        )
        self.stack.addWidget(self.webcam)

        self._content_card.content_layout().addWidget(self.stack)
        main_layout.addWidget(self._content_card, stretch=1)

        layout.addWidget(main, stretch=1)
        self.setCentralWidget(central)

        # Keep the webcam tab in sync with the dashboard's selected session.
        self.dashboard.session_changed.connect(self.webcam.set_session_filter)
        self.webcam.set_session_filter(self.dashboard.current_session_id())

        # Header controls reference self.webcam, so update them only after it exists.
        self._update_header_controls(False)

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
        title.setStyleSheet(
            f"""
            QLabel {{
                background: {Colors.SURFACE};
                color: {Colors.PRIMARY};
                border: 1px solid {Colors.BORDER};
                border-radius: {Spacing.RADIUS_SM}px;
                padding: 4px 10px;
                font-weight: 700;
                font-size: {Fonts.SUBHEAD}pt;
            }}
            """
        )
        layout.addWidget(title)

        # Sensor status LED + label
        sensor_status_layout = QHBoxLayout()
        sensor_status_layout.setSpacing(Spacing.SM)
        self.sensor_led = StatusLed(color=Colors.DANGER, size=12)
        self.sensor_status_label = QLabel("H10: not connected")
        self.sensor_status_label.setProperty("role", "muted")
        sensor_status_layout.addWidget(self.sensor_led)
        sensor_status_layout.addWidget(self.sensor_status_label)
        layout.addLayout(sensor_status_layout)

        layout.addStretch(1)

        # Single H10 toggle button: Connect / Cancel / Disconnect.
        self.h10_toggle_btn = QPushButton("🔗  Connect H10")
        self.h10_toggle_btn.setProperty("role", "primary")
        self.h10_toggle_btn.setToolTip("Connect the Polar H10 and show live ECG")
        self.h10_toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.h10_toggle_btn.clicked.connect(self._on_h10_toggle)
        layout.addWidget(self.h10_toggle_btn)

        # Separate Start/Stop session buttons to avoid toggle-state bugs.
        self.start_session_btn = QPushButton("▶  Start session")
        self.start_session_btn.setProperty("role", "primary")
        self.start_session_btn.setToolTip("Start a recording session")
        self.start_session_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.start_session_btn.setEnabled(False)
        self.start_session_btn.setVisible(False)
        self.start_session_btn.clicked.connect(self._on_start_session)
        layout.addWidget(self.start_session_btn)

        self.stop_session_btn = QPushButton("■  Stop session")
        self.stop_session_btn.setProperty("role", "danger")
        self.stop_session_btn.setToolTip("Stop the recording session")
        self.stop_session_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.stop_session_btn.setEnabled(False)
        self.stop_session_btn.setVisible(False)
        self.stop_session_btn.clicked.connect(self._on_stop_session)
        layout.addWidget(self.stop_session_btn)

        # Match control (manual override for when auto-detect is off or fails)
        self.match_toggle = ToggleActionButton(
            idle_text="▶  Start match",
            active_text="■  End match",
            idle_role="primary",
            active_role="danger",
        )
        self.match_toggle.setToolTip(
            "Manual match control. Auto-detect is used first; this button is a fallback."
        )
        self.match_toggle.setVisible(False)
        self.match_toggle.clicked.connect(self._on_match_toggle)
        layout.addWidget(self.match_toggle)

        self.game_mode_combo = QComboBox()
        self.game_mode_combo.addItems(GAME_MODES)
        self.game_mode_combo.setEnabled(False)
        self.game_mode_combo.setVisible(False)
        self.game_mode_combo.setToolTip("Select game mode for manual match start")
        self.game_mode_combo.setCursor(Qt.CursorShape.PointingHandCursor)
        layout.addWidget(self.game_mode_combo)

        # Webcam toggle
        self.webcam_toggle = ToggleActionButton(
            idle_text="▶  Enable webcam",
            active_text="■  Disable webcam",
            idle_role="primary",
            active_role="danger",
        )
        self.webcam_toggle.setToolTip("Enable webcam recording once a session is active")
        self.webcam_toggle.setVisible(False)
        self.webcam_toggle.clicked.connect(self._on_webcam_toggle)
        layout.addWidget(self.webcam_toggle)

        return header

    def _create_status_card(self) -> CardWidget:
        card = CardWidget()
        layout = card.content_layout()
        layout.setSpacing(Spacing.SM)

        self._status_label = QLabel(
            "Ready. Press 'Connect H10' to pair the Polar H10 sensor, then start a session."
        )
        self._status_label.setWordWrap(True)
        self._status_label.setProperty("role", "muted")
        layout.addWidget(self._status_label)

        prediction_row = QHBoxLayout()
        prediction_row.setSpacing(Spacing.MD)
        prediction_row.addWidget(QLabel("Next prediction:"))
        self.prediction_progress = QProgressBar()
        self.prediction_progress.setRange(0, 100)
        self.prediction_progress.setValue(0)
        self.prediction_progress.setTextVisible(True)
        self.prediction_progress.setFormat("Not started")
        prediction_row.addWidget(self.prediction_progress, stretch=1)
        self.last_prediction_label = QLabel("Last: —")
        self.last_prediction_label.setProperty("role", "muted")
        prediction_row.addWidget(self.last_prediction_label)
        layout.addLayout(prediction_row)

        self._prediction_timer = QTimer(self)
        self._prediction_timer.timeout.connect(self._tick_prediction_progress)
        self._prediction_timer.start(100)
        self._prediction_step_seconds = self.settings.window_seconds * (100 - self.settings.overlap_percent) / 100.0
        self._last_prediction_time: Optional[float] = None

        return card

    def _create_statusbar(self) -> None:
        self.status = QStatusBar()
        self.setStatusBar(self.status)

        self.pill_sensor = StatusPill("H10: idle")
        self.pill_flow = StatusPill("flow: —")
        self.pill_models = StatusPill("models: —")
        self.pill_webcam = StatusPill("webcam: off")
        self.pill_auto = StatusPill("auto-detect: on", active=self.settings.auto_detect_game)
        self.pill_match = StatusPill("match: —")

        for pill in (
            self.pill_sensor,
            self.pill_flow,
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
        if self._session_active:
            self._status_label.setText("Stop the recording session before changing settings.")
            return
        dialog = SettingsDialog(self.settings, self)
        if dialog.exec():
            self.settings = dialog.settings
            self.settings.save()
            logger.info("Settings updated")
            self.logs.set_logs_dir(Path(self.settings.logs_save_path))
            self.webcam.webcam_dir = Path(self.settings.webcam_save_path)
            self.webcam.refresh_list()
            self.dashboard.webcam_dir = Path(self.settings.webcam_save_path)
            self._prediction_step_seconds = (
                self.settings.window_seconds * (100 - self.settings.overlap_percent) / 100.0
            )
            self._update_status()

    # ------------------------------------------------------------------
    # Session / match / webcam actions
    # ------------------------------------------------------------------

    def _on_h10_toggle(self) -> None:
        """Toggle H10 connect / cancel / disconnect from a single button.

        State machine:
          - disconnected : button = "Connect H10"   -> start worker
          - connecting   : button = "Cancel"      -> stop worker
          - connected    : button = "Disconnect"  -> stop worker
        """
        if self._h10_connecting:
            self._disconnect_h10("Connection cancelled.")
            logger.info("User cancelled H10 connection")
            return

        if self._sensor_connected:
            self._disconnect_h10("H10 disconnected.")
            logger.info("User disconnected H10")
            return

        self._start_h10_connection()

    def _start_h10_connection(self) -> None:
        if self.worker is not None and self.worker.isRunning():
            return
        self._h10_connecting = True
        self._update_h10_toggle_ui()
        self._status_label.setText("Searching for Polar H10...")
        self._sensor_status = "connecting"
        self._update_status()

        self.worker = SensorWorker(self.settings, parent=self)
        self.worker.connection_changed.connect(self._on_connection_changed)
        self.worker.prediction.connect(self._on_prediction)
        self.worker.samples.connect(self._on_samples)
        self.worker.error.connect(self._on_error)
        self.worker.match_started.connect(self._on_match_started)
        self.worker.match_ended.connect(self._on_match_ended)
        self.worker.game_event.connect(self._on_game_event)
        self.worker.webcam_changed.connect(self._on_webcam_changed)
        self.worker.webcam_snapshot.connect(self._on_webcam_snapshot)
        self.worker.session_state_changed.connect(self._on_session_state_changed)
        self.worker.finished.connect(self._on_worker_finished)
        self.worker.start()

    def _disconnect_h10(self, message: str = "H10 disconnected.") -> None:
        if self._session_active:
            self._on_stop_session()
        if self.worker is not None:
            self.worker.stop()
            self.worker = None
        self._sensor_connected = False
        self._h10_connecting = False
        self._sensor_status = "idle"
        self._update_h10_toggle_ui()
        self._update_header_controls(False)
        self._update_status()
        self._status_label.setText(message)

    def _on_worker_finished(self) -> None:
        """Clean up when the H10 worker thread exits for any reason."""
        if self.worker is not None:
            self.worker = None
        self._sensor_connected = False
        self._h10_connecting = False
        self._sensor_status = "idle"
        self._update_h10_toggle_ui()
        self._update_header_controls(False)
        self._update_status()

    def _update_h10_toggle_ui(self) -> None:
        if self._h10_connecting:
            self.h10_toggle_btn.setText("✕  Cancel connection")
            self.h10_toggle_btn.setProperty("role", "danger")
            self.h10_toggle_btn.setToolTip("Stop trying to connect the H10")
        elif self._sensor_connected:
            self.h10_toggle_btn.setText("✕  Disconnect H10")
            self.h10_toggle_btn.setProperty("role", "danger")
            self.h10_toggle_btn.setToolTip("Disconnect the Polar H10")
        else:
            self.h10_toggle_btn.setText("🔗  Connect H10")
            self.h10_toggle_btn.setProperty("role", "primary")
            self.h10_toggle_btn.setToolTip("Connect the Polar H10 and show live ECG")
        self.h10_toggle_btn.style().unpolish(self.h10_toggle_btn)
        self.h10_toggle_btn.style().polish(self.h10_toggle_btn)
        self.h10_toggle_btn.update()

    def _on_start_session(self) -> None:
        if self.worker is None or not self.worker.isRunning():
            self._status_label.setText("Connect the Polar H10 sensor before starting a session.")
            return
        if not self._sensor_connected:
            self._status_label.setText("H10 is still connecting. Wait for the green LED.")
            return
        self._prediction_count = 0
        self._in_match = False
        self.worker.start_session()
        self._status_label.setText("Session started. Recording ECG, predictions and webcam...")
        logger.info("User started recording session")

    def _on_stop_session(self) -> None:
        if self.worker is not None and self.worker.isRunning():
            self.worker.stop_session()
        self._status_label.setText("Stopping session...")
        logger.info("User stopped recording session")

    def _on_session_state_changed(self, active: bool) -> None:
        self._session_active = active
        if not active:
            self._in_match = False
            self._webcam_recording = False
            self.match_toggle.set_active(False)
            self.webcam_toggle.set_active(False)
            self.webcam.set_recording_state(False, None)
            self.game_mode_combo.setEnabled(False)
            self.dashboard.refresh_sessions()
            self.logs.refresh_logs()
            self.webcam.refresh_list()
            self._status_label.setText("Session stopped. H10 preview still active.")
        else:
            self._status_label.setText("Session active. Recording ECG, predictions and webcam.")
        self._update_header_controls(self.worker is not None and self.worker.isRunning())

    def _on_match_toggle(self) -> None:
        active = self.match_toggle.is_active()
        logger.info("Match toggle clicked; currently active=%s", active)
        if active:
            self._stop_match()
        else:
            self._start_match()

    def _start_match(self) -> None:
        if self.worker is None:
            logger.warning("Cannot start match: no worker")
            self._status_label.setText("Connect the H10 and start a session before starting a match.")
            return
        if not self.worker.isRunning():
            logger.warning("Cannot start match: worker not running")
            self._status_label.setText("Worker not running. Reconnect the H10.")
            return
        mode = self.game_mode_combo.currentText()
        logger.info("Requesting match start: %s", mode)
        self._status_label.setText(f"Starting match ({mode})...")
        self.worker.start_match(mode)

    def _stop_match(self) -> None:
        if self.worker is None:
            logger.warning("Cannot stop match: no worker")
            return
        logger.info("Requesting match end")
        self._status_label.setText("Ending match...")
        self.worker.end_match()

    def _toggle_webcam(self) -> None:
        if self.worker is None:
            return
        self.worker.toggle_webcam()

    def _on_webcam_toggle(self) -> None:
        self._toggle_webcam()

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
            self._on_stop_session()
        if self.worker is not None:
            self.worker.stop()
            self.worker = None
        self.settings.save()
        self.close()

    def closeEvent(self, event: object) -> None:
        """Intercept window close to ensure clean shutdown."""
        if self.worker is not None:
            self.worker.stop()
            self.worker = None
        self.settings.save()
        event.accept()

    # ------------------------------------------------------------------
    # Worker signal handlers
    # ------------------------------------------------------------------

    def _on_webcam_changed(self, recording: bool, path: object) -> None:
        """Update UI when the worker reports a webcam state change."""
        self._webcam_recording = recording
        # Webcam toggle becomes available as soon as the worker reports state,
        # which happens after a sensor connects.
        if self.worker is not None and self.worker.isRunning():
            self._update_header_controls(True)
        self.webcam_toggle.set_active(recording)
        self.webcam.set_recording_state(recording, path)
        self._update_status()
        status = "Webcam recording started" if recording else "Webcam recording stopped"
        if path:
            self._status_label.setText(f"{status}: {path}")
        else:
            self._status_label.setText(status)

    def _on_webcam_snapshot(self, path: object) -> None:
        """Notify the webcam tab when a new snapshot is saved."""
        self.webcam.add_snapshot(path)

    def _on_connection_changed(self, name: str, status: str) -> None:
        self._sensor_status = status.lower()
        if self._sensor_status == "connected":
            self._sensor_connected = True
            self._h10_connecting = False
            self._update_h10_toggle_ui()
            self._status_label.setText("H10 connected. Switch to Logs tab to see live ECG. Press Start session to record.")
        elif self._sensor_status == "disconnected":
            self._sensor_connected = False
            self._h10_connecting = False
            self._status_label.setText("H10 disconnected.")
            self._update_h10_toggle_ui()
        else:
            self._status_label.setText(f"[{name}] {status}")
        if self.worker is not None and self.worker.isRunning():
            self._update_header_controls(True)
        self._update_status()

    def _on_prediction(self, name: str, prediction: object) -> None:
        import time

        self._prediction_count += 1
        self._last_prediction_time = time.time()
        pred = prediction
        label = pred.get("ensemble_label", 0)
        label_name = "flow" if label == 1 else "no-flow"
        self._status_label.setText(
            f"[{name}] prediction #{self._prediction_count}: {label_name} "
            f"({pred.get('n_for_majority')}/{pred.get('n_votes')} votes)"
        )
        self.pill_flow.set_text(f"flow: {label_name}")
        self.pill_flow.set_active(label == 1)
        self.last_prediction_label.setText(f"Last: {label_name}")
        self.last_prediction_label.setProperty("role", "")
        self.last_prediction_label.setStyleSheet(
            f"color: {Colors.FLOW if label == 1 else Colors.NO_FLOW}; font-weight: 600;"
        )
        self.prediction_progress.setValue(0)
        self.prediction_progress.setFormat("0 s")

    def _tick_prediction_progress(self) -> None:
        import time

        if self._last_prediction_time is None:
            self.prediction_progress.setValue(0)
            self.prediction_progress.setFormat("Not started")
            return

        elapsed = time.time() - self._last_prediction_time
        step = self._prediction_step_seconds
        if step <= 0:
            step = self.settings.window_seconds or 60
        pct = min(100, int(100 * elapsed / step))
        remaining = max(0, step - elapsed)
        self.prediction_progress.setValue(pct)
        self.prediction_progress.setFormat(f"{remaining:.1f} s")

    def _on_error(self, name: str, exc: object) -> None:
        self._status_label.setText(f"[{name}] error: {exc}")
        logger.error("[%s] worker error: %s", name, exc)
        if name == "webcam" and self.worker is not None:
            self.webcam.show_error(str(exc))
        if name == "webcam" and self.worker is not None:
            self.webcam.show_error(str(exc))

    def _on_samples(self, name: str, samples: object) -> None:
        self.logs.add_samples(name, samples)

    def _on_match_started(self, game_mode: str, detected: bool) -> None:
        self._in_match = True
        self.match_toggle.set_active(True)
        self.game_mode_combo.setEnabled(False)
        source = "auto-detected" if detected else "manual"
        self._status_label.setText(f"Match started ({source}): {game_mode}")
        logger.info("Match started: %s (%s)", game_mode, source)
        self._update_header_controls(True)
        self._update_status()

    def _on_match_ended(self) -> None:
        self._in_match = False
        self.match_toggle.set_active(False)
        self.game_mode_combo.setEnabled(self._session_active)
        self._status_label.setText("Match ended. Session still running.")
        logger.info("Match ended")
        self._update_header_controls(True)
        self._update_status()

    def _on_game_event(self, event: object) -> None:
        etype = event.get("event_type", "event") if isinstance(event, dict) else "event"
        self._status_label.setText(f"Game event: {etype}")

    # ------------------------------------------------------------------
    # Header / status helpers
    # ------------------------------------------------------------------

    def _update_header_controls(self, worker_running: bool) -> None:
        # H10 toggle is always visible and enabled so the user can connect, cancel,
        # or disconnect at any time.
        self.h10_toggle_btn.setEnabled(True)

        # Start/Stop session: only show the one that is relevant right now.
        can_start = self._sensor_connected and not self._session_active
        self.start_session_btn.setEnabled(can_start)
        self.start_session_btn.setVisible(can_start)
        self.stop_session_btn.setEnabled(self._session_active)
        self.stop_session_btn.setVisible(self._session_active)

        # Match control only appears once a session is running.
        self.match_toggle.setVisible(self._session_active)
        self.match_toggle.setEnabled(self._session_active)
        self.match_toggle.setToolTip(
            "Start or end a match manually"
            if self._session_active
            else "Available once a session is running"
        )

        # Game-mode selector only needed before manually starting a match.
        show_game_mode = self._session_active and not self._in_match
        self.game_mode_combo.setVisible(show_game_mode)
        self.game_mode_combo.setEnabled(show_game_mode)

        # Webcam toggle only appears once a session is running.
        webcam_available = self._session_active and self._sensor_status == "connected"
        self.webcam_toggle.setVisible(self._session_active)
        self.webcam_toggle.setEnabled(webcam_available)
        webcam_tooltip = (
            "Toggle webcam recording"
            if webcam_available
            else "Available once a session is running and the sensor is connected"
        )
        self.webcam_toggle.setToolTip(webcam_tooltip)
        self.webcam.set_toggle_enabled(webcam_available, webcam_tooltip)

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

        # Sensor LED + label + pill
        if "connected" in self._sensor_status:
            self.sensor_led.set_color(Colors.SUCCESS)
            self.sensor_status_label.setText("H10: connected")
            self.sensor_status_label.setProperty("role", "")
            self.pill_sensor.set_text("H10: connected")
            self.pill_sensor.set_active(True)
        elif "connecting" in self._sensor_status or "scan" in self._sensor_status:
            self.sensor_led.set_color(Colors.WARNING)
            self.sensor_status_label.setText("H10: connecting...")
            self.sensor_status_label.setProperty("role", "muted")
            self.pill_sensor.set_text("H10: connecting")
            self.pill_sensor.set_active(False, warning=True)
        else:
            self.sensor_led.set_color(Colors.DANGER)
            self.sensor_status_label.setText("H10: not connected")
            self.sensor_status_label.setProperty("role", "muted")
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
