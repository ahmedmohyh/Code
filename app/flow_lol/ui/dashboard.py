"""Post-game dashboard with a modern card-based layout."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import os

from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtGui import QColor, QPainter, QPen, QPolygon
from PyQt6.QtWidgets import (
    QComboBox,
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

from flow_lol.ui.components import CardWidget, CompactActionBar
from flow_lol.ui.styles import Colors, Spacing
from flow_lol.persistence.repository import SessionRepository

logger = logging.getLogger(__name__)


class FlowTimelineWidget(QWidget):
    """Painter-based timeline of flow (green) vs no-flow (grey) windows."""

    BAR_WIDTH = 5
    PADDING_LEFT = 50
    PADDING_RIGHT = 16
    PADDING_TOP = 24
    PADDING_BOTTOM = 36

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.predictions: List[Dict[str, Any]] = []
        self.matches: List[Dict[str, Any]] = []
        self.game_events: List[Dict[str, Any]] = []
        self.setMinimumHeight(180)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

    def set_data(
        self,
        predictions: List[Dict[str, Any]],
        matches: Optional[List[Dict[str, Any]]] = None,
        game_events: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        self.predictions = predictions
        self.matches = matches or []
        self.game_events = game_events or []
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
        painter.fillRect(0, 0, width, height, QColor(Colors.SURFACE))

        # Grid lines (subtle)
        painter.setPen(QPen(QColor(Colors.BORDER), 1, Qt.PenStyle.DotLine))
        for i in range(1, 5):
            y = self.PADDING_TOP + int(plot_h * i / 5)
            painter.drawLine(self.PADDING_LEFT, y, width - self.PADDING_RIGHT, y)

        if not self.predictions:
            painter.setPen(QColor(Colors.TEXT_SECONDARY))
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
                QColor(Colors.MATCH_REGION),
            )
            painter.setPen(QPen(QColor(180, 210, 230), 1))
            painter.drawLine(int(x1), self.PADDING_TOP, int(x1), self.PADDING_TOP + plot_h)
            painter.drawLine(int(x2), self.PADDING_TOP, int(x2), self.PADDING_TOP + plot_h)

        # Prediction bars
        for pred in self.predictions:
            x = _x(pred["timestamp"])
            label = pred.get("ensemble_label", 0)
            color = QColor(Colors.FLOW) if label == 1 else QColor(Colors.NO_FLOW)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            painter.drawRect(
                int(x - self.BAR_WIDTH / 2),
                self.PADDING_TOP,
                self.BAR_WIDTH,
                plot_h,
            )

        # Game event markers (triangles)
        event_colors = {
            "kill": QColor(Colors.SUCCESS),
            "death": QColor(Colors.DANGER),
            "objective": QColor(Colors.PRIMARY),
        }
        painter.setPen(Qt.PenStyle.NoPen)
        for event in self.game_events:
            t = event.get("timestamp")
            if t is None:
                continue
            x = _x(t)
            etype = event.get("event_type", "")
            color = event_colors.get(etype, QColor(Colors.WARNING))
            painter.setBrush(color)
            # Draw a small upward triangle above the axis.
            polygon = QPolygon([
                QPoint(int(x), y_axis - 8),
                QPoint(int(x - 5), y_axis - 1),
                QPoint(int(x + 5), y_axis - 1),
            ])
            painter.drawPolygon(polygon)

        # Axis line
        painter.setPen(QPen(QColor(Colors.TEXT_MUTED), 1))
        y_axis = self.PADDING_TOP + plot_h
        painter.drawLine(self.PADDING_LEFT, y_axis, width - self.PADDING_RIGHT, y_axis)

        # Time labels
        painter.setPen(QColor(Colors.TEXT_SECONDARY))
        for label_t in [t_min, (t_min + t_max) / 2, t_max]:
            txt = datetime.fromtimestamp(label_t).strftime("%H:%M:%S")
            x = _x(label_t)
            painter.drawText(int(x - 30), y_axis + 20, 60, 20, Qt.AlignmentFlag.AlignCenter, txt)


class DashboardWidget(QWidget):
    """Post-game dashboard for reviewing sessions, matches, and flow predictions."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.repo = SessionRepository()
        self._sessions: List[Dict[str, Any]] = []
        self._match_rows: List[Dict[str, Any]] = []
        self._replay_rows: List[Dict[str, Any]] = []
        self._current_session_id: Optional[int] = None

        self._build_ui()
        self.refresh_sessions()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(Spacing.MD)

        # Header card
        header_card = CardWidget("Sessions")
        header_layout = header_card.content_layout()

        top_row = QHBoxLayout()
        top_row.setSpacing(Spacing.MD)

        top_row.addWidget(QLabel("Selected session:"))
        self.session_combo = QComboBox()
        self.session_combo.setMinimumWidth(260)
        self.session_combo.currentIndexChanged.connect(self._on_session_changed)
        top_row.addWidget(self.session_combo, stretch=1)

        actions = CompactActionBar()
        self.refresh_btn = actions.add_button("🔄 Refresh")
        self.refresh_btn.clicked.connect(self.refresh_sessions)

        self.mark_finished_btn = actions.add_button("✓ Mark finished")
        self.mark_finished_btn.setEnabled(False)
        self.mark_finished_btn.clicked.connect(self._mark_selected_finished)

        self.delete_btn = actions.add_button("🗑 Delete")
        self.delete_btn.setProperty("role", "danger")
        self.delete_btn.setEnabled(False)
        self.delete_btn.clicked.connect(self._delete_selected_session)

        self.clear_all_btn = actions.add_button("Clear all")
        self.clear_all_btn.setProperty("role", "danger")
        self.clear_all_btn.clicked.connect(self._clear_all_sessions)

        actions.add_stretch()
        top_row.addWidget(actions)
        header_layout.addLayout(top_row)
        layout.addWidget(header_card)

        # Content splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Timeline card
        timeline_card = CardWidget("Flow timeline")
        self.timeline = FlowTimelineWidget()
        timeline_card.content_layout().addWidget(self.timeline)
        splitter.addWidget(timeline_card)

        # Details card
        details_card = CardWidget("Session details")
        details_layout = details_card.content_layout()

        self.details_label = QLabel("Select a session to see details.")
        self.details_label.setWordWrap(True)
        self.details_label.setProperty("role", "muted")
        details_layout.addWidget(self.details_label)

        details_layout.addWidget(QLabel("Matches"))
        self.match_list = QListWidget()
        self.match_list.setAlternatingRowColors(True)
        self.match_list.currentItemChanged.connect(self._on_match_selected)
        details_layout.addWidget(self.match_list)

        details_layout.addWidget(QLabel("Game events"))
        self.event_list = QListWidget()
        self.event_list.setAlternatingRowColors(True)
        details_layout.addWidget(self.event_list)

        details_layout.addWidget(QLabel("Replays"))
        self.replay_list = QListWidget()
        self.replay_list.setAlternatingRowColors(True)
        details_layout.addWidget(self.replay_list)

        self.open_replay_btn = QPushButton("▶ Open selected replay")
        self.open_replay_btn.clicked.connect(self._open_selected_replay)
        self.open_replay_btn.setEnabled(False)
        details_layout.addWidget(self.open_replay_btn)

        splitter.addWidget(details_card)
        splitter.setSizes([650, 320])
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
            self.details_label.setProperty("role", "muted")
            self.match_list.clear()
            self.timeline.set_data([])
            return

        session_id = session["id"]
        self._current_session_id = session_id
        predictions = self.repo.get_predictions(session_id)
        matches = self.repo.get_matches(session_id)
        events = self.repo.get_sensor_events(session_id)
        game_events = self.repo.get_game_events(session_id)
        replays = self.repo.get_replays(session_id)

        # Match list
        self.match_list.clear()
        self._match_rows: List[Dict[str, Any]] = matches
        for m in matches:
            start = datetime.fromtimestamp(m["started_at"]).strftime("%H:%M:%S")
            end = "running" if m["ended_at"] is None else datetime.fromtimestamp(m["ended_at"]).strftime("%H:%M:%S")
            detected = "auto" if m["detected"] else "manual"
            rec = ""
            if m.get("notes"):
                rec = f" | {m['notes']}"
            item_text = f"{m['game_mode']} – {start} → {end} ({detected}){rec}"
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, m["id"])
            self.match_list.addItem(item)
        if not matches:
            self.match_list.addItem("No matches recorded")

        # Global event / replay summaries
        self.event_list.clear()
        for e in game_events:
            t = datetime.fromtimestamp(e["timestamp"]).strftime("%H:%M:%S")
            actor = e.get("actor") or "?"
            target = e.get("target") or ""
            desc = f"{t} – {e['event_type']}"
            if target:
                desc += f": {actor} → {target}"
            else:
                desc += f": {actor}"
            self.event_list.addItem(desc)
        if not game_events:
            self.event_list.addItem("No game events recorded")

        self.replay_list.clear()
        self._replay_rows: List[Dict[str, Any]] = replays
        for r in replays:
            if r.get("recorded_at"):
                t = datetime.fromtimestamp(r["recorded_at"]).strftime("%Y-%m-%d %H:%M")
                text = f"{r['file_name']} ({t})"
            else:
                text = r["file_name"]
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, r["file_path"])
            self.replay_list.addItem(item)
        self.open_replay_btn.setEnabled(bool(replays))
        if not replays:
            self.replay_list.addItem("No replays linked")

        # Stats
        n_preds = len(predictions)
        n_flow = sum(1 for p in predictions if p.get("ensemble_label") == 1)
        flow_pct = (n_flow / n_preds * 100) if n_preds else 0
        duration = "running" if session["ended_at"] is None else f"{session['ended_at'] - session['started_at']:.0f} s"
        sensor_summary = session.get("sensor_summary") or "unknown"

        self.details_label.setProperty("role", "")
        self.details_label.setText(
            f"<b>Session {session_id}</b><br>"
            f"Started: {datetime.fromtimestamp(session['started_at'])}<br>"
            f"Duration: {duration}<br>"
            f"Sensors: {sensor_summary}<br>"
            f"Predictions: {n_preds}<br>"
            f"Flow windows: {n_flow} ({flow_pct:.1f}%)<br>"
            f"Sensor events: {len(events)} | Game events: {len(game_events)} | Replays: {len(replays)}"
        )

        self.timeline.set_data(predictions, matches, game_events)

    def _on_match_selected(
        self,
        current: QListWidgetItem | None,
        previous: QListWidgetItem | None,
    ) -> None:
        if current is None or self._current_session_id is None:
            return
        match_id = current.data(Qt.ItemDataRole.UserRole)
        if not isinstance(match_id, int):
            return
        # Refresh event and replay lists for this match.
        events = self.repo.get_game_events(self._current_session_id, match_id=match_id)
        self.event_list.clear()
        for e in events:
            t = datetime.fromtimestamp(e["timestamp"]).strftime("%H:%M:%S")
            actor = e.get("actor") or "?"
            target = e.get("target") or ""
            desc = f"{t} – {e['event_type']}"
            if target:
                desc += f": {actor} → {target}"
            else:
                desc += f": {actor}"
            self.event_list.addItem(desc)
        if not events:
            self.event_list.addItem("No game events recorded for this match")

        replays = self.repo.get_replays(self._current_session_id, match_id=match_id)
        self.replay_list.clear()
        self._replay_rows = replays
        for r in replays:
            if r.get("recorded_at"):
                t = datetime.fromtimestamp(r["recorded_at"]).strftime("%Y-%m-%d %H:%M")
                text = f"{r['file_name']} ({t})"
            else:
                text = r["file_name"]
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, r["file_path"])
            self.replay_list.addItem(item)
        self.open_replay_btn.setEnabled(bool(replays))
        if not replays:
            self.replay_list.addItem("No replays linked to this match")

    def _open_selected_replay(self) -> None:
        item = self.replay_list.currentItem()
        if item is None:
            return
        path = item.data(Qt.ItemDataRole.UserRole)
        if not path or not isinstance(path, str):
            return
        try:
            os.startfile(path)
            logger.info("Opened replay %s", path)
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Could not open replay:\n{exc}")
            logger.error("Failed to open replay %s: %s", path, exc)

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
            f"Delete session {session_id} from the local database?<br>"
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
            f"Delete all {len(self._sessions)} session(s) from the local database?<br>"
            "This cannot be undone and does not delete ECG CSV files or webcam MP4s.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        n_deleted = self.repo.delete_all_sessions()
        logger.info("Cleared all sessions from database (%s deleted)", n_deleted)
        self.refresh_sessions()
