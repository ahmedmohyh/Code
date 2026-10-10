"""Post-game dashboard: session list, match list, and flow timeline."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from flow_lol.persistence.repository import SessionRepository

logger = logging.getLogger(__name__)


class FlowTimelineWidget(QWidget):
    """Simple painter-based timeline of flow (green) vs no-flow (grey) windows."""

    BAR_WIDTH = 4
    PADDING_LEFT = 40
    PADDING_RIGHT = 10
    PADDING_TOP = 20
    PADDING_BOTTOM = 30

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.predictions: List[Dict[str, Any]] = []
        self.matches: List[Dict[str, Any]] = []
        self.setMinimumHeight(140)
        self.setBackgroundRole(self.backgroundRole())

    def set_data(
        self,
        predictions: List[Dict[str, Any]],
        matches: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        self.predictions = predictions
        self.matches = matches or []
        self.update()

    def paintEvent(self, event: object) -> None:
        painter = QPainter(self)
        try:
            self._draw(painter)
        finally:
            painter.end()

    def _draw(self, painter: QPainter) -> None:
        width = self.width()
        height = self.height()
        if width <= 0 or height <= 0:
            return

        plot_w = width - self.PADDING_LEFT - self.PADDING_RIGHT
        plot_h = height - self.PADDING_TOP - self.PADDING_BOTTOM

        # Background
        painter.fillRect(0, 0, width, height, QColor(255, 255, 255))

        if not self.predictions:
            painter.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                "No predictions for this session yet.",
            )
            return

        times = [p["timestamp"] for p in self.predictions]
        t_min, t_max = min(times), max(times)
        if t_max == t_min:
            t_max = t_min + 1.0

        def _x(t: float) -> float:
            return self.PADDING_LEFT + (t - t_min) / (t_max - t_min) * plot_w

        # Match background regions
        for match in self.matches:
            start = match.get("started_at")
            end = match.get("ended_at") or t_max
            if start is None:
                continue
            x1 = _x(start)
            x2 = _x(end)
            painter.fillRect(
                int(x1),
                self.PADDING_TOP,
                max(1, int(x2 - x1)),
                plot_h,
                QColor(230, 245, 255),
            )
            painter.setPen(QPen(QColor(180, 210, 230), 1))
            painter.drawLine(int(x1), self.PADDING_TOP, int(x1), self.PADDING_TOP + plot_h)
            painter.drawLine(int(x2), self.PADDING_TOP, int(x2), self.PADDING_TOP + plot_h)

        # Prediction bars
        for pred in self.predictions:
            x = _x(pred["timestamp"])
            label = pred.get("ensemble_label", 0)
            color = QColor(80, 180, 80) if label == 1 else QColor(160, 160, 160)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            painter.drawRect(
                int(x - self.BAR_WIDTH / 2),
                self.PADDING_TOP,
                self.BAR_WIDTH,
                plot_h,
            )

        # Axis line
        painter.setPen(QPen(QColor(0, 0, 0), 1))
        y_axis = self.PADDING_TOP + plot_h
        painter.drawLine(self.PADDING_LEFT, y_axis, width - self.PADDING_RIGHT, y_axis)

        # Time labels
        painter.setPen(QColor(0, 0, 0))
        for label_t in [t_min, (t_min + t_max) / 2, t_max]:
            txt = datetime.fromtimestamp(label_t).strftime("%H:%M:%S")
            x = _x(label_t)
            painter.drawText(int(x - 25), y_axis + 20, 50, 20, Qt.AlignmentFlag.AlignCenter, txt)


class DashboardWidget(QWidget):
    """Post-game dashboard for reviewing sessions, matches, and flow predictions."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.repo = SessionRepository()
        self._sessions: List[Dict[str, Any]] = []

        self._build_ui()
        self.refresh_sessions()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Header
        header = QHBoxLayout()
        header.addWidget(QLabel("Session:"))
        self.session_combo = QComboBox()
        self.session_combo.currentIndexChanged.connect(self._on_session_changed)
        header.addWidget(self.session_combo, stretch=1)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh_sessions)
        header.addWidget(refresh_btn)

        clear_all_btn = QPushButton("Clear all sessions")
        clear_all_btn.setStyleSheet("QPushButton { background-color: #f44336; color: white; }")
        clear_all_btn.clicked.connect(self._clear_all_sessions)
        header.addWidget(clear_all_btn)
        layout.addLayout(header)

        # Splitter: timeline + details
        splitter = QSplitter(Qt.Orientation.Horizontal)

        timeline_box = QGroupBox("Flow timeline")
        tl_layout = QVBoxLayout(timeline_box)
        self.timeline = FlowTimelineWidget()
        tl_layout.addWidget(self.timeline)
        splitter.addWidget(timeline_box)

        details_box = QGroupBox("Session details")
        details_layout = QVBoxLayout(details_box)
        self.details_label = QLabel("Select a session to see details.")
        self.details_label.setWordWrap(True)
        details_layout.addWidget(self.details_label)

        details_layout.addWidget(QLabel("Matches:"))
        self.match_list = QListWidget()
        details_layout.addWidget(self.match_list)

        self.mark_finished_btn = QPushButton("Mark selected session as finished")
        self.mark_finished_btn.setEnabled(False)
        self.mark_finished_btn.clicked.connect(self._mark_selected_finished)
        details_layout.addWidget(self.mark_finished_btn)

        self.delete_btn = QPushButton("Delete selected session data")
        self.delete_btn.setEnabled(False)
        self.delete_btn.setStyleSheet("QPushButton { background-color: #f44336; color: white; }")
        self.delete_btn.clicked.connect(self._delete_selected_session)
        details_layout.addWidget(self.delete_btn)

        splitter.addWidget(details_box)
        splitter.setSizes([600, 300])
        layout.addWidget(splitter, stretch=1)

    def refresh_sessions(self) -> None:
        self._sessions = self.repo.get_sessions(limit=50)
        self.session_combo.clear()
        if not self._sessions:
            self.session_combo.addItem("No sessions recorded")
            self.session_combo.setEnabled(False)
            self._show_session(None)
            return
        self.session_combo.setEnabled(True)
        for s in self._sessions:
            started = datetime.fromtimestamp(s["started_at"]).strftime("%Y-%m-%d %H:%M")
            ended = " (running)" if s["ended_at"] is None else ""
            text = f"{started} – session {s['id']}{ended}"
            self.session_combo.addItem(text)
        self._on_session_changed(0)

    def _on_session_changed(self, index: int) -> None:
        if index < 0 or not self._sessions:
            self._show_session(None)
            return
        session = self._sessions[index]
        self._show_session(session)

    def _show_session(self, session: Optional[Dict[str, Any]]) -> None:
        self.delete_btn.setEnabled(session is not None)
        self.mark_finished_btn.setEnabled(
            session is not None and session.get("ended_at") is None
        )
        if session is None:
            self.details_label.setText("No session selected.")
            self.match_list.clear()
            self.timeline.set_data([])
            return

        session_id = session["id"]
        predictions = self.repo.get_predictions(session_id)
        matches = self.repo.get_matches(session_id)
        events = self.repo.get_sensor_events(session_id)

        # Match list
        self.match_list.clear()
        for m in matches:
            start = datetime.fromtimestamp(m["started_at"]).strftime("%H:%M:%S")
            end = "running" if m["ended_at"] is None else datetime.fromtimestamp(m["ended_at"]).strftime("%H:%M:%S")
            detected = "auto" if m["detected"] else "manual"
            self.match_list.addItem(f"{m['game_mode']} – {start} → {end} ({detected})")
        if not matches:
            self.match_list.addItem("No matches recorded")

        # Stats
        n_preds = len(predictions)
        n_flow = sum(1 for p in predictions if p.get("ensemble_label") == 1)
        flow_pct = (n_flow / n_preds * 100) if n_preds else 0
        duration = "running" if session["ended_at"] is None else f"{session['ended_at'] - session['started_at']:.0f} s"
        sensor_summary = session.get("sensor_summary") or "unknown"

        self.details_label.setText(
            f"Session {session_id}\n"
            f"Started: {datetime.fromtimestamp(session['started_at'])}\n"
            f"Duration: {duration}\n"
            f"Sensors: {sensor_summary}\n"
            f"Predictions: {n_preds}\n"
            f"Flow windows: {n_flow} ({flow_pct:.1f}%)\n"
            f"Sensor events: {len(events)}"
        )

        self.timeline.set_data(predictions, matches)

    def _mark_selected_finished(self) -> None:
        index = self.session_combo.currentIndex()
        if index < 0 or not self._sessions:
            return
        session = self._sessions[index]
        session_id = session["id"]
        if session.get("ended_at") is not None:
            return
        self.repo.end_session(session_id)
        logger.info("Manually marked session %s as finished", session_id)
        self.refresh_sessions()

    def _delete_selected_session(self) -> None:
        index = self.session_combo.currentIndex()
        if index < 0 or not self._sessions:
            return
        session = self._sessions[index]
        session_id = session["id"]
        reply = QMessageBox.question(
            self,
            "Delete session data",
            f"Delete session {session_id} from the local database?\n"
            "This does not delete ECG CSV files or webcam MP4s.",
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.repo.delete_session(session_id)
            logger.info("Deleted session %s", session_id)
            self.refresh_sessions()

    def _clear_all_sessions(self) -> None:
        if not self._sessions:
            QMessageBox.information(self, "Clear all sessions", "There are no sessions to delete.")
            return
        reply = QMessageBox.question(
            self,
            "Clear all sessions",
            f"Delete all {len(self._sessions)} session(s) from the local database?\n"
            "This cannot be undone and does not delete ECG CSV files or webcam MP4s.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        n_deleted = self.repo.delete_all_sessions()
        logger.info("Cleared all sessions from database (%s deleted)", n_deleted)
        self.refresh_sessions()
