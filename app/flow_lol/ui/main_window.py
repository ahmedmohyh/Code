"""Main application window with a modern sidebar + header layout."""

from __future__ import annotations

import logging

from pathlib import Path

from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QMenu,
    QProgressBar,
    QPushButton,
    QStackedWidget,
    QStatusBar,
    QSystemTrayIcon,
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
from flow_lol.ui.edge_status import EdgeStatusWindow
from flow_lol.ui.game_detector_thread import GameDetectorThread
from flow_lol.ui.logs_widget import LogsWidget
from flow_lol.ui.sensor_worker import SensorWorker
from flow_lol.ui.settings_dialog import SettingsDialog
from flow_lol.ui.styles import Colors, Fonts, Spacing, stylesheet
from flow_lol.ui.webcam_widget import WebcamWidget

logger = logging.getLogger(__name__)

GAME_MODES = ["Ranked Solo/Duo", "Ranked Flex", "Normal", "ARAM", "Custom", "Other"]


class WebcamCheckWorker(QThread):
    """Check webcam availability in the background so the UI does not freeze."""

    result = pyqtSignal(bool, str)

    def run(self) -> None:
        try:
            from flow_lol.webcam.recorder import WebcamRecorder

            if WebcamRecorder.is_available():
                self.result.emit(True, "")
            else:
                self.result.emit(False, "No webcam detected. Check camera connection and Windows privacy settings.")
        except Exception as exc:
            self.result.emit(False, f"Webcam check failed: {exc}")


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
        self._client_connected = False
        self._client_phase = "None"
        self._in_match = False
        self._is_shutting_down = False

        self._apply_stylesheet()
        self._create_menu()
        self._create_central_layout()
        self._create_statusbar()

        # Start the League client/game detector immediately so it works even
        # before the H10 is connected.
        self._game_detector = GameDetectorThread(self.settings, self)
        self._game_detector.match_started.connect(self._on_match_started)
        self._game_detector.match_ended.connect(self._on_match_ended)
        self._game_detector.game_event.connect(self._on_game_event)
        self._game_detector.client_state_changed.connect(self._on_game_client_changed)
        self._game_detector.start()

        # Screen-edge status indicator (thin colored bar at top of screen).
        self._edge_status = EdgeStatusWindow(self)
        self._edge_status.set_enabled(self.settings.screen_edge_status_enabled)

        # System tray icon so the app can run minimized to tray.
        self._create_tray_icon()

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

    def _create_tray_icon(self) -> None:
        """Create a system tray icon with a context menu."""
        self._tray_icon = QSystemTrayIcon(self)
        self._tray_icon.setToolTip("Flow-LoL")
        # Use a generic colored icon via QIcon fallback.
        self._tray_icon.setIcon(QIcon.fromTheme("applications-other"))

        tray_menu = QMenu(self)
        show_action = QAction("Show Flow-LoL", self)
        show_action.triggered.connect(self._restore_from_tray)
        tray_menu.addAction(show_action)

        edge_action = QAction("Screen-edge status", self)
        edge_action.setCheckable(True)
        edge_action.setChecked(self.settings.screen_edge_status_enabled)
        edge_action.triggered.connect(self._on_tray_edge_toggle)
        tray_menu.addAction(edge_action)

        tray_menu.addSeparator()

        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self._safe_exit)
        tray_menu.addAction(exit_action)

        self._tray_icon.setContextMenu(tray_menu)
        self._tray_icon.activated.connect(self._on_tray_activated)
        self._tray_icon.show()

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

        self.dashboard = DashboardWidget(
            settings=self.settings,
            webcam_dir=Path(self.settings.webcam_save_path),
        )
        self.dashboard.test_webcam_clicked.connect(self._on_dashboard_test_webcam)
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

        self._exit_btn = SidebarButton("🚪", "Close app")
        self._exit_btn.setToolTip("Safely stop all workers and exit Flow-LoL")
        self._exit_btn.clicked.connect(self._safe_exit)
        layout.addWidget(self._exit_btn)

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

        # Webcam recording LED + label
        self.webcam_status_layout = QHBoxLayout()
        self.webcam_status_layout.setSpacing(Spacing.SM)
        self.webcam_rec_led = StatusLed(color=Colors.TEXT_MUTED, size=12)
        self.webcam_rec_label = QLabel("REC")
        self.webcam_rec_label.setProperty("role", "muted")
        self.webcam_status_layout.addWidget(self.webcam_rec_led)
        self.webcam_status_layout.addWidget(self.webcam_rec_label)
        self.webcam_status_layout.setEnabled(False)

        # League client open indicator LED + label
        self.client_status_layout = QHBoxLayout()
        self.client_status_layout.setSpacing(Spacing.SM)
        self.client_led = StatusLed(color=Colors.TEXT_MUTED, size=12)
        self.client_label = QLabel("LOL")
        self.client_label.setProperty("role", "muted")
        self.client_status_layout.addWidget(self.client_led)
        self.client_status_layout.addWidget(self.client_label)
        self.client_status_layout.setEnabled(False)

        # Match / in-game indicator LED + label
        self.match_status_layout = QHBoxLayout()
        self.match_status_layout.setSpacing(Spacing.SM)
        self.match_led = StatusLed(color=Colors.TEXT_MUTED, size=12)
        self.match_label = QLabel("GAME")
        self.match_label.setProperty("role", "muted")
        self.match_status_layout.addWidget(self.match_led)
        self.match_status_layout.addWidget(self.match_label)
        self.match_status_layout.setEnabled(False)

        layout.addLayout(sensor_status_layout)
        layout.addLayout(self.webcam_status_layout)
        layout.addLayout(self.client_status_layout)
        layout.addLayout(self.match_status_layout)

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
            self._edge_status.set_enabled(self.settings.screen_edge_status_enabled)
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
            self._edge_status.set_unknown()
        else:
            self._status_label.setText("Session active. Recording ECG, predictions and webcam.")
            # If a match is already in progress when the session starts, record it retroactively.
            if self._in_match and self.worker is not None and self.worker.isRunning():
                mode = self.game_mode_combo.currentText()
                self.worker.record_match_start(mode, detected=True)
        self._update_header_controls(self.worker is not None and self.worker.isRunning())

    def _on_match_toggle(self) -> None:
        active = self.match_toggle.is_active()
        logger.info("Match toggle clicked; currently active=%s", active)
        if active:
            self._stop_match()
        else:
            self._start_match()

    def _start_match(self) -> None:
        mode = self.game_mode_combo.currentText()
        logger.info("Requesting match start: %s", mode)
        self._status_label.setText(f"Starting match ({mode})...")
        self._game_detector.start_match(mode, detected=False)

    def _stop_match(self) -> None:
        logger.info("Requesting match end")
        self._status_label.setText("Ending match...")
        self._game_detector.end_match()

    def _toggle_webcam(self) -> None:
        if self.worker is None:
            return
        self.worker.toggle_webcam()

    def _on_webcam_toggle(self) -> None:
        self._toggle_webcam()

    def _on_dashboard_test_webcam(self) -> None:
        """Handle the dashboard's test-webcam button.

        If a session is already active, the button toggles the session webcam
        on/off. Otherwise it does a quick availability check and reports the
        result without recording anything.
        """
        if self.worker is not None and self.worker.isRunning() and self._session_active:
            self._toggle_webcam()
            return

        self._status_label.setText("Checking webcam availability...")
        self.dashboard.test_webcam_btn.setEnabled(False)
        self.dashboard.test_webcam_btn.setText("📹 Checking...")

        self._webcam_check_worker = WebcamCheckWorker(self)
        self._webcam_check_worker.result.connect(self._on_webcam_check_result)
        self._webcam_check_worker.finished.connect(self._webcam_check_worker.deleteLater)
        self._webcam_check_worker.start()

    def _on_webcam_check_result(self, available: bool, message: str) -> None:
        """Update the UI after the background webcam check finishes."""
        self.dashboard.test_webcam_btn.setEnabled(True)
        self.dashboard.test_webcam_btn.setText("📹 Test webcam")
        if available:
            self._status_label.setText("Webcam is available.")
        else:
            self._status_label.setText(message)

    def _safe_exit(self) -> None:
        """Stop any running session cleanly and exit the app."""
        if self._is_shutting_down:
            return

        if self.worker is not None and self.worker.isRunning() and self._session_active:
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

        self._is_shutting_down = True
        self._do_full_shutdown()
        QApplication.instance().quit()

    def _do_full_shutdown(self) -> None:
        """Stop all background threads and clean up resources."""
        if self._tray_icon is not None:
            self._tray_icon.hide()

        if self.worker is not None:
            if self.worker.isRunning():
                self.worker.stop()
                if not self.worker.wait(5000):
                    logger.warning("Sensor worker did not stop within 5 s")
            self.worker = None

        if self._game_detector is not None:
            if self._game_detector.isRunning():
                self._game_detector.stop()
                if not self._game_detector.wait(5000):
                    logger.warning("Game detector thread did not stop within 5 s")
            self._game_detector = None

        if self._webcam_check_worker is not None and self._webcam_check_worker.isRunning():
            self._webcam_check_worker.wait(2000)
            self._webcam_check_worker = None

        self._edge_status.set_enabled(False)
        self._edge_status.hide()
        self.settings.save()

    def closeEvent(self, event: object) -> None:
        """Minimize to tray on X; full shutdown only when _safe_exit is used."""
        if self._is_shutting_down:
            self._do_full_shutdown()
            event.accept()
            return

        if self._tray_icon is not None and self._tray_icon.isVisible():
            self.hide()
            self._tray_icon.showMessage(
                "Flow-LoL",
                "App is running in the system tray. Click the tray icon to restore.",
                QSystemTrayIcon.MessageIcon.Information,
                2000,
            )
            event.ignore()
            return

        event.ignore()
        self._safe_exit()

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        """Restore the main window when the tray icon is activated."""
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            self._restore_from_tray()

    def _restore_from_tray(self) -> None:
        """Show and raise the main window from the system tray."""
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _on_tray_edge_toggle(self, checked: bool) -> None:
        """Toggle screen-edge status from the tray context menu."""
        self.settings.screen_edge_status_enabled = checked
        self.settings.save()
        self._edge_status.set_enabled(checked)

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
        self._edge_status.update_state(label)

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
        if self.worker is not None and self.worker.isRunning() and self._session_active:
            self.worker.record_match_start(game_mode, detected=detected)
        self._update_header_controls(True)
        self._update_status()

    def _on_match_ended(self) -> None:
        self._in_match = False
        self.match_toggle.set_active(False)
        self.game_mode_combo.setEnabled(self._session_active)
        self._status_label.setText("Match ended. Session still running.")
        logger.info("Match ended")
        if self.worker is not None and self.worker.isRunning() and self._session_active:
            self.worker.record_match_end()
        self._update_header_controls(True)
        self._update_status()

    def _on_game_event(self, event: object) -> None:
        etype = event.get("event_type", "event") if isinstance(event, dict) else "event"
        self._status_label.setText(f"Game event: {etype}")
        if self.worker is not None and self.worker.isRunning() and self._session_active:
            self.worker.record_game_event(event)

    def _on_game_client_changed(self, connected: bool, phase: str) -> None:
        """Update the LOL client indicator when the detector sees the client."""
        self._client_connected = connected
        self._client_phase = phase
        self._update_status()
        if connected:
            self._status_label.setText(f"League client open: {phase}")
        else:
            self._status_label.setText("League client closed.")

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

        # Dashboard test-webcam button is always usable for availability check,
        # but make it primary role when it can actually toggle during a session.
        self.dashboard.test_webcam_btn.setEnabled(True)
        if self._session_active and self._sensor_status == "connected":
            self.dashboard.test_webcam_btn.setToolTip(
                "Toggle webcam recording for the active session"
            )
        else:
            self.dashboard.test_webcam_btn.setToolTip(
                "Check if the webcam is available (no session is active)"
            )

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
            self.webcam_rec_led.set_color(Colors.DANGER)
            self.webcam_rec_label.setText("REC")
            self.webcam_rec_label.setProperty("role", "")
            self.webcam_rec_label.setStyleSheet(f"color: {Colors.DANGER}; font-weight: 700;")
            self.webcam_status_layout.setEnabled(True)
        else:
            self.pill_webcam.set_text("webcam: off")
            self.pill_webcam.set_active(False)
            self.webcam_rec_led.set_color(Colors.TEXT_MUTED)
            self.webcam_rec_label.setText("REC")
            self.webcam_rec_label.setProperty("role", "muted")
            self.webcam_rec_label.setStyleSheet("")
            self.webcam_status_layout.setEnabled(False)

        self.pill_auto.set_text(f"auto-detect: {'on' if self.settings.auto_detect_game else 'off'}")
        self.pill_auto.set_active(self.settings.auto_detect_game)

        if self._in_match:
            self.pill_match.set_text("match: active")
            self.pill_match.set_active(True)
            self.match_led.set_color(Colors.WARNING)
            self.match_label.setText("GAME")
            self.match_label.setProperty("role", "")
            self.match_label.setStyleSheet(f"color: {Colors.WARNING}; font-weight: 700;")
            self.match_status_layout.setEnabled(True)
        else:
            self.pill_match.set_text("match: —")
            self.pill_match.set_active(False)
            self.match_led.set_color(Colors.TEXT_MUTED)
            self.match_label.setText("GAME")
            self.match_label.setProperty("role", "muted")
            self.match_label.setStyleSheet("")
            self.match_status_layout.setEnabled(False)

        # League client open indicator (separate from match-in-progress).
        if self._client_connected:
            self.client_led.set_color(Colors.PRIMARY)
            self.client_label.setText("LOL")
            self.client_label.setProperty("role", "")
            self.client_label.setStyleSheet(f"color: {Colors.PRIMARY}; font-weight: 700;")
            self.client_status_layout.setEnabled(True)
        else:
            self.client_led.set_color(Colors.TEXT_MUTED)
            self.client_label.setText("LOL")
            self.client_label.setProperty("role", "muted")
            self.client_label.setStyleSheet("")
            self.client_status_layout.setEnabled(False)
