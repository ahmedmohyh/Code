"""Post-game dashboard with a modern card-based layout."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import os

from PyQt6.QtCore import QPoint, QSize, Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap, QPolygon
from PyQt6.QtMultimedia import QMediaPlayer
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSlider,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from flow_lol.ui.components import CardWidget, CompactActionBar, Switch
from flow_lol.ui.styles import Colors, Spacing
from flow_lol.persistence.repository import SessionRepository
from flow_lol.utils.paths import default_data_dir

logger = logging.getLogger(__name__)


class FlowTimelineWidget(QWidget):
    """Painter-based timeline/graph of flow (green) vs no-flow (grey) windows."""

    BAR_WIDTH = 12
    PADDING_LEFT = 50
    PADDING_RIGHT = 16
    PADDING_TOP = 24
    PADDING_BOTTOM = 36

    prediction_clicked = pyqtSignal(object)
    selection_changed = pyqtSignal(object)

    MODE_TIMELINE = "timeline"
    MODE_BLOCKS = "blocks"
    MODE_LINE = "line"
    MODE_SCATTER = "scatter"

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.predictions: List[Dict[str, Any]] = []
        self.matches: List[Dict[str, Any]] = []
        self.game_events: List[Dict[str, Any]] = []
        self.mode: str = self.MODE_TIMELINE
        self._alternate_shading = False
        self._selected_prediction: Optional[Dict[str, Any]] = None
        self._t_min = 0.0
        self._t_max = 1.0
        self._mouse_x: Optional[int] = None
        self._hover_pred: Optional[Dict[str, Any]] = None
        self.setMinimumHeight(200)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.CrossCursor)

    def set_mode(self, mode: str) -> None:
        self.mode = mode if mode in (self.MODE_TIMELINE, self.MODE_BLOCKS, self.MODE_LINE, self.MODE_SCATTER) else self.MODE_TIMELINE
        self.update()

    def set_data(
        self,
        predictions: List[Dict[str, Any]],
        matches: Optional[List[Dict[str, Any]]] = None,
        game_events: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        self.predictions = predictions
        self.matches = matches or []
        self.game_events = game_events or []
        self._selected_prediction = None
        self.update()

    def set_alternate_shading(self, enabled: bool) -> None:
        self._alternate_shading = enabled
        self.update()

    def selected_prediction(self) -> Optional[Dict[str, Any]]:
        return self._selected_prediction

    def set_selected_prediction(self, prediction: Optional[Dict[str, Any]]) -> None:
        self._selected_prediction = prediction
        if prediction is not None:
            self.selection_changed.emit(prediction)
        self.update()

    def paintEvent(self, event: object) -> None:
        painter = QPainter(self)
        try:
            self._draw(painter)
        finally:
            painter.end()

    def _geometry(self) -> tuple:
        width = self.width()
        height = self.height()
        plot_w = width - self.PADDING_LEFT - self.PADDING_RIGHT
        plot_h = height - self.PADDING_TOP - self.PADDING_BOTTOM
        return width, height, plot_w, plot_h

    def _time_range(self) -> tuple[float, float]:
        if not self.predictions:
            return 0.0, 1.0
        times = [p["timestamp"] for p in self.predictions]
        t_min, t_max = min(times), max(times)
        if t_max == t_min:
            t_max = t_min + 1.0
        return t_min, t_max

    def _x(self, t: float, t_min: float, t_max: float, plot_w: float) -> float:
        return self.PADDING_LEFT + (t - t_min) / (t_max - t_min) * plot_w

    def _t_from_x(self, x: float, t_min: float, t_max: float, plot_w: float) -> float:
        return t_min + (x - self.PADDING_LEFT) / max(1, plot_w) * (t_max - t_min)

    def _draw(self, painter: QPainter) -> None:
        width, height, plot_w, plot_h = self._geometry()
        if width <= 0 or height <= 0:
            return

        t_min, t_max = self._time_range()
        self._t_min, self._t_max = t_min, t_max

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

        if self.mode == self.MODE_TIMELINE:
            self._draw_timeline(painter, plot_w, plot_h, t_min, t_max)
        elif self.mode == self.MODE_BLOCKS:
            self._draw_blocks(painter, plot_w, plot_h, t_min, t_max)
        elif self.mode == self.MODE_LINE:
            self._draw_line(painter, plot_w, plot_h, t_min, t_max)
        elif self.mode == self.MODE_SCATTER:
            self._draw_scatter(painter, plot_w, plot_h, t_min, t_max)

        self._draw_axis_and_events(painter, plot_w, plot_h, t_min, t_max)
        self._draw_selection(painter, plot_w, plot_h, t_min, t_max)
        self._draw_hover_indicator(painter, plot_w, plot_h, t_min, t_max)

    def _draw_match_regions(
        self,
        painter: QPainter,
        plot_h: float,
        t_min: float,
        t_max: float,
        plot_w: float,
    ) -> None:
        for match in self.matches:
            start = match.get("started_at")
            end = match.get("ended_at") or t_max
            if start is None:
                continue
            x1 = self._x(start, t_min, t_max, plot_w)
            x2 = self._x(end, t_min, t_max, plot_w)
            painter.fillRect(
                int(x1),
                self.PADDING_TOP,
                max(1, int(x2 - x1)),
                plot_h,
                QColor(Colors.MATCH_REGION),
            )
            painter.setPen(QPen(QColor(180, 210, 230), 1))
            painter.drawLine(int(x1), self.PADDING_TOP, int(x1), self.PADDING_TOP + int(plot_h))
            painter.drawLine(int(x2), self.PADDING_TOP, int(x2), self.PADDING_TOP + int(plot_h))

    def _draw_timeline(
        self,
        painter: QPainter,
        plot_w: float,
        plot_h: float,
        t_min: float,
        t_max: float,
    ) -> None:
        self._draw_match_regions(painter, plot_h, t_min, t_max, plot_w)
        sorted_preds = sorted(enumerate(self.predictions), key=lambda item: item[1]["timestamp"])
        for idx, pred in sorted_preds:
            x = self._x(pred["timestamp"], t_min, t_max, plot_w)
            label = pred.get("ensemble_label", 0)
            color = self._prediction_color(label, idx)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            painter.drawRect(
                int(x - self.BAR_WIDTH / 2),
                self.PADDING_TOP,
                self.BAR_WIDTH,
                int(plot_h),
            )

    def _prediction_color(self, label: int, index: int) -> QColor:
        """Return the bar/block color, optionally alternating each window."""
        base = QColor(Colors.FLOW) if label == 1 else QColor(Colors.NO_FLOW)
        if not self._alternate_shading:
            return base
        if index % 2 == 1:
            if label == 1:
                return base.darker(110)
            return base.darker(115)
        return base

    def _draw_blocks(
        self,
        painter: QPainter,
        plot_w: float,
        plot_h: float,
        t_min: float,
        t_max: float,
    ) -> None:
        """Merge consecutive same-label predictions into wide coloured blocks."""
        self._draw_match_regions(painter, plot_h, t_min, t_max, plot_w)
        if not self.predictions:
            return
        sorted_preds = sorted(self.predictions, key=lambda p: p["timestamp"])
        runs: list[tuple[float, float, int]] = []
        run_start_ts = sorted_preds[0]["timestamp"]
        run_label = sorted_preds[0].get("ensemble_label", 0)
        for pred in sorted_preds[1:]:
            label = pred.get("ensemble_label", 0)
            if label != run_label:
                runs.append((run_start_ts, pred["timestamp"], run_label))
                run_start_ts = pred["timestamp"]
                run_label = label
        runs.append((run_start_ts, sorted_preds[-1]["timestamp"], run_label))

        for run_idx, (start_ts, end_ts, label) in enumerate(runs):
            x1 = self._x(start_ts, t_min, t_max, plot_w)
            x2 = self._x(end_ts, t_min, t_max, plot_w)
            color = self._prediction_color(label, run_idx)
            # Add a subtle border so adjacent blocks are distinguishable.
            painter.setPen(QPen(QColor(Colors.TEXT_MUTED), 1))
            painter.setBrush(color)
            rect_x = int(x1)
            rect_w = max(self.BAR_WIDTH, int(x2 - x1))
            painter.drawRect(rect_x, self.PADDING_TOP, rect_w, int(plot_h))

    def _draw_line(
        self,
        painter: QPainter,
        plot_w: float,
        plot_h: float,
        t_min: float,
        t_max: float,
    ) -> None:
        self._draw_match_regions(painter, plot_h, t_min, t_max, plot_w)
        sorted_preds = sorted(self.predictions, key=lambda p: p["timestamp"])
        pen = QPen(QColor(Colors.TEXT), 2)
        painter.setPen(pen)
        prev_x: Optional[float] = None
        prev_y: Optional[float] = None
        for pred in sorted_preds:
            x = self._x(pred["timestamp"], t_min, t_max, plot_w)
            label = pred.get("ensemble_label", 0)
            y = self.PADDING_TOP + (0 if label == 1 else int(plot_h))
            color = QColor(Colors.FLOW) if label == 1 else QColor(Colors.NO_FLOW)
            painter.setBrush(color)
            painter.drawEllipse(int(x - 4), int(y - 4), 8, 8)
            if prev_x is not None and prev_y is not None:
                painter.drawLine(int(prev_x), int(prev_y), int(x), int(y))
            prev_x, prev_y = x, y

    def _draw_scatter(
        self,
        painter: QPainter,
        plot_w: float,
        plot_h: float,
        t_min: float,
        t_max: float,
    ) -> None:
        self._draw_match_regions(painter, plot_h, t_min, t_max, plot_w)
        for pred in self.predictions:
            x = self._x(pred["timestamp"], t_min, t_max, plot_w)
            label = pred.get("ensemble_label", 0)
            y = self.PADDING_TOP + (0.2 * plot_h if label == 1 else 0.8 * plot_h)
            color = QColor(Colors.FLOW) if label == 1 else QColor(Colors.NO_FLOW)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            painter.drawEllipse(int(x - 5), int(y - 5), 10, 10)

    def _draw_axis_and_events(
        self,
        painter: QPainter,
        plot_w: float,
        plot_h: float,
        t_min: float,
        t_max: float,
    ) -> None:
        # Game event markers (triangles above the axis)
        event_colors = {
            "kill": QColor(Colors.SUCCESS),
            "death": QColor(Colors.DANGER),
            "objective": QColor(Colors.PRIMARY),
        }
        painter.setPen(Qt.PenStyle.NoPen)
        y_axis = self.PADDING_TOP + int(plot_h)
        for event in self.game_events:
            t = event.get("timestamp")
            if t is None:
                continue
            x = self._x(t, t_min, t_max, plot_w)
            etype = event.get("event_type", "")
            color = event_colors.get(etype, QColor(Colors.WARNING))
            painter.setBrush(color)
            polygon = QPolygon([
                QPoint(int(x), y_axis - 8),
                QPoint(int(x - 5), y_axis - 1),
                QPoint(int(x + 5), y_axis - 1),
            ])
            painter.drawPolygon(polygon)

        # Axis line
        painter.setPen(QPen(QColor(Colors.TEXT_MUTED), 1))
        painter.drawLine(self.PADDING_LEFT, y_axis, self.width() - self.PADDING_RIGHT, y_axis)

        # Time labels
        painter.setPen(QColor(Colors.TEXT_SECONDARY))
        for label_t in [t_min, (t_min + t_max) / 2, t_max]:
            txt = datetime.fromtimestamp(label_t).strftime("%H:%M:%S")
            x = self._x(label_t, t_min, t_max, plot_w)
            painter.drawText(int(x - 30), y_axis + 20, 60, 20, Qt.AlignmentFlag.AlignCenter, txt)

    def _prediction_at_x(self, x: float) -> tuple[Optional[Dict[str, Any]], float]:
        """Return the prediction nearest to the given mouse x and the time there."""
        width, _, plot_w, _ = self._geometry()
        if not self.predictions or plot_w <= 0 or x < self.PADDING_LEFT or x > width - self.PADDING_RIGHT:
            return None, 0.0
        t_min, t_max = self._time_range()
        t = self._t_from_x(x, t_min, t_max, plot_w)
        nearest = min(self.predictions, key=lambda p: abs(p["timestamp"] - t))
        # Accept clicks/hovers within ~1.5 average inter-prediction gaps.
        threshold = max(15.0, (t_max - t_min) / max(1, len(self.predictions)) * 1.5)
        if abs(nearest["timestamp"] - t) <= threshold:
            return nearest, t
        return None, t

    def mouseMoveEvent(self, event) -> None:
        x = int(event.position().x())
        self._mouse_x = x
        pred, t = self._prediction_at_x(x)
        self._hover_pred = pred
        if pred is not None:
            ts = pred["timestamp"]
            label = "flow" if pred.get("ensemble_label", 0) == 1 else "no-flow"
            votes = pred.get("n_for_majority", 0)
            total = pred.get("n_votes", 0)
            self.setToolTip(
                f"{datetime.fromtimestamp(ts).strftime('%H:%M:%S')} – {label.upper()}\n"
                f"Votes: {votes}/{total} | click to inspect"
            )
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self.setToolTip("")
            self.setCursor(Qt.CursorShape.CrossCursor)
        self.update()

    def leaveEvent(self, event) -> None:
        self._mouse_x = None
        self._hover_pred = None
        self.setToolTip("")
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.update()

    def _draw_hover_indicator(
        self,
        painter: QPainter,
        plot_w: float,
        plot_h: float,
        t_min: float,
        t_max: float,
    ) -> None:
        if self._mouse_x is None:
            return
        width, _, _, _ = self._geometry()
        if self._mouse_x < self.PADDING_LEFT or self._mouse_x > width - self.PADDING_RIGHT:
            return
        # Vertical time indicator line.
        painter.setPen(QPen(QColor(Colors.TEXT_SECONDARY), 1, Qt.PenStyle.DashLine))
        painter.drawLine(self._mouse_x, self.PADDING_TOP, self._mouse_x, self.PADDING_TOP + int(plot_h))
        # If the cursor is over a prediction, draw a small highlight outline.
        if self._hover_pred is not None:
            x = self._x(self._hover_pred["timestamp"], t_min, t_max, plot_w)
            label = self._hover_pred.get("ensemble_label", 0)
            color = QColor(Colors.TEXT if label == 1 else Colors.TEXT)
            painter.setPen(QPen(color, 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            half = self.BAR_WIDTH // 2 + 4
            painter.drawRect(int(x - half), self.PADDING_TOP - 4, half * 2, int(plot_h) + 8)

    def _draw_selection(
        self,
        painter: QPainter,
        plot_w: float,
        plot_h: float,
        t_min: float,
        t_max: float,
    ) -> None:
        if self._selected_prediction is None:
            return
        x = self._x(self._selected_prediction["timestamp"], t_min, t_max, plot_w)
        label = self._selected_prediction.get("ensemble_label", 0)
        color = QColor(Colors.PRIMARY) if label == 1 else QColor(Colors.TEXT)
        # Solid vertical line for the selected window.
        painter.setPen(QPen(color, 2))
        painter.drawLine(int(x), self.PADDING_TOP, int(x), self.PADDING_TOP + int(plot_h))
        # Label at the top of the line.
        ts = self._selected_prediction["timestamp"]
        txt = datetime.fromtimestamp(ts).strftime("%H:%M:%S")
        painter.setPen(QColor(Colors.TEXT))
        text_y = max(2, self.PADDING_TOP - 18)
        painter.drawText(int(x) + 4, text_y, 120, 16, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, txt)

    def mousePressEvent(self, event) -> None:
        pred, _ = self._prediction_at_x(event.position().x())
        if pred is not None:
            self.set_selected_prediction(pred)
            self.prediction_clicked.emit(pred)


class DashboardWidget(QWidget):
    """Post-game dashboard for reviewing sessions, matches, and flow predictions."""

    session_changed = pyqtSignal(object)
    test_webcam_clicked = pyqtSignal()

    def __init__(
        self,
        settings: Any | None = None,
        webcam_dir: Optional[Path] = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.settings = settings
        self.repo = SessionRepository()
        self.webcam_dir = Path(webcam_dir) if webcam_dir else default_data_dir() / "webcam"
        self._sessions: List[Dict[str, Any]] = []
        self._match_rows: List[Dict[str, Any]] = []
        self._replay_rows: List[Dict[str, Any]] = []
        self._current_session_id: Optional[int] = None
        self._current_predictions: List[Dict[str, Any]] = []
        self._sorted_predictions: List[Dict[str, Any]] = []
        self._selected_index: int = -1

        self._build_ui()
        self.refresh_sessions()

    def current_session_id(self) -> Optional[int]:
        """Return the id of the session currently shown in the dashboard."""
        return self._current_session_id

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

        self.test_webcam_btn = actions.add_button("📹 Test webcam")
        self.test_webcam_btn.setToolTip("Quickly check or toggle the webcam")
        self.test_webcam_btn.clicked.connect(self._on_test_webcam)

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

        # View-mode selector
        view_row = QHBoxLayout()
        view_row.setSpacing(Spacing.MD)
        view_row.addWidget(QLabel("View mode:"))
        self.view_combo = QComboBox()
        self.view_combo.addItem("Timeline (bars)", FlowTimelineWidget.MODE_TIMELINE)
        self.view_combo.addItem("Blocks", FlowTimelineWidget.MODE_BLOCKS)
        self.view_combo.addItem("Line graph", FlowTimelineWidget.MODE_LINE)
        self.view_combo.addItem("Scatter", FlowTimelineWidget.MODE_SCATTER)
        self.view_combo.currentIndexChanged.connect(self._on_view_mode_changed)
        view_row.addWidget(self.view_combo)
        view_row.addStretch()
        view_row.addWidget(QLabel("Alternate shading:"))
        self.alternate_switch = Switch()
        self.alternate_switch.setToolTip("Shade every other window so boundaries are easier to see")
        self.alternate_switch.toggled.connect(self._on_alternate_toggled)
        view_row.addWidget(self.alternate_switch)
        layout.addLayout(view_row)

        # Navigation row under the timeline
        nav_row = QHBoxLayout()
        nav_row.setSpacing(Spacing.MD)
        self.prev_window_btn = QPushButton("◀ Prev window")
        self.prev_window_btn.setToolTip("Move the selection to the previous prediction window")
        self.prev_window_btn.clicked.connect(self._on_previous_window)
        self.next_window_btn = QPushButton("Next window ▶")
        self.next_window_btn.setToolTip("Move the selection to the next prediction window")
        self.next_window_btn.clicked.connect(self._on_next_window)
        self.prev_flow_btn = QPushButton("◀ Prev flow")
        self.prev_flow_btn.setToolTip("Jump the selection to the previous flow window")
        self.prev_flow_btn.clicked.connect(self._on_previous_flow_window)
        self.next_flow_btn = QPushButton("Next flow ▶")
        self.next_flow_btn.setToolTip("Jump the selection to the next flow window")
        self.next_flow_btn.clicked.connect(self._on_next_flow_window)
        self.inspect_selected_btn = QPushButton("🔍 Inspect selected")
        self.inspect_selected_btn.setToolTip("Open the selected window in the inspection popup")
        self.inspect_selected_btn.clicked.connect(self._on_inspect_selected)
        self.inspect_selected_btn.setEnabled(False)
        nav_row.addWidget(self.prev_window_btn)
        nav_row.addWidget(self.next_window_btn)
        nav_row.addWidget(self.prev_flow_btn)
        nav_row.addWidget(self.next_flow_btn)
        nav_row.addWidget(self.inspect_selected_btn)
        self.selection_info = QLabel("Click a window or use Prev / Next")
        self.selection_info.setProperty("role", "muted")
        nav_row.addWidget(self.selection_info)
        nav_row.addStretch()
        layout.addLayout(nav_row)

        # Content splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Timeline card
        timeline_card = CardWidget("Flow timeline")
        self.timeline = FlowTimelineWidget()
        self.timeline.prediction_clicked.connect(self._on_prediction_clicked)
        self.timeline.selection_changed.connect(self._on_timeline_selection_changed)
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
        self.match_list.setMinimumHeight(220)
        self.match_list.currentItemChanged.connect(self._on_match_selected)
        details_layout.addWidget(self.match_list, stretch=2)

        details_layout.addWidget(QLabel("Game events"))
        self.event_list = QListWidget()
        self.event_list.setAlternatingRowColors(True)
        self.event_list.setMinimumHeight(120)
        details_layout.addWidget(self.event_list, stretch=1)

        details_layout.addWidget(QLabel("Replays"))
        self.replay_list = QListWidget()
        self.replay_list.setAlternatingRowColors(True)
        self.replay_list.setMinimumHeight(100)
        details_layout.addWidget(self.replay_list, stretch=1)

        self.open_replay_btn = QPushButton("▶ Open selected replay")
        self.open_replay_btn.clicked.connect(self._open_selected_replay)
        self.open_replay_btn.setEnabled(False)
        details_layout.addWidget(self.open_replay_btn)

        splitter.addWidget(details_card)
        splitter.setSizes([520, 450])
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
            self._current_session_id = None
            self.session_changed.emit(None)
            return

        session_id = session["id"]
        self._current_session_id = session_id
        self.session_changed.emit(session_id)
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
        step_seconds = self._prediction_step_seconds(predictions)
        flow_duration = n_flow * step_seconds
        duration = (
            "running"
            if session["ended_at"] is None
            else self._format_duration(session["ended_at"] - session["started_at"])
        )
        sensor_summary = session.get("sensor_summary") or "unknown"

        self.details_label.setProperty("role", "")
        self.details_label.setText(
            f"<b>Session {session_id}</b><br>"
            f"Started: {datetime.fromtimestamp(session['started_at'])}<br>"
            f"Duration: {duration}<br>"
            f"Sensors: {sensor_summary}<br>"
            f"Predictions: {n_preds} windows<br>"
            f"Flow windows: {n_flow} ({flow_pct:.1f}%, {self._format_duration(flow_duration)})<br>"
            f"Sensor events: {len(events)} | Game events: {len(game_events)} | Replays: {len(replays)}"
        )

        self._current_predictions = predictions
        self._sorted_predictions = sorted(predictions, key=lambda p: p["timestamp"])
        self._selected_index = -1
        self.timeline.set_data(predictions, matches, game_events)
        self._update_selection_ui()

    @staticmethod
    def _format_duration(seconds: float) -> str:
        """Format seconds as Xm YYs."""
        s = max(0, int(round(seconds)))
        return f"{s // 60}m {s % 60:02d}s"

    def _prediction_step_seconds(self, predictions: List[Dict[str, Any]]) -> float:
        """Estimate the interval between consecutive prediction windows."""
        if len(predictions) < 2:
            return 30.0
        times = sorted(p["timestamp"] for p in predictions)
        diffs = [times[i + 1] - times[i] for i in range(len(times) - 1)]
        median = sorted(diffs)[len(diffs) // 2]
        return max(1.0, median)

    def _on_test_webcam(self) -> None:
        """Emit signal so MainWindow can run the actual webcam test/toggle."""
        self.test_webcam_clicked.emit()

    def _on_view_mode_changed(self, index: int) -> None:
        mode = self.view_combo.itemData(index)
        if mode:
            self.timeline.set_mode(str(mode))

    def _on_prediction_clicked(self, prediction: Dict[str, Any]) -> None:
        if self._current_session_id is None:
            return
        # Use the configured window size so the popup shows the exact prediction window.
        window_seconds = 60
        if self.settings is not None:
            window_seconds = max(1, getattr(self.settings, "window_seconds", 60))
        # Find the match active during this prediction, if any.
        pred_ts = prediction.get("timestamp", 0.0)
        active_match_id: int | None = None
        for m in self._match_rows:
            started = m.get("started_at") or 0
            ended = m.get("ended_at")
            if started <= pred_ts and (ended is None or pred_ts <= ended):
                active_match_id = m["id"]
                break
        game_events = (
            self.repo.get_game_events(self._current_session_id, match_id=active_match_id)
            if active_match_id is not None
            else []
        )
        dialog = PredictionInspectDialog(
            prediction=prediction,
            session_id=self._current_session_id,
            webcam_dir=self.webcam_dir,
            window_seconds=window_seconds,
            game_events=game_events,
            parent=self,
        )
        dialog.exec()

    def _on_timeline_selection_changed(self, prediction: Dict[str, Any]) -> None:
        if not self._sorted_predictions:
            return
        for i, p in enumerate(self._sorted_predictions):
            if p["timestamp"] == prediction["timestamp"]:
                self._selected_index = i
                break
        self._update_selection_ui()

    def _update_selection_ui(self) -> None:
        has_selection = self._selected_index >= 0 and self._selected_index < len(self._sorted_predictions)
        n_preds = len(self._sorted_predictions)
        has_flow = any(p.get("ensemble_label") == 1 for p in self._sorted_predictions)
        self.inspect_selected_btn.setEnabled(has_selection)
        self.prev_window_btn.setEnabled(n_preds > 1)
        self.next_window_btn.setEnabled(n_preds > 0)
        self.prev_flow_btn.setEnabled(has_flow and n_preds > 1)
        self.next_flow_btn.setEnabled(has_flow)
        if has_selection:
            pred = self._sorted_predictions[self._selected_index]
            ts = pred["timestamp"]
            label = "flow" if pred.get("ensemble_label", 0) == 1 else "no-flow"
            self.selection_info.setText(
                f"Selected {datetime.fromtimestamp(ts).strftime('%H:%M:%S')} ({label})"
            )
        else:
            self.selection_info.setText("Click a window or use Next / Next flow")

    def _on_previous_window(self) -> None:
        if not self._sorted_predictions:
            return
        n = len(self._sorted_predictions)
        if self._selected_index < 0:
            self._selected_index = n - 1
        else:
            self._selected_index = (self._selected_index - 1) % n
        pred = self._sorted_predictions[self._selected_index]
        self.timeline.set_selected_prediction(pred)
        self._update_selection_ui()

    def _on_next_window(self) -> None:
        if not self._sorted_predictions:
            return
        if self._selected_index < 0:
            self._selected_index = 0
        else:
            self._selected_index = (self._selected_index + 1) % len(self._sorted_predictions)
        pred = self._sorted_predictions[self._selected_index]
        self.timeline.set_selected_prediction(pred)
        self._update_selection_ui()

    def _on_previous_flow_window(self) -> None:
        if not self._sorted_predictions:
            return
        n = len(self._sorted_predictions)
        start = self._selected_index if self._selected_index >= 0 else n - 1
        for offset in range(1, n + 1):
            idx = (start - offset) % n
            if self._sorted_predictions[idx].get("ensemble_label") == 1:
                self._selected_index = idx
                pred = self._sorted_predictions[idx]
                self.timeline.set_selected_prediction(pred)
                self._update_selection_ui()
                return

    def _on_next_flow_window(self) -> None:
        if not self._sorted_predictions:
            return
        start = max(0, self._selected_index)
        n = len(self._sorted_predictions)
        for offset in range(1, n + 1):
            idx = (start + offset) % n
            if self._sorted_predictions[idx].get("ensemble_label") == 1:
                self._selected_index = idx
                pred = self._sorted_predictions[idx]
                self.timeline.set_selected_prediction(pred)
                self._update_selection_ui()
                return

    def _on_inspect_selected(self) -> None:
        if 0 <= self._selected_index < len(self._sorted_predictions):
            self._on_prediction_clicked(self._sorted_predictions[self._selected_index])

    def _on_alternate_toggled(self, enabled: bool) -> None:
        self.timeline.set_alternate_shading(enabled)

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


class PredictionInspectDialog(QDialog):
    """Popup showing details for a single prediction with in-app video + snapshots."""

    def __init__(
        self,
        prediction: Dict[str, Any],
        session_id: int,
        webcam_dir: Path,
        window_seconds: float = 30.0,
        game_events: Optional[List[Dict[str, Any]]] = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.prediction = prediction
        self.session_id = session_id
        self.webcam_dir = webcam_dir
        self._window_ms = int(window_seconds * 1000)
        self._game_events = game_events or []
        self._video_path: Optional[Path] = None
        self._video_start_ts: Optional[float] = None
        self._auto_seek_done = False

        ts = prediction.get("timestamp", 0.0)
        label = prediction.get("ensemble_label", 0)
        label_text = "flow" if label == 1 else "no-flow"
        n_votes = prediction.get("n_votes", 0)
        n_for = prediction.get("n_for_majority", 0)

        self.setWindowTitle(f"Prediction at {datetime.fromtimestamp(ts).strftime('%H:%M:%S')}")
        self.setMinimumSize(720, 620)
        self.resize(760, 640)

        layout = QVBoxLayout(self)
        layout.setSpacing(Spacing.MD)

        summary = QLabel(
            f"<b>Result:</b> {label_text.upper()}<br>"
            f"<b>Votes:</b> {n_for}/{n_votes} models voted {label_text}<br>"
            f"<b>Time:</b> {datetime.fromtimestamp(ts)}"
        )
        summary.setWordWrap(True)
        layout.addWidget(summary)

        # Per-model votes in a single horizontal row so no scrolling is needed.
        votes_layout = QHBoxLayout()
        votes_layout.setSpacing(Spacing.MD)
        votes = prediction.get("votes", {})
        if votes:
            for name, vote in sorted(votes.items()):
                icon = "✅" if vote == 1 else "❌"
                vote_label = QLabel(f"<b>{icon} {name}</b>")
                vote_label.setStyleSheet(
                    f"background: {Colors.SURFACE_DIM};"
                    f"border: 1px solid {Colors.BORDER};"
                    f"border-radius: {Spacing.RADIUS_SM}px;"
                    f"padding: 4px 10px;"
                )
                votes_layout.addWidget(vote_label)
            votes_layout.addStretch(1)
        else:
            no_votes = QLabel("No vote data available")
            no_votes.setProperty("role", "muted")
            votes_layout.addWidget(no_votes)
            votes_layout.addStretch(1)
        layout.addLayout(votes_layout)

        media_card = CardWidget("Media preview")
        media_layout = media_card.content_layout()

        self.player = QMediaPlayer()
        self.video_widget = QVideoWidget()
        self.video_widget.setMinimumHeight(320)
        self.video_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self.player.setVideoOutput(self.video_widget)

        self.image_overlay = QLabel()
        self.image_overlay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_overlay.setStyleSheet("background-color: #000000;")
        self.image_overlay.setMinimumHeight(320)
        self.image_overlay.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        self.preview_stack = QStackedWidget()
        self.preview_stack.setMinimumHeight(340)
        self.preview_stack.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self.preview_stack.addWidget(self.video_widget)
        self.preview_stack.addWidget(self.image_overlay)
        self.preview_stack.setCurrentWidget(self.video_widget)
        media_layout.addWidget(self.preview_stack, stretch=1)

        self.player.positionChanged.connect(self._on_position_changed)
        self.player.durationChanged.connect(self._on_duration_changed)
        self.player.mediaStatusChanged.connect(self._on_media_status_changed)

        self._seek_slider = QSlider(Qt.Orientation.Horizontal)
        self._seek_slider.setRange(0, 0)
        self._seek_slider.setEnabled(False)
        self._seek_slider.sliderReleased.connect(self._on_seek_released)
        self._time_label = QLabel("00:00 / 00:00")
        self._time_label.setProperty("role", "muted")

        controls = QHBoxLayout()
        controls.setSpacing(Spacing.SM)
        self.play_btn = QPushButton("▶")
        self.play_btn.setProperty("role", "icon")
        self.play_btn.setToolTip("Play / pause")
        self.play_btn.clicked.connect(self._toggle_playback)
        self.play_btn.setEnabled(False)
        self.stop_btn = QPushButton("⏹")
        self.stop_btn.setProperty("role", "icon")
        self.stop_btn.setToolTip("Stop")
        self.stop_btn.clicked.connect(self._stop)
        self.stop_btn.setEnabled(False)
        controls.addWidget(self.play_btn)
        controls.addWidget(self.stop_btn)
        controls.addWidget(self._seek_slider, stretch=1)
        controls.addWidget(self._time_label)
        media_layout.addLayout(controls)

        media_buttons = QHBoxLayout()
        media_buttons.setSpacing(Spacing.MD)
        self.play_video_btn = QPushButton("▶ Play video at prediction")
        self.play_video_btn.setToolTip("Load the session video and jump to the prediction time")
        self.play_video_btn.clicked.connect(self._play_video_at_prediction)
        media_buttons.addWidget(self.play_video_btn)
        media_buttons.addStretch()
        media_layout.addLayout(media_buttons)

        self.media_info = QLabel("")
        self.media_info.setProperty("role", "muted")
        self.media_info.setWordWrap(True)
        media_layout.addWidget(self.media_info)

        layout.addWidget(media_card, stretch=1)

        # Game events around prediction ---------------------------------------
        events_card = CardWidget("Game events around prediction")
        events_layout = events_card.content_layout()
        events_layout.setSpacing(Spacing.SM)

        self.events_around_list = QListWidget()
        self.events_around_list.setAlternatingRowColors(True)
        self.events_around_list.setMinimumHeight(80)
        self.events_around_list.setMaximumHeight(140)
        self._populate_events_around(ts)
        events_layout.addWidget(self.events_around_list)
        layout.addWidget(events_card)

        # Snapshots gallery ---------------------------------------------------
        snapshots_card = CardWidget("Snapshots around prediction")
        snaps_layout = snapshots_card.content_layout()
        snaps_layout.setSpacing(Spacing.SM)

        self.snap_gallery = QListWidget()
        self.snap_gallery.setViewMode(QListWidget.ViewMode.IconMode)
        self.snap_gallery.setFlow(QListWidget.Flow.LeftToRight)
        self.snap_gallery.setWrapping(True)
        self.snap_gallery.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.snap_gallery.setSpacing(8)
        self.snap_gallery.setIconSize(QSize(110, 90))
        self.snap_gallery.setGridSize(QSize(140, 130))
        self.snap_gallery.setMinimumHeight(220)
        self.snap_gallery.setMaximumHeight(340)
        self.snap_gallery.setAlternatingRowColors(False)
        self.snap_gallery.itemClicked.connect(self._show_snapshot_image)
        snaps_layout.addWidget(self.snap_gallery, stretch=1)

        snap_nav = QHBoxLayout()
        snap_nav.setSpacing(Spacing.MD)
        self.prev_snap_btn = QPushButton("◀ Previous snapshot")
        self.prev_snap_btn.clicked.connect(self._previous_snapshot)
        self.next_snap_btn = QPushButton("Next snapshot ▶")
        self.next_snap_btn.clicked.connect(self._next_snapshot)
        snap_nav.addWidget(self.prev_snap_btn)
        snap_nav.addWidget(self.next_snap_btn)
        snap_nav.addStretch()
        snaps_layout.addLayout(snap_nav)

        layout.addWidget(snapshots_card, stretch=1)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

        # Try to pre-load the session video and seek to the prediction time.
        self._load_session_video()

        # Load snapshot thumbnails for this prediction.
        self._populate_snapshots(ts)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _session_video_path(self) -> Optional[Path]:
        if not self.webcam_dir.exists():
            return None
        # New layout: session folder containing a video.
        for folder in self.webcam_dir.iterdir():
            if folder.is_dir() and folder.name.startswith(f"session_{self.session_id}_"):
                videos = list(folder.glob("*.mp4"))
                if videos:
                    return videos[0]
        # Old layout: top-level MP4 file matching the session id.
        for path in self.webcam_dir.iterdir():
            if (
                path.is_file()
                and path.suffix.lower() == ".mp4"
                and path.name.startswith(f"session_{self.session_id}_")
            ):
                return path
        return None

    @staticmethod
    def _video_start_timestamp(path: Path) -> Optional[float]:
        """Parse session_<id>_YYYYMMDD_HHMMSS.mp4 filename or fall back to mtime."""
        import re

        match = re.match(r"session_\d+_(\d{8}_\d{6})\.mp4", path.name, re.IGNORECASE)
        if match:
            try:
                dt = datetime.strptime(match.group(1), "%Y%m%d_%H%M%S")
                return dt.timestamp()
            except ValueError:
                pass
        try:
            return path.stat().st_mtime
        except Exception:
            return None

    def _load_session_video(self) -> None:
        video = self._session_video_path()
        if video is None:
            self.media_info.setText("No webcam video found for this session.")
            self.play_video_btn.setEnabled(False)
            return
        self._video_path = video
        self._video_start_ts = self._video_start_timestamp(video)
        pred_ts = self.prediction.get("timestamp", 0.0)
        offset_ms = self._offset_ms(pred_ts)
        window_s = getattr(self, "_window_ms", 30000) // 1000
        self.media_info.setText(
            f"Video: {video.name}  |  offset {self._format_ms(offset_ms)}"
            f"  |  window {window_s}s"
        )
        self.player.setSource(QUrl.fromLocalFile(str(video)))
        self.play_btn.setEnabled(True)
        self.stop_btn.setEnabled(True)
        self._seek_slider.setEnabled(True)

    def _offset_ms(self, pred_ts: float) -> int:
        if self._video_start_ts is None:
            return 0
        return int(max(0, pred_ts - self._video_start_ts) * 1000)

    def _play_video_at_prediction(self) -> None:
        if self._video_path is None:
            self._load_session_video()
        offset_ms = self._offset_ms(self.prediction.get("timestamp", 0.0))
        self.preview_stack.setCurrentWidget(self.video_widget)
        self.player.setPosition(offset_ms)
        self.player.play()
        self.play_btn.setText("⏸")

    # ------------------------------------------------------------------
    # Windowed playback: keep the playhead inside the exact prediction window.
    # ------------------------------------------------------------------

    def _preview_bounds_ms(self) -> tuple[int, int]:
        """Return start/end offset in ms for the exact prediction window clip."""
        offset_ms = self._offset_ms(self.prediction.get("timestamp", 0.0))
        # The popup is created with the window size in seconds from the settings.
        window_ms = getattr(self, "_window_ms", 30000)
        duration = self.player.duration()
        start_ms = max(0, offset_ms)
        end_ms = start_ms + window_ms
        if duration > 0:
            end_ms = min(end_ms, duration)
        return start_ms, end_ms

    def _clamp_to_preview_window(self) -> None:
        """Loop playback inside the selected prediction window."""
        position = self.player.position()
        start_ms, end_ms = self._preview_bounds_ms()
        if position < start_ms or position >= end_ms:
            self.player.setPosition(start_ms)

    def _on_media_status_changed(self, status: QMediaPlayer.MediaStatus) -> None:
        if status == QMediaPlayer.MediaStatus.LoadedMedia and not self._auto_seek_done:
            self._auto_seek_done = True
            # Auto-seek to the prediction offset once the video is ready.
            self._play_video_at_prediction()

    def _on_position_changed(self, position: int) -> None:
        if not self._seek_slider.isSliderDown():
            self._seek_slider.setValue(position)
        self._update_time_label(position, self.player.duration())
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._clamp_to_preview_window()

    def _on_duration_changed(self, duration: int) -> None:
        self._seek_slider.setRange(0, duration)
        self._update_time_label(self.player.position(), duration)

    def _on_seek_released(self) -> None:
        start_ms, end_ms = self._preview_bounds_ms()
        value = max(start_ms, min(self._seek_slider.value(), end_ms))
        self.player.setPosition(value)

    def _toggle_playback(self) -> None:
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
            self.play_btn.setText("▶")
        else:
            self.preview_stack.setCurrentWidget(self.video_widget)
            start_ms, _ = self._preview_bounds_ms()
            if self.player.position() < start_ms:
                self.player.setPosition(start_ms)
            self.player.play()
            self.play_btn.setText("⏸")

    def _stop(self) -> None:
        self.player.stop()
        self.play_btn.setText("▶")
        self._seek_slider.setValue(0)
        self._update_time_label(0, self.player.duration())

    @staticmethod
    def _format_ms(ms: int) -> str:
        seconds = max(0, ms) // 1000
        return f"{seconds // 60:02d}:{seconds % 60:02d}"

    def _update_time_label(self, position: int, duration: int) -> None:
        self._time_label.setText(f"{self._format_ms(position)} / {self._format_ms(duration)}")

    # ------------------------------------------------------------------
    # Game events
    # ------------------------------------------------------------------

    def _populate_events_around(self, ts: float) -> None:
        """List game events whose timestamp falls inside the prediction window."""
        self.events_around_list.clear()
        half_window = (self._window_ms / 1000.0) / 2.0
        start_ts = ts - half_window
        end_ts = ts + half_window
        shown = 0
        for e in self._game_events:
            et = e.get("timestamp")
            if et is None or et < start_ts or et > end_ts:
                continue
            t = datetime.fromtimestamp(et).strftime("%H:%M:%S")
            actor = e.get("actor") or "?"
            target = e.get("target") or ""
            etype = e.get("event_type", "event")
            desc = f"{t} – {etype}"
            if target:
                desc += f": {actor} → {target}"
            else:
                desc += f": {actor}"
            self.events_around_list.addItem(desc)
            shown += 1
        if shown == 0:
            self.events_around_list.addItem("No game events in this prediction window")

    # ------------------------------------------------------------------
    # Snapshots
    # ----------------------------------------------------------------

    def _populate_snapshots(self, ts: float) -> None:
        self.snap_gallery.clear()
        self._snapshot_paths: List[Path] = []
        if not self.webcam_dir.exists():
            self.snap_gallery.addItem("No webcam folder found")
            return

        snaps: List[Path] = []
        # New layout: session folders.
        for folder in self.webcam_dir.iterdir():
            if folder.is_dir() and folder.name.startswith(f"session_{self.session_id}_"):
                snap_dir = folder / "snapshots"
                if snap_dir.exists():
                    snaps.extend(self._collect_snapshots(snap_dir))
        # Old layout: top-level snapshots folder.
        if not snaps:
            old_snap_dir = self.webcam_dir / "snapshots"
            if old_snap_dir.exists():
                snaps.extend(self._collect_snapshots(old_snap_dir))

        # Show the snapshots closest in time to the prediction first.
        snaps.sort(key=lambda p: abs(p.stat().st_mtime - ts))
        snaps = snaps[:50]
        self._snapshot_paths = snaps

        for path in snaps:
            item = QListWidgetItem(path.name)
            item.setData(Qt.ItemDataRole.UserRole, str(path))
            item.setToolTip(str(path))
            icon = self._snapshot_thumbnail(str(path))
            if icon is not None:
                item.setIcon(icon)
            else:
                item.setText(f"📷 {path.name}")
            item.setSizeHint(QSize(120, 120))
            self.snap_gallery.addItem(item)

        if self.snap_gallery.count() == 0:
            self.snap_gallery.addItem("No snapshots found for this session")
        self._update_snapshot_nav_buttons()

    def _snapshot_thumbnail(self, path: str) -> Optional[QIcon]:
        """Return a 110x90 thumbnail icon for a snapshot image."""
        try:
            pixmap = QPixmap(path)
            if pixmap.isNull():
                return None
            scaled = pixmap.scaled(
                QSize(110, 90),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            return QIcon(scaled)
        except Exception:
            return None

    @staticmethod
    def _collect_snapshots(snap_dir: Path) -> List[Path]:
        """Return all JPG snapshots in snap_dir."""
        return [p for p in snap_dir.glob("*.jpg") if p.is_file()]

    def _update_snapshot_nav_buttons(self) -> None:
        row = self.snap_gallery.currentRow()
        self.prev_snap_btn.setEnabled(row > 0)
        self.next_snap_btn.setEnabled(0 <= row < self.snap_gallery.count() - 1)

    def _previous_snapshot(self) -> None:
        row = self.snap_gallery.currentRow()
        if row > 0:
            self.snap_gallery.setCurrentRow(row - 1)
            item = self.snap_gallery.currentItem()
            if item is not None:
                self._show_snapshot_image(item)

    def _next_snapshot(self) -> None:
        row = self.snap_gallery.currentRow()
        if 0 <= row < self.snap_gallery.count() - 1:
            self.snap_gallery.setCurrentRow(row + 1)
            item = self.snap_gallery.currentItem()
            if item is not None:
                self._show_snapshot_image(item)

    def _show_snapshots(self) -> None:
        self._populate_snapshots(self.prediction.get("timestamp", 0.0))

    def _show_snapshot_image(self, item: QListWidgetItem) -> None:
        path_str = item.data(Qt.ItemDataRole.UserRole)
        if not path_str:
            return
        path = Path(path_str)
        self.player.stop()
        self.play_btn.setText("▶")
        self.preview_stack.setCurrentWidget(self.image_overlay)
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            self.image_overlay.setText(f"Could not load {path.name}")
            self.image_overlay.setStyleSheet("background-color: #000000; color: #ffffff; font-size: 16px;")
            return
        target_size = self.image_overlay.size()
        if target_size.width() <= 10 or target_size.height() <= 10:
            target_size = self.preview_stack.size()
        if target_size.width() <= 10 or target_size.height() <= 10:
            target_size = QSize(640, 480)
        scaled = pixmap.scaled(
            target_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.image_overlay.setPixmap(scaled)
        self.image_overlay.setStyleSheet("background-color: #000000;")
        self.media_info.setText(f"Snapshot: {path.name}")
        self._update_snapshot_nav_buttons()

    def resizeEvent(self, event) -> None:
        """Rescale the current snapshot when the dialog is resized."""
        super().resizeEvent(event)
        if self.preview_stack.currentWidget() == self.image_overlay:
            current_item = self.snap_gallery.currentItem()
            if current_item is not None:
                path_str = current_item.data(Qt.ItemDataRole.UserRole)
                if path_str:
                    self._show_snapshot_image(current_item)

    def closeEvent(self, event) -> None:
        """Stop playback when the dialog closes so audio does not continue."""
        self.player.stop()
        event.accept()
