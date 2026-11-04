"""Post-game dashboard with a modern card-based layout."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import os

from PyQt6.QtCore import QPoint, QRect, QSize, Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap, QPolygon
from PyQt6.QtMultimedia import QMediaPlayer
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSplitter,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
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
    event_clicked = pyqtSignal(object)

    MODE_TIMELINE = "timeline"
    MODE_BLOCKS = "blocks"
    MODE_LINE = "line"
    MODE_SCATTER = "scatter"
    MODE_DISTRIBUTION = "distribution"

    # Symbol types drawn on the graph for each event class.
    EVENT_SYMBOL_KILL = "kill"
    EVENT_SYMBOL_DEATH = "death"
    EVENT_SYMBOL_OBJECTIVE = "objective"

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.predictions: List[Dict[str, Any]] = []
        self.matches: List[Dict[str, Any]] = []
        self.game_events: List[Dict[str, Any]] = []
        self.mode: str = self.MODE_DISTRIBUTION
        self._alternate_shading = False
        self._selected_prediction: Optional[Dict[str, Any]] = None
        self._selected_event: Optional[Dict[str, Any]] = None
        self._t_min = 0.0
        self._t_max = 1.0
        self._mouse_x: Optional[int] = None
        self._hover_pred: Optional[Dict[str, Any]] = None
        self._hover_event: Optional[Dict[str, Any]] = None
        self._visible_match_ids: set[int] = set()
        self._highlight_username: Optional[str] = None
        self._filter_username: Optional[str] = None
        self._show_kills = True
        self._show_deaths = True
        self._show_objectives = False
        self.setMinimumHeight(240)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.CrossCursor)

    def set_event_visibility(
        self,
        kills: Optional[bool] = None,
        deaths: Optional[bool] = None,
        objectives: Optional[bool] = None,
    ) -> None:
        if kills is not None:
            self._show_kills = kills
        if deaths is not None:
            self._show_deaths = deaths
        if objectives is not None:
            self._show_objectives = objectives
        self.update()

    def set_mode(self, mode: str) -> None:
        allowed = (
            self.MODE_TIMELINE,
            self.MODE_BLOCKS,
            self.MODE_LINE,
            self.MODE_SCATTER,
            self.MODE_DISTRIBUTION,
        )
        self.mode = mode if mode in allowed else self.MODE_TIMELINE
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
        self._selected_event = None
        self._visible_match_ids = {m["id"] for m in self.matches}
        self.update()

    def set_visible_matches(self, match_ids: set[int]) -> None:
        """Restrict the timeline to predictions/events inside these matches."""
        self._visible_match_ids = set(match_ids)
        # Keep the selected event if it is still inside the visible range.
        if self._selected_event is not None:
            event_match = self._selected_event.get("match_id")
            if event_match is not None and event_match not in self._visible_match_ids:
                self._selected_event = None
        self.update()

    def visible_match_ids(self) -> set[int]:
        return set(self._visible_match_ids)

    def set_highlight_username(self, username: Optional[str]) -> None:
        """Highlight events where the given player is actor (green) or target (red)."""
        self._highlight_username = username.strip().lower() if username else None
        self.update()

    def set_filter_username(self, username: Optional[str]) -> None:
        """Show only events that involve the selected player (actor or target)."""
        self._filter_username = username.strip().lower() if username else None
        self.update()

    def set_alternate_shading(self, enabled: bool) -> None:
        self._alternate_shading = enabled
        self.update()

    def _visible_predictions(self) -> List[Dict[str, Any]]:
        """Return predictions that fall inside the selected match(es)."""
        if not self._visible_match_ids:
            return self.predictions
        visible = []
        for pred in self.predictions:
            ts = pred.get("timestamp")
            if ts is None:
                continue
            for m in self.matches:
                if m["id"] not in self._visible_match_ids:
                    continue
                started = m.get("started_at")
                ended = m.get("ended_at")
                if started is not None and ts >= started and (ended is None or ts <= ended):
                    visible.append(pred)
                    break
        return visible

    def _visible_events(self) -> List[Dict[str, Any]]:
        """Return game events that fall inside the selected match(es) and player filter."""
        base = []
        if not self._visible_match_ids:
            base = list(self.game_events)
        else:
            for event in self.game_events:
                ts = event.get("timestamp")
                if ts is None:
                    continue
                for m in self.matches:
                    if m["id"] not in self._visible_match_ids:
                        continue
                    started = m.get("started_at")
                    ended = m.get("ended_at")
                    if started is not None and ts >= started and (ended is None or ts <= ended):
                        base.append(event)
                        break

        if not self._filter_username:
            return base
        filtered = []
        for event in base:
            actor = (event.get("actor") or "").lower()
            target = (event.get("target") or "").lower()
            if actor == self._filter_username or target == self._filter_username:
                filtered.append(event)
        return filtered

    def _time_range(self) -> tuple[float, float]:
        preds = self._visible_predictions()
        if preds:
            times = [p["timestamp"] for p in preds]
            t_min, t_max = min(times), max(times)
        elif self._visible_match_ids:
            # No predictions in this match; use the match bounds.
            bounds: list[float] = []
            for m in self.matches:
                if m["id"] in self._visible_match_ids:
                    if m.get("started_at") is not None:
                        bounds.append(m["started_at"])
                    if m.get("ended_at") is not None:
                        bounds.append(m["ended_at"])
            t_min, t_max = (min(bounds), max(bounds)) if bounds else (0.0, 1.0)
        else:
            if self.predictions:
                times = [p["timestamp"] for p in self.predictions]
                t_min, t_max = min(times), max(times)
            else:
                return 0.0, 1.0
        if t_max == t_min:
            t_max = t_min + 1.0
        # Add a small padding so markers at the edges are visible.
        pad = max(1.0, (t_max - t_min) * 0.02)
        return t_min - pad, t_max + pad

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

        visible_preds = self._visible_predictions()
        if not visible_preds:
            painter.setPen(QColor(Colors.TEXT_SECONDARY))
            text = (
                "No predictions in the selected match(es)."
                if self._visible_match_ids
                else "No predictions for this session yet."
            )
            painter.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                text,
            )
            return

        if self.mode == self.MODE_TIMELINE:
            self._draw_timeline(painter, plot_w, plot_h, t_min, t_max, visible_preds)
        elif self.mode == self.MODE_BLOCKS:
            self._draw_blocks(painter, plot_w, plot_h, t_min, t_max, visible_preds)
        elif self.mode == self.MODE_LINE:
            self._draw_line(painter, plot_w, plot_h, t_min, t_max, visible_preds)
        elif self.mode == self.MODE_SCATTER:
            self._draw_scatter(painter, plot_w, plot_h, t_min, t_max, visible_preds)
        elif self.mode == self.MODE_DISTRIBUTION:
            self._draw_distribution(painter, plot_w, plot_h, t_min, t_max, visible_preds)

        self._draw_axis_and_events(painter, plot_w, plot_h, t_min, t_max)
        self._draw_axis_labels(painter, plot_w, plot_h)
        self._draw_selection(painter, plot_w, plot_h, t_min, t_max)
        self._draw_hover_indicator(painter, plot_w, plot_h, t_min, t_max)

    def selected_prediction(self) -> Optional[Dict[str, Any]]:
        return self._selected_prediction

    def set_selected_prediction(self, prediction: Optional[Dict[str, Any]]) -> None:
        self._selected_prediction = prediction
        self._selected_event = None
        if prediction is not None:
            self.selection_changed.emit(prediction)
        self.update()

    def set_selected_event(self, event: Optional[Dict[str, Any]]) -> None:
        """Highlight one event on the graph."""
        self._selected_event = event
        self._selected_prediction = None
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


    def _draw_match_regions(
        self,
        painter: QPainter,
        plot_h: float,
        t_min: float,
        t_max: float,
        plot_w: float,
    ) -> None:
        for match in self.matches:
            if self._visible_match_ids and match.get("id") not in self._visible_match_ids:
                continue
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
        visible_preds: List[Dict[str, Any]],
    ) -> None:
        self._draw_match_regions(painter, plot_h, t_min, t_max, plot_w)
        sorted_preds = sorted(enumerate(visible_preds), key=lambda item: item[1]["timestamp"])
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
        visible_preds: List[Dict[str, Any]],
    ) -> None:
        """Merge consecutive same-label predictions into wide coloured blocks."""
        self._draw_match_regions(painter, plot_h, t_min, t_max, plot_w)
        if not visible_preds:
            return
        sorted_preds = sorted(visible_preds, key=lambda p: p["timestamp"])
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
        visible_preds: List[Dict[str, Any]],
    ) -> None:
        self._draw_match_regions(painter, plot_h, t_min, t_max, plot_w)
        sorted_preds = sorted(visible_preds, key=lambda p: p["timestamp"])
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
        visible_preds: List[Dict[str, Any]],
    ) -> None:
        self._draw_match_regions(painter, plot_h, t_min, t_max, plot_w)
        for pred in visible_preds:
            x = self._x(pred["timestamp"], t_min, t_max, plot_w)
            label = pred.get("ensemble_label", 0)
            y = self.PADDING_TOP + (0.2 * plot_h if label == 1 else 0.8 * plot_h)
            color = QColor(Colors.FLOW) if label == 1 else QColor(Colors.NO_FLOW)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            painter.drawEllipse(int(x - 5), int(y - 5), 10, 10)

    def _draw_distribution(
        self,
        painter: QPainter,
        plot_w: float,
        plot_h: float,
        t_min: float,
        t_max: float,
        visible_preds: List[Dict[str, Any]],
    ) -> None:
        """Smooth "flow intensity" curve over time, like a continuous distribution.

        Each match becomes a hill-shaped flow profile so non-experts can read
        "high = more flow, low = less flow" and see kills/objectives overlaid.
        """
        self._draw_match_regions(painter, plot_h, t_min, t_max, plot_w)
        if not visible_preds:
            return

        sorted_preds = sorted(visible_preds, key=lambda p: p["timestamp"])
        times = [p["timestamp"] for p in sorted_preds]
        labels = [float(p.get("ensemble_label", 0)) for p in sorted_preds]
        duration = max(t_max - t_min, 1.0)
        # Adaptive bandwidth: about 10% of the session length, at least one window step.
        bandwidth = max(duration * 0.10, (times[1] - times[0]) if len(times) > 1 else 30.0)

        path = QPainterPath()
        first_point = True
        for px in range(int(self.PADDING_LEFT), int(self.width() - self.PADDING_RIGHT) + 1):
            t = self._t_from_x(px, t_min, t_max, plot_w)
            num = 0.0
            den = 0.0
            for ti, li in zip(times, labels):
                dt = (t - ti) / bandwidth
                w = 2.718281828 ** (-0.5 * dt * dt)
                num += w * li
                den += w
            intensity = num / den if den > 0 else 0.0
            y = self.PADDING_TOP + (1.0 - intensity) * plot_h
            if first_point:
                path.moveTo(float(px), y)
                first_point = False
            else:
                path.lineTo(float(px), y)

        # Fill the area under the curve with a translucent flow colour.
        fill_path = QPainterPath(path)
        fill_path.lineTo(self.width() - self.PADDING_RIGHT, self.PADDING_TOP + plot_h)
        fill_path.lineTo(self.PADDING_LEFT, self.PADDING_TOP + plot_h)
        fill_path.closeSubpath()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(Colors.FLOW).lighter(120))
        painter.setOpacity(0.35)
        painter.drawPath(fill_path)
        painter.setOpacity(1.0)

        painter.setPen(QPen(QColor(Colors.FLOW), 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)

    def _event_passes_type_filter(self, event: Dict[str, Any]) -> bool:
        """Return True if the event should be drawn given the current toggles.

        When a single player is highlighted, a ChampionKill event is split:
        - actor == highlighted player -> controlled by the Kills toggle
        - target == highlighted player -> controlled by the Deaths toggle
        Otherwise raw event_type maps directly to its toggle.
        """
        event_type = event.get("event_type", "")
        highlight = self._highlight_username
        actor = (event.get("actor") or "").lower()
        target = (event.get("target") or "").lower()
        is_actor = bool(highlight and actor == highlight)
        is_target = bool(highlight and target == highlight)

        if event_type == "kill":
            if highlight:
                if is_actor:
                    return self._show_kills
                if is_target:
                    return self._show_deaths
                # Should not reach here when the player filter is active.
                return self._show_kills
            return self._show_kills
        if event_type == "death":
            return self._show_deaths
        if event_type == "objective":
            return self._show_objectives
        return True

    def _draw_axis_and_events(
        self,
        painter: QPainter,
        plot_w: float,
        plot_h: float,
        t_min: float,
        t_max: float,
    ) -> None:
        """Draw the time axis and render game-event symbols on the graph itself."""
        self._event_positions: list[tuple[Dict[str, Any], QRect]] = []
        visible_events = self._visible_events()

        # Draw one symbol per visible event in a dedicated event lane at the top
        # of the plot so the flow bars stay readable.
        lane_height = 28
        lane_top = self.PADDING_TOP + 6
        for event in visible_events:
            t = event.get("timestamp")
            if t is None:
                continue
            if not self._event_passes_type_filter(event):
                continue
            etype = event.get("event_type", "")
            x = int(self._x(t, t_min, t_max, plot_w))
            if x < self.PADDING_LEFT or x > self.width() - self.PADDING_RIGHT:
                continue
            y = lane_top + self._event_lane_offset(etype, event) * lane_height
            rect = QRect(x - 9, y - 9, 18, 18)
            self._event_positions.append((event, rect))
            self._draw_event_symbol(painter, rect, event, event == self._selected_event)

        # Axis line
        y_axis = self.PADDING_TOP + int(plot_h)
        painter.setPen(QPen(QColor(Colors.TEXT_MUTED), 1))
        painter.drawLine(self.PADDING_LEFT, y_axis, self.width() - self.PADDING_RIGHT, y_axis)

        # Time labels
        painter.setPen(QColor(Colors.TEXT_SECONDARY))
        for label_t in [t_min, (t_min + t_max) / 2, t_max]:
            txt = datetime.fromtimestamp(label_t).strftime("%H:%M:%S")
            x = self._x(label_t, t_min, t_max, plot_w)
            painter.drawText(int(x - 30), y_axis + 20, 60, 20, Qt.AlignmentFlag.AlignCenter, txt)

    def _event_lane_offset(self, event_type: str, event: Dict[str, Any]) -> int:
        """Return which event lane (0..2) an event lives in.

        When a player is highlighted and they were the victim of a kill,
        place that symbol in the death lane so the K/D lanes stay meaningful.
        """
        highlight = self._highlight_username
        if highlight and event_type == "kill":
            target = (event.get("target") or "").lower()
            if target == highlight:
                return 1
        return {
            "kill": 0,
            "death": 1,
            "objective": 2,
        }.get(event_type, 2)

    def _draw_event_symbol(
        self,
        painter: QPainter,
        rect: QRect,
        event: Dict[str, Any],
        selected: bool,
    ) -> None:
        """Draw a readable symbol for a kill, death, or objective.

        When a player is selected, symbols show the selected player's role:
        - K in green: selected player scored a kill / was the actor
        - D in red: selected player was killed / was the target
        Otherwise the symbol shows the raw event type (K/D/O).
        """
        event_type = event.get("event_type", "")
        event_colors = {
            "kill": QColor(Colors.SUCCESS),
            "death": QColor(Colors.DANGER),
            "objective": QColor(Colors.PRIMARY),
        }
        cx, cy = rect.center().x(), rect.center().y()

        highlight = self._highlight_username
        actor = (event.get("actor") or "").lower()
        target = (event.get("target") or "").lower()
        is_actor = bool(highlight and actor == highlight)
        is_target = bool(highlight and target == highlight)

        # Default symbol from event type.
        base_color = event_colors.get(event_type, QColor(Colors.WARNING))
        label = {"kill": "K", "death": "D", "objective": "O"}.get(event_type, "?")

        # When a player is selected and this kill/death event involves them,
        # change the symbol to show their role. Objectives stay blue O.
        # For kills: actor = killer (green K), target = victim (red D).
        # For deaths: actor = the player who died (red D).
        if event_type == "kill" and is_actor:
            base_color = QColor(Colors.SUCCESS)
            label = "K"
        elif event_type == "kill" and is_target:
            base_color = QColor(Colors.DANGER)
            label = "D"
        elif event_type == "death" and is_actor:
            base_color = QColor(Colors.DANGER)
            label = "D"

        # Selection ring.
        if selected:
            painter.setPen(QPen(QColor(Colors.WARNING), 3))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(rect.adjusted(-3, -3, 3, 3))

        # Symbol background.
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(base_color)
        painter.drawEllipse(rect)

        # Inner letter/icon label.
        font = painter.font()
        font.setBold(True)
        font.setPointSize(8)
        painter.setFont(font)
        painter.setPen(QPen(QColor(Colors.SURFACE), 1))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, label)

    def _draw_axis_labels(
        self,
        painter: QPainter,
        plot_w: float,
        plot_h: float,
    ) -> None:
        """Draw X and Y axis titles."""
        painter.setPen(QColor(Colors.TEXT_SECONDARY))
        font = painter.font()
        font.setPointSize(9)
        painter.setFont(font)

        # X-axis label (below the axis line, outside the plot area).
        x_label = "Time"
        painter.setPen(QColor(Colors.TEXT_SECONDARY))
        painter.drawText(
            int(self.PADDING_LEFT + plot_w / 2 - 30),
            self.height() - 6,
            60,
            16,
            Qt.AlignmentFlag.AlignCenter,
            x_label,
        )

        # Y-axis label, rotated
        painter.save()
        painter.translate(12, int(self.PADDING_TOP + plot_h / 2))
        painter.rotate(-90)
        painter.setPen(QColor(Colors.TEXT_SECONDARY))
        painter.drawText(-60, 0, 120, 16, Qt.AlignmentFlag.AlignCenter, "Flow state")
        painter.restore()

    def _event_at(self, x: int, y: int) -> Optional[Dict[str, Any]]:
        """Return the visible event whose symbol contains the given point."""
        for event, rect in getattr(self, "_event_positions", []):
            if rect.contains(x, y):
                return event
        return None

    def _prediction_at_x(self, x: float) -> tuple[Optional[Dict[str, Any]], float]:
        """Return the prediction nearest to the given mouse x and the time there."""
        width, _, plot_w, _ = self._geometry()
        visible_preds = self._visible_predictions()
        if not visible_preds or plot_w <= 0 or x < self.PADDING_LEFT or x > width - self.PADDING_RIGHT:
            return None, 0.0
        t_min, t_max = self._time_range()
        t = self._t_from_x(x, t_min, t_max, plot_w)
        nearest = min(visible_preds, key=lambda p: abs(p["timestamp"] - t))
        # Accept clicks/hovers within ~1.5 average inter-prediction gaps.
        threshold = max(15.0, (t_max - t_min) / max(1, len(visible_preds)) * 1.5)
        if abs(nearest["timestamp"] - t) <= threshold:
            return nearest, t
        return None, t

    def mouseMoveEvent(self, event) -> None:
        x = int(event.position().x())
        y = int(event.position().y())
        self._mouse_x = x
        hover_event = self._event_at(x, y)
        self._hover_event = hover_event
        if hover_event is not None:
            ts = hover_event["timestamp"]
            etype = hover_event.get("event_type", "event")
            actor = hover_event.get("actor") or "?"
            target = hover_event.get("target") or ""
            desc = f"{datetime.fromtimestamp(ts).strftime('%H:%M:%S')} – {etype}"
            if target:
                desc += f": {actor} → {target}"
            else:
                desc += f": {actor}"
            self.setToolTip(f"{desc}\nClick to highlight")
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            self._hover_pred = None
        else:
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
        x = int(event.position().x())
        y = int(event.position().y())
        event_hit = self._event_at(x, y)
        if event_hit is not None:
            self.set_selected_event(event_hit)
            self.event_clicked.emit(event_hit)
            return
        pred, _ = self._prediction_at_x(x)
        if pred is not None:
            self.set_selected_prediction(pred)
            self.prediction_clicked.emit(pred)


class LegendToggle(QWidget):
    """Colored event symbol + text label + on/off switch for the timeline legend."""

    toggled = pyqtSignal(bool)

    def __init__(
        self,
        text: str,
        event_type: str,
        checked: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.symbol_label = QLabel()
        self.symbol_label.setPixmap(self._symbol_pixmap(event_type))
        layout.addWidget(self.symbol_label)

        self.text_label = QLabel(text)
        self.text_label.setProperty("role", "muted")
        layout.addWidget(self.text_label)

        self.switch = Switch(checked=checked)
        self.switch.toggled.connect(self.toggled.emit)
        layout.addWidget(self.switch)

    @staticmethod
    def _symbol_pixmap(event_type: str, size: int = 16) -> QPixmap:
        """Draw the same K/D/O circle symbol used on the graph."""
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        color = {
            "kill": QColor(Colors.SUCCESS),
            "death": QColor(Colors.DANGER),
            "objective": QColor(Colors.PRIMARY),
        }.get(event_type, QColor(Colors.WARNING))
        letter = {"kill": "K", "death": "D", "objective": "O"}.get(event_type, "?")

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        painter.drawEllipse(0, 0, size, size)

        font = painter.font()
        font.setBold(True)
        font.setPointSize(7)
        painter.setFont(font)
        painter.setPen(QPen(QColor(Colors.SURFACE), 1))
        painter.drawText(QRect(0, 0, size, size), Qt.AlignmentFlag.AlignCenter, letter)
        painter.end()
        return pixmap


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
        self._current_game_events: List[Dict[str, Any]] = []
        self._graph_expanded = False
        self._normal_splitter_sizes: List[int] = [520, 450]

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
        self.view_combo.addItem("Flow distribution", FlowTimelineWidget.MODE_DISTRIBUTION)
        self.view_combo.setCurrentIndex(self.view_combo.count() - 1)
        self.view_combo.currentIndexChanged.connect(self._on_view_mode_changed)
        view_row.addWidget(self.view_combo)

        view_row.addWidget(QLabel("Match:"))
        self.match_combo = QComboBox()
        self.match_combo.setMinimumWidth(180)
        self.match_combo.currentIndexChanged.connect(self._on_match_combo_changed)
        view_row.addWidget(self.match_combo)

        view_row.addWidget(QLabel("Player:"))
        self.player_filter_combo = QComboBox()
        self.player_filter_combo.setMinimumWidth(140)
        self.player_filter_combo.setToolTip("Show only events involving this player")
        self.player_filter_combo.currentIndexChanged.connect(self._on_player_filter_changed)
        view_row.addWidget(self.player_filter_combo)

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
        self.nav_row_widget = QWidget()
        self.nav_row_widget.setLayout(nav_row)
        layout.addWidget(self.nav_row_widget)

        # Content splitter
        self.splitter = QSplitter(Qt.Orientation.Horizontal)

        # Timeline card with inline zoom button
        timeline_card = CardWidget()  # title built manually with toggle switches
        timeline_container = QWidget()
        timeline_container_layout = QVBoxLayout(timeline_container)
        timeline_container_layout.setContentsMargins(0, 0, 0, 0)
        timeline_container_layout.setSpacing(0)

        # Header with title + kill/death/objective toggle switches
        timeline_header = QHBoxLayout()
        timeline_title = QLabel("Flow timeline")
        timeline_title.setProperty("role", "heading")
        timeline_header.addWidget(timeline_title)
        timeline_header.addStretch()

        self.kill_switch = self._make_legend_switch("Kills", FlowTimelineWidget.EVENT_SYMBOL_KILL)
        self.death_switch = self._make_legend_switch("Deaths", FlowTimelineWidget.EVENT_SYMBOL_DEATH)
        self.objective_switch = self._make_legend_switch("Objectives", FlowTimelineWidget.EVENT_SYMBOL_OBJECTIVE)
        self.objective_switch.switch.setChecked(False)
        # Deaths only exist relative to a selected player; hide the toggle in All-players mode.
        self.death_switch.setVisible(False)
        timeline_header.addWidget(self.kill_switch)
        timeline_header.addSpacing(12)
        timeline_header.addWidget(self.death_switch)
        timeline_header.addSpacing(12)
        timeline_header.addWidget(self.objective_switch)
        timeline_card.content_layout().addLayout(timeline_header)

        self.timeline = FlowTimelineWidget()
        self.timeline.prediction_clicked.connect(self._on_prediction_clicked)
        self.timeline.selection_changed.connect(self._on_timeline_selection_changed)
        self.timeline.event_clicked.connect(self._on_timeline_event_clicked)
        timeline_container_layout.addWidget(self.timeline, stretch=1)

        self.kill_switch.toggled.connect(lambda checked: (self.timeline.set_event_visibility(kills=checked), self._refresh_event_list()))
        self.death_switch.toggled.connect(lambda checked: (self.timeline.set_event_visibility(deaths=checked), self._refresh_event_list()))
        self.objective_switch.toggled.connect(lambda checked: (self.timeline.set_event_visibility(objectives=checked), self._refresh_event_list()))

        zoom_bar = QHBoxLayout()
        zoom_bar.addStretch()
        self.expand_graph_btn = QPushButton("⛶")
        self.expand_graph_btn.setProperty("role", "icon")
        self.expand_graph_btn.setToolTip("Expand / shrink the graph")
        self.expand_graph_btn.setFixedSize(32, 32)
        self.expand_graph_btn.clicked.connect(self._toggle_graph_expansion)
        zoom_bar.addWidget(self.expand_graph_btn)
        timeline_container_layout.addLayout(zoom_bar)

        # Event summary lives under the graph and is only shown when a player is selected.
        self.events_container = QWidget()
        events_container_layout = QVBoxLayout(self.events_container)
        events_container_layout.setContentsMargins(0, 0, 0, 0)
        events_container_layout.setSpacing(4)
        events_label = QLabel("Game events")
        events_label.setProperty("role", "muted")
        events_container_layout.addWidget(events_label)

        self.event_table = QTableWidget()
        self.event_table.setColumnCount(3)
        self.event_table.setHorizontalHeaderLabels(["Time", "Type", "Details"])
        self.event_table.horizontalHeader().setStretchLastSection(True)
        self.event_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.event_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.event_table.setAlternatingRowColors(True)
        self.event_table.setMinimumHeight(90)
        self.event_table.setMaximumHeight(160)
        self.event_table.setColumnWidth(0, 70)
        self.event_table.setColumnWidth(1, 80)
        self.event_table.itemClicked.connect(self._on_event_table_clicked)
        self.event_table.itemDoubleClicked.connect(self._on_event_table_double_clicked)
        events_container_layout.addWidget(self.event_table)
        self.events_container.setVisible(False)
        timeline_container_layout.addWidget(self.events_container)

        timeline_card.content_layout().addWidget(timeline_container)
        self.splitter.addWidget(timeline_card)

        # Details card (scrollable so long session details are always readable)
        details_card = CardWidget("Session details")
        details_scroll = QScrollArea()
        details_scroll.setWidgetResizable(True)
        details_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        details_widget = QWidget()
        details_layout = QVBoxLayout(details_widget)
        details_layout.setSpacing(Spacing.SM)

        self.details_label = QLabel("Select a session to see details.")
        self.details_label.setWordWrap(True)
        self.details_label.setProperty("role", "muted")
        details_layout.addWidget(self.details_label)

        details_layout.addWidget(QLabel("Replays"))
        self.replay_list = QListWidget()
        self.replay_list.setAlternatingRowColors(True)
        self.replay_list.setMinimumHeight(100)
        details_layout.addWidget(self.replay_list, stretch=1)

        self.open_replay_btn = QPushButton("▶ Open selected replay")
        self.open_replay_btn.clicked.connect(self._open_selected_replay)
        self.open_replay_btn.setEnabled(False)
        details_layout.addWidget(self.open_replay_btn)

        details_scroll.setWidget(details_widget)
        details_card.content_layout().addWidget(details_scroll)

        self.splitter.addWidget(details_card)
        self.splitter.setSizes([520, 450])
        layout.addWidget(self.splitter, stretch=1)

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
            self.match_combo.clear()
            self.match_combo.setEnabled(False)
            self.event_table.setRowCount(0)
            self.events_container.setVisible(False)
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

        # Match dropdown: "All matches" first, then each match.
        self.match_combo.clear()
        self.match_combo.addItem("All matches", -1)
        self._match_rows: List[Dict[str, Any]] = matches
        for m in matches:
            start = datetime.fromtimestamp(m["started_at"]).strftime("%H:%M:%S")
            end = "running" if m["ended_at"] is None else datetime.fromtimestamp(m["ended_at"]).strftime("%H:%M:%S")
            detected = "auto" if m["detected"] else "manual"
            rec = ""
            if m.get("notes"):
                rec = f" | {m['notes']}"
            text = f"{m['game_mode']} – {start} → {end} ({detected}){rec}"
            self.match_combo.addItem(text, m["id"])
        self.match_combo.setEnabled(len(matches) > 0)

        # Store full session events and initialize the player list with all players.
        self._current_game_events = list(game_events)
        self._refresh_player_list(all_matches=True)

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
            f"Started: {datetime.fromtimestamp(session['started_at']).strftime('%Y-%m-%d %H:%M:%S')}<br>"
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
        # Default to "All matches" and refresh the event list / timeline filter.
        self._on_match_combo_changed(0)
        self._update_selection_ui()

    @staticmethod
    def _format_duration(seconds: float) -> str:
        """Format seconds as hours/minutes/seconds depending on length."""
        s = max(0, int(round(seconds)))
        hours = s // 3600
        minutes = (s % 3600) // 60
        secs = s % 60
        if hours:
            return f"{hours}h {minutes}m {secs:02d}s"
        return f"{minutes}m {secs:02d}s"

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

    def _inspect_nearest_prediction(self, timestamp: Optional[float]) -> None:
        """Select the prediction window closest to the given timestamp and open the inspect popup."""
        if not self._sorted_predictions or timestamp is None:
            return
        nearest = min(
            self._sorted_predictions,
            key=lambda p: abs(p.get("timestamp", 0.0) - timestamp),
        )
        if not nearest:
            return
        for i, p in enumerate(self._sorted_predictions):
            if p["timestamp"] == nearest["timestamp"]:
                self._selected_index = i
                break
        self.timeline.set_selected_prediction(nearest)
        self._update_selection_ui()
        self._on_prediction_clicked(nearest)

    def _on_alternate_toggled(self, enabled: bool) -> None:
        self.timeline.set_alternate_shading(enabled)

    def _on_player_filter_changed(self, index: int) -> None:
        """Filter events to the selected player and highlight them."""
        username = self.player_filter_combo.itemData(index)
        if username:
            self.timeline.set_filter_username(username)
            self.timeline.set_highlight_username(username)
        else:
            self.timeline.set_filter_username(None)
            self.timeline.set_highlight_username(None)
        # The Deaths toggle only makes sense when a single player is selected,
        # because globally a ChampionKill is just a kill (actor + victim).
        self.death_switch.setVisible(bool(username))
        self._refresh_event_list()

    def _toggle_graph_expansion(self) -> None:
        """Expand the graph to hide the details panel, or restore it."""
        self._graph_expanded = not self._graph_expanded
        if self._graph_expanded:
            self._normal_splitter_sizes = list(self.splitter.sizes())
            # Hide the right (details) panel and the nav row below the graph.
            self.splitter.setSizes([self.splitter.width(), 0])
            self.nav_row_widget.setVisible(False)
            self.timeline.setMinimumHeight(360)
            self.expand_graph_btn.setText("🗗")
            self.expand_graph_btn.setToolTip("Shrink the graph")
        else:
            total = max(1, sum(self.splitter.sizes()))
            left = self._normal_splitter_sizes[0]
            right = self._normal_splitter_sizes[1]
            scale = total / max(1, left + right)
            self.splitter.setSizes([int(left * scale), int(right * scale)])
            self.nav_row_widget.setVisible(True)
            self.timeline.setMinimumHeight(240)
            self.expand_graph_btn.setText("⛶")
            self.expand_graph_btn.setToolTip("Expand the graph")

    def _refresh_player_list(self, all_matches: bool = False) -> None:
        """Rebuild the player dropdown from the selected match (or whole session)."""
        match_id = self.match_combo.itemData(self.match_combo.currentIndex())
        events = list(self._current_game_events)
        if not all_matches and match_id != -1:
            events = [e for e in events if e.get("match_id") == match_id]

        # Compute K/D counts per player.
        stats: Dict[str, Dict[str, int]] = {}
        for e in events:
            actor = (e.get("actor") or "").lower()
            target = (e.get("target") or "").lower()
            etype = e.get("event_type", "")
            if actor:
                stats.setdefault(actor, {"kills": 0, "deaths": 0})
                if etype == "kill":
                    stats[actor]["kills"] += 1
                elif etype == "death":
                    stats[actor]["deaths"] += 1
            if target:
                stats.setdefault(target, {"kills": 0, "deaths": 0})
                if etype == "kill":
                    stats[target]["deaths"] += 1
                elif etype == "death":
                    stats[target]["kills"] += 1

        players = sorted(stats.keys())

        # Preserve current selection if the player is still in the new list.
        current = self.player_filter_combo.itemData(self.player_filter_combo.currentIndex())
        self.player_filter_combo.clear()
        self.player_filter_combo.addItem("All players", None)
        for p in players:
            kills = stats[p]["kills"]
            deaths = stats[p]["deaths"]
            text = f"{p} (K:{kills} D:{deaths})"
            self.player_filter_combo.addItem(text, p)
        if current and current in players:
            idx = self.player_filter_combo.findData(current)
            self.player_filter_combo.setCurrentIndex(max(0, idx))
        else:
            self.player_filter_combo.setCurrentIndex(0)

    def _on_match_combo_changed(self, index: int) -> None:
        """Filter the timeline and event list to the selected match."""
        if self._current_session_id is None or index < 0:
            return
        match_id = self.match_combo.itemData(index)
        if match_id == -1:
            self.timeline.set_visible_matches({m["id"] for m in self._match_rows})
        elif isinstance(match_id, int):
            self.timeline.set_visible_matches({match_id})
        else:
            self.timeline.set_visible_matches(set())
        self._refresh_player_list(all_matches=(match_id == -1))
        self._refresh_event_list()

        # Update replay list for the selected match as well.
        replays = self.repo.get_replays(
            self._current_session_id,
            match_id=match_id if isinstance(match_id, int) and match_id != -1 else None,
        )
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
            self.replay_list.addItem(
                "No replays linked" if match_id == -1 else "No replays linked to this match"
            )

    def _table_events(self) -> List[Dict[str, Any]]:
        """Return the exact events currently shown in the table under the graph.

        Applies match filter, player filter, and kill/death/objective toggles.
        """
        match_id = self.match_combo.itemData(self.match_combo.currentIndex())
        username = self.player_filter_combo.itemData(self.player_filter_combo.currentIndex())
        if not username:
            return []

        events = list(self._current_game_events)
        if match_id != -1:
            events = [e for e in events if e.get("match_id") == match_id]
        username = username.lower()
        events = [
            e for e in events
            if (e.get("actor") or "").lower() == username
            or (e.get("target") or "").lower() == username
        ]

        # Apply the same kill/death/objective toggles that govern the graph.
        filtered: List[Dict[str, Any]] = []
        for e in events:
            etype = e.get("event_type", "")
            is_actor = (e.get("actor") or "").lower() == username
            is_target = (e.get("target") or "").lower() == username
            if etype == "kill":
                if is_actor and not self.timeline._show_kills:
                    continue
                if is_target and not self.timeline._show_deaths:
                    continue
            elif etype == "death" and not self.timeline._show_deaths:
                continue
            elif etype == "objective" and not self.timeline._show_objectives:
                continue
            filtered.append(e)
        return filtered

    def _refresh_event_list(self) -> None:
        """Repopulate the event table respecting the current match and player filters."""
        username = self.player_filter_combo.itemData(self.player_filter_combo.currentIndex())
        self.events_container.setVisible(bool(username))
        if not username:
            return

        filtered = self._table_events()
        self.event_table.setRowCount(len(filtered))
        for row, e in enumerate(filtered):
            t_item = QTableWidgetItem(datetime.fromtimestamp(e["timestamp"]).strftime("%H:%M:%S"))
            type_item = QTableWidgetItem(e.get("event_type", "").capitalize())
            actor = e.get("actor") or "?"
            target = e.get("target") or ""
            details = f"{actor} → {target}" if target else actor
            details_item = QTableWidgetItem(details)
            t_item.setData(Qt.ItemDataRole.UserRole, id(e))
            type_item.setData(Qt.ItemDataRole.UserRole, id(e))
            details_item.setData(Qt.ItemDataRole.UserRole, id(e))
            self.event_table.setItem(row, 0, t_item)
            self.event_table.setItem(row, 1, type_item)
            self.event_table.setItem(row, 2, details_item)
        if not filtered:
            self.event_table.setRowCount(1)
            for col in range(3):
                item = QTableWidgetItem("No game events match the current filters")
                item.setFlags(Qt.ItemFlag.ItemIsEnabled)
                self.event_table.setItem(0, col, item)

    def _event_description(self, e: Dict[str, Any]) -> str:
        t = datetime.fromtimestamp(e["timestamp"]).strftime("%H:%M:%S")
        actor = e.get("actor") or "?"
        target = e.get("target") or ""
        desc = f"{t} – {e['event_type']}"
        if target:
            desc += f": {actor} → {target}"
        else:
            desc += f": {actor}"
        return desc

    def _on_event_table_clicked(self, item: QTableWidgetItem) -> None:
        """When the user clicks a row in the event table, highlight it on the graph."""
        row = item.row()
        events = self._table_events()
        if row < len(events):
            self.timeline.set_selected_event(events[row])

    def _on_event_table_double_clicked(self, item: QTableWidgetItem) -> None:
        """Double-click an event row: jump to the nearest prediction window and inspect it."""
        row = item.row()
        events = self._table_events()
        if row >= len(events):
            return
        event = events[row]
        self._inspect_nearest_prediction(event.get("timestamp"))

    def _on_timeline_event_clicked(self, event: Dict[str, Any]) -> None:
        """When the user clicks an event symbol on the graph, select it in the table."""
        match_id = event.get("match_id")
        if match_id is not None:
            idx = self.match_combo.findData(match_id)
            if idx >= 0:
                self.match_combo.setCurrentIndex(idx)
        # Make sure the table is visible and populated. If no player is selected,
        # pick the actor/target of this event automatically.
        username = self.player_filter_combo.itemData(self.player_filter_combo.currentIndex())
        actor = (event.get("actor") or "").lower()
        target = (event.get("target") or "").lower()
        if not username and (actor or target):
            chosen = actor or target
            idx = self.player_filter_combo.findData(chosen)
            if idx >= 0:
                self.player_filter_combo.setCurrentIndex(idx)
            else:
                # Player not in the list for the current match; fall back to all matches.
                self._refresh_player_list(all_matches=True)
                idx = self.player_filter_combo.findData(chosen)
                if idx >= 0:
                    self.player_filter_combo.setCurrentIndex(idx)

        events = self._table_events()
        for row, e in enumerate(events):
            if e is event:
                self.event_table.selectRow(row)
                break

    def _open_fullscreen_graph(self) -> None:
        """Open a maximized window with the graph, session/match dropdowns and event list."""
        session_id = self._current_session_id
        if session_id is None:
            QMessageBox.information(self, "Fullscreen graph", "Select a session first.")
            return
        dialog = FullscreenGraphDialog(
            repo=self.repo,
            sessions=self._sessions,
            current_session_id=session_id,
            current_match_id=self.match_combo.itemData(self.match_combo.currentIndex()),
            webcam_dir=self.webcam_dir,
            parent=self,
        )
        dialog.exec()

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

    def _make_legend_switch(
        self,
        label: str,
        event_type: str,
    ) -> LegendToggle:
        """Create a colored K/D/O symbol + label + Switch for the timeline legend."""
        return LegendToggle(label, event_type, checked=True)


class FullscreenGraphDialog(QDialog):
    """Maximized timeline with session/match selectors and event list."""

    def __init__(
        self,
        repo: SessionRepository,
        sessions: List[Dict[str, Any]],
        current_session_id: int,
        current_match_id: int | None,
        webcam_dir: Path,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Flow-LoL – Fullscreen graph")
        self.setWindowState(Qt.WindowState.WindowMaximized)
        self.setMinimumSize(900, 600)
        self.repo = repo
        self._sessions = sessions
        self._webcam_dir = webcam_dir
        self._current_match_id = current_match_id if current_match_id not in (None, -1) else None
        self._game_events: List[Dict[str, Any]] = []

        layout = QVBoxLayout(self)
        layout.setSpacing(Spacing.MD)

        # Top bar: session + match selectors.
        top_bar = QHBoxLayout()
        top_bar.setSpacing(Spacing.MD)
        top_bar.addWidget(QLabel("Session:"))
        self.session_combo = QComboBox()
        self.session_combo.setMinimumWidth(260)
        for s in sessions:
            started = datetime.fromtimestamp(s["started_at"]).strftime("%Y-%m-%d %H:%M")
            ended = " (running)" if s["ended_at"] is None else ""
            self.session_combo.addItem(f"{started} – session {s['id']}{ended}", s["id"])
        idx = self.session_combo.findData(current_session_id)
        self.session_combo.setCurrentIndex(max(0, idx))
        self.session_combo.currentIndexChanged.connect(self._on_session_changed)
        top_bar.addWidget(self.session_combo, stretch=2)

        top_bar.addWidget(QLabel("Match:"))
        self.match_combo = QComboBox()
        self.match_combo.setMinimumWidth(220)
        self.match_combo.currentIndexChanged.connect(self._on_match_changed)
        top_bar.addWidget(self.match_combo, stretch=1)

        self.view_combo = QComboBox()
        self.view_combo.addItem("Timeline (bars)", FlowTimelineWidget.MODE_TIMELINE)
        self.view_combo.addItem("Blocks", FlowTimelineWidget.MODE_BLOCKS)
        self.view_combo.addItem("Line graph", FlowTimelineWidget.MODE_LINE)
        self.view_combo.addItem("Scatter", FlowTimelineWidget.MODE_SCATTER)
        self.view_combo.addItem("Flow distribution", FlowTimelineWidget.MODE_DISTRIBUTION)
        self.view_combo.setCurrentIndex(self.view_combo.count() - 1)
        self.view_combo.currentIndexChanged.connect(self._on_view_changed)
        top_bar.addWidget(QLabel("View:"))
        top_bar.addWidget(self.view_combo)

        self.fs_kill_switch = self._make_fs_legend_switch("Kills", FlowTimelineWidget.EVENT_SYMBOL_KILL)
        self.fs_objective_switch = self._make_fs_legend_switch("Objectives", FlowTimelineWidget.EVENT_SYMBOL_OBJECTIVE)
        self.fs_objective_switch.switch.setChecked(False)
        top_bar.addSpacing(12)
        top_bar.addWidget(self.fs_kill_switch)
        top_bar.addSpacing(12)
        top_bar.addWidget(self.fs_objective_switch)

        close_btn = QPushButton("✕ Close")
        close_btn.clicked.connect(self.accept)
        top_bar.addWidget(close_btn)
        layout.addLayout(top_bar)

        # Main area: big timeline + event list on the right.
        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.timeline = FlowTimelineWidget()
        self.timeline.setMinimumHeight(360)
        self.timeline.event_clicked.connect(self._on_timeline_event_clicked)
        splitter.addWidget(self.timeline)

        self.fs_kill_switch.toggled.connect(lambda checked: self.timeline.set_event_visibility(kills=checked))
        self.fs_objective_switch.toggled.connect(lambda checked: self.timeline.set_event_visibility(objectives=checked))

        events_card = CardWidget("Game events")
        events_layout = events_card.content_layout()
        self.event_list = QListWidget()
        self.event_list.setAlternatingRowColors(True)
        self.event_list.itemClicked.connect(self._on_event_list_clicked)
        events_layout.addWidget(self.event_list)
        splitter.addWidget(events_card)
        splitter.setSizes([800, 300])
        layout.addWidget(splitter, stretch=1)

        self._load_session(current_session_id, select_match_id=self._current_match_id)

    def _load_session(self, session_id: int, select_match_id: int | None = None) -> None:
        self._current_session_id = session_id
        predictions = self.repo.get_predictions(session_id)
        matches = self.repo.get_matches(session_id)
        self._game_events = self.repo.get_game_events(session_id)

        self.match_combo.clear()
        self.match_combo.addItem("All matches", -1)
        for m in matches:
            start = datetime.fromtimestamp(m["started_at"]).strftime("%H:%M:%S")
            end = "running" if m["ended_at"] is None else datetime.fromtimestamp(m["ended_at"]).strftime("%H:%M:%S")
            self.match_combo.addItem(f"{m['game_mode']} – {start} → {end}", m["id"])

        if select_match_id is not None:
            idx = self.match_combo.findData(select_match_id)
            if idx >= 0:
                self.match_combo.setCurrentIndex(idx)
            else:
                self.match_combo.setCurrentIndex(0)
        else:
            self.match_combo.setCurrentIndex(0)

        self.timeline.set_data(predictions, matches, self._game_events)
        self._refresh_event_list()

    def _on_session_changed(self, index: int) -> None:
        session_id = self.session_combo.itemData(index)
        if isinstance(session_id, int):
            self._load_session(session_id)

    def _on_match_changed(self, index: int) -> None:
        match_id = self.match_combo.itemData(index)
        if match_id == -1:
            self.timeline.set_visible_matches({m["id"] for m in self.repo.get_matches(self._current_session_id)})
        elif isinstance(match_id, int):
            self.timeline.set_visible_matches({match_id})
        self._refresh_event_list()

    def _on_view_changed(self, index: int) -> None:
        mode = self.view_combo.itemData(index)
        if mode:
            self.timeline.set_mode(str(mode))

    def _refresh_event_list(self) -> None:
        self.event_list.clear()
        match_id = self.match_combo.itemData(self.match_combo.currentIndex())
        events = (
            list(self._game_events)
            if match_id == -1
            else [e for e in self._game_events if e.get("match_id") == match_id]
        )
        for e in events:
            self.event_list.addItem(self._event_description(e))
        if not events:
            self.event_list.addItem(
                "No game events recorded"
                if match_id == -1
                else "No game events recorded for this match"
            )

    def _event_description(self, e: Dict[str, Any]) -> str:
        t = datetime.fromtimestamp(e["timestamp"]).strftime("%H:%M:%S")
        actor = e.get("actor") or "?"
        target = e.get("target") or ""
        desc = f"{t} – {e['event_type']}"
        if target:
            desc += f": {actor} → {target}"
        else:
            desc += f": {actor}"
        return desc

    def _on_event_list_clicked(self, item: QListWidgetItem) -> None:
        row = self.event_list.row(item)
        if row < 0:
            return
        match_id = self.match_combo.itemData(self.match_combo.currentIndex())
        events = (
            list(self._game_events)
            if match_id == -1
            else [e for e in self._game_events if e.get("match_id") == match_id]
        )
        if row < len(events):
            self.timeline.set_selected_event(events[row])

    def _on_timeline_event_clicked(self, event: Dict[str, Any]) -> None:
        match_id = event.get("match_id")
        if match_id is not None:
            idx = self.match_combo.findData(match_id)
            if idx >= 0:
                self.match_combo.setCurrentIndex(idx)
        for i in range(self.event_list.count()):
            item = self.event_list.item(i)
            if item is None:
                continue
            visible_match_id = self.match_combo.itemData(self.match_combo.currentIndex())
            events = (
                list(self._game_events)
                if visible_match_id == -1
                else [e for e in self._game_events if e.get("match_id") == match_id]
            )
            row = self.event_list.row(item)
            if row < len(events) and events[row] is event:
                self.event_list.setCurrentItem(item)
                break

    def _make_fs_legend_switch(
        self,
        label: str,
        event_type: str,
    ) -> LegendToggle:
        """Create a colored K/D/O symbol + label + Switch for the fullscreen timeline legend."""
        return LegendToggle(label, event_type, checked=True)


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
