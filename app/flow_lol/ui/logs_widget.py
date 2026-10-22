"""Live ECG + on-disk log viewer tab with a modern card-based layout."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List

from PyQt6.QtCore import QFileSystemWatcher, Qt
from PyQt6.QtGui import QColor, QPainter, QPen, QTextCursor
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from flow_lol.sensors.buffer import ECGSample
from flow_lol.ui.components import CardWidget, CompactActionBar
from flow_lol.ui.styles import Colors, Spacing
from flow_lol.utils.logging import get_current_log_file
from flow_lol.utils.paths import default_data_dir

logger = logging.getLogger(__name__)


def _resolve_logs_dir(logs_save_path: str | None = None) -> Path:
    """Return the active logs directory from settings or default data dir."""
    if logs_save_path:
        return Path(logs_save_path)
    return default_data_dir() / "logs"


class ECGPlotWidget(QWidget):
    """Simple rolling ECG plot drawn with QPainter.

    Shows the last ``window_seconds`` of samples for one sensor.
    """

    def __init__(self, window_seconds: float = 10.0, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.window_seconds = window_seconds
        self.samples: List[ECGSample] = []
        self.sensor_name: str = ""
        self.setMinimumHeight(180)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"background: {Colors.DARK_PANEL};")

    def set_sensor_name(self, name: str) -> None:
        self.sensor_name = name
        self.update()

    def add_samples(self, samples: List[ECGSample]) -> None:
        if not samples:
            return
        self.samples.extend(samples)
        self._trim()
        self.update()

    def _trim(self) -> None:
        if not self.samples:
            return
        newest = self.samples[-1].timestamp
        cutoff = newest - self.window_seconds
        while self.samples and self.samples[0].timestamp < cutoff:
            self.samples.pop(0)

    def paintEvent(self, event: object) -> None:
        painter = QPainter(self)
        try:
            self._draw(painter)
        finally:
            painter.end()

    def _draw(self, painter: QPainter) -> None:
        width = self.width()
        height = self.height()
        painter.fillRect(0, 0, width, height, QColor(Colors.DARK_PANEL))

        if len(self.samples) < 2:
            painter.setPen(QColor(Colors.TEXT_MUTED))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No ECG data yet.")
            return

        values = [s.value for s in self.samples]
        min_v = min(values)
        max_v = max(values)
        pad = (max_v - min_v) * 0.1 or 1.0
        min_v -= pad
        max_v += pad

        t0 = self.samples[0].timestamp
        t1 = self.samples[-1].timestamp
        duration = max(t1 - t0, 0.001)

        # Grid
        painter.setPen(QPen(QColor(Colors.DARK_PANEL_LIGHT), 1, Qt.PenStyle.DotLine))
        for i in range(1, 5):
            y = int(height * i / 5)
            painter.drawLine(0, y, width, y)

        pen = QPen(QColor(Colors.SUCCESS))
        pen.setWidth(2)
        painter.setPen(pen)

        points: List[tuple[int, int]] = []
        margin = 12
        plot_w = width - 2 * margin
        plot_h = height - 2 * margin
        for s in self.samples:
            x = margin + int(((s.timestamp - t0) / duration) * plot_w)
            y = margin + int(((max_v - s.value) / (max_v - min_v)) * plot_h)
            points.append((x, y))

        for i in range(1, len(points)):
            painter.drawLine(points[i - 1][0], points[i - 1][1], points[i][0], points[i][1])

        painter.setPen(QColor(Colors.TEXT_MUTED))
        painter.drawText(
            margin,
            margin + 12,
            f"{self.sensor_name or 'ECG'} | {len(self.samples)} samples | "
            f"{min_v + pad:.1f} .. {max_v - pad:.1f} µV",
        )


class LogViewerWidget(QWidget):
    """List log files, show their contents, and delete selected files."""

    def __init__(self, parent: QWidget | None = None, logs_dir: Path | None = None) -> None:
        super().__init__(parent)
        self.logs_dir = logs_dir or _resolve_logs_dir()
        self._watched_path: Path | None = None
        self._watcher: QFileSystemWatcher | None = None
        self._last_size = 0
        self._build_ui()
        self.refresh_list()

    def set_logs_dir(self, logs_dir: Path) -> None:
        self.logs_dir = logs_dir
        self.refresh_list()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(Spacing.MD)

        # Left: file list
        left_card = CardWidget("Log files")
        left_layout = left_card.content_layout()

        self.file_list = QListWidget()
        self.file_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.file_list.setAlternatingRowColors(True)
        self.file_list.currentItemChanged.connect(self._on_file_selected)
        left_layout.addWidget(self.file_list)

        actions = CompactActionBar()
        self.refresh_btn = actions.add_button("🔄 Refresh")
        self.refresh_btn.clicked.connect(self.refresh_list)
        self.delete_btn = actions.add_button("🗑 Delete")
        self.delete_btn.setProperty("role", "danger")
        self.delete_btn.clicked.connect(self._delete_selected)
        self.delete_all_btn = actions.add_button("🗑 Delete all")
        self.delete_all_btn.setProperty("role", "danger")
        self.delete_all_btn.clicked.connect(self._delete_all)
        actions.add_stretch()
        left_layout.addWidget(actions)

        left_card.setMaximumWidth(320)
        layout.addWidget(left_card)

        # Right: text viewer
        right_card = CardWidget("Contents")
        self.text_view = QPlainTextEdit()
        self.text_view.setReadOnly(True)
        self.text_view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        right_card.content_layout().addWidget(self.text_view)
        layout.addWidget(right_card, stretch=1)

    def refresh_list(self) -> None:
        self.file_list.clear()
        if not self.logs_dir.exists():
            self.text_view.setPlainText(f"Log directory not found: {self.logs_dir}")
            return

        current_log = get_current_log_file()
        files = sorted(self.logs_dir.glob("*.log"), reverse=True)
        selected_path: Path | None = None
        for path in files:
            is_current = current_log is not None and path == current_log
            text = f"{path.name}  (CURRENT — in use)" if is_current else path.name
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, str(path))
            if is_current:
                item.setToolTip("This log is currently being written by the app; it cannot be deleted while the app is running.")
                item.setForeground(QColor(Colors.PRIMARY))
            self.file_list.addItem(item)

        if self.file_list.count() == 0:
            self.text_view.setPlainText("No .log files found.")
        else:
            self.file_list.setCurrentRow(0)

    def _on_file_selected(self, current: QListWidgetItem | None, previous: QListWidgetItem | None) -> None:
        if current is None:
            return
        path = Path(current.data(Qt.ItemDataRole.UserRole))
        self._watch_file(path)
        self._load_file_text(path)

    def _watch_file(self, path: Path) -> None:
        """Start (or move) a file watcher so new log lines appear automatically."""
        if self._watcher is None:
            self._watcher = QFileSystemWatcher(self)
            self._watcher.fileChanged.connect(self._on_file_changed)

        if self._watched_path is not None and self._watched_path != path:
            self._watcher.removePath(str(self._watched_path))
            self._last_size = 0

        path_str = str(path)
        if self._watched_path != path:
            self._watcher.addPath(path_str)
            self._watched_path = path
            self._last_size = path.stat().st_size if path.exists() else 0

    def _on_file_changed(self, path_str: str) -> None:
        path = Path(path_str)
        if not path.exists():
            return
        current_log = get_current_log_file()
        if current_log is not None and path == current_log:
            self._append_new_lines(path)
        else:
            self._load_file_text(path)

    def _append_new_lines(self, path: Path) -> None:
        try:
            current_size = path.stat().st_size
            if current_size < self._last_size:
                # Log was rotated/truncated; reload fully.
                self._load_file_text(path)
                return
            if current_size == self._last_size:
                return

            with path.open("r", encoding="utf-8", errors="replace") as f:
                f.seek(self._last_size)
                new_text = f.read()

            if new_text:
                self.text_view.moveCursor(QTextCursor.MoveOperation.End)
                self.text_view.insertPlainText(new_text)
                self.text_view.moveCursor(QTextCursor.MoveOperation.End)
            self._last_size = current_size
        except Exception as exc:
            logger.warning("Could not tail log file %s: %s", path, exc)

    def _load_file_text(self, path: Path) -> None:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
            self.text_view.setPlainText(text)
            scrollbar = self.text_view.verticalScrollBar()
            if scrollbar is not None:
                scrollbar.setValue(scrollbar.maximum())
            self._last_size = path.stat().st_size if path.exists() else 0
        except Exception as exc:
            self.text_view.setPlainText(f"Could not read {path}: {exc}")

    def _delete_selected(self) -> None:
        item = self.file_list.currentItem()
        if item is None:
            QMessageBox.information(self, "Delete", "No log file selected.")
            return
        path_str = item.data(Qt.ItemDataRole.UserRole)
        path = Path(path_str)

        current_log = get_current_log_file()
        if current_log is not None and path == current_log:
            QMessageBox.information(
                self,
                "Cannot delete current log",
                "The currently active log file cannot be deleted while the app is running. "
                "Stop the app first, or delete this file after closing Flow-LoL.",
            )
            return

        reply = QMessageBox.question(
            self,
            "Delete log file",
            f"Delete {path.name}?<br>This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            path.unlink()
            self.refresh_list()
            logger.info("Deleted log file %s", path)
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Could not delete file:\n{exc}")
            logger.error("Failed to delete %s: %s", path, exc)

    def _delete_all(self) -> None:
        if not self.logs_dir.exists():
            return
        current_log = get_current_log_file()
        all_files = sorted(self.logs_dir.glob("*.log"))
        deletable = [p for p in all_files if current_log is None or p != current_log]

        if not all_files:
            QMessageBox.information(self, "Delete all logs", "No log files to delete.")
            return
        if not deletable:
            QMessageBox.information(
                self,
                "Delete all logs",
                "Only the currently active log file is present. Stop the app to delete it.",
            )
            return

        reply = QMessageBox.question(
            self,
            "Delete all logs",
            f"Delete {len(deletable)} older log file(s) in {self.logs_dir}?\n"
            "The current log file will be kept because it is still in use.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        deleted = 0
        failed: list[str] = []
        for path in deletable:
            try:
                path.unlink()
                deleted += 1
            except Exception as exc:
                failed.append(f"{path.name}: {exc}")
                logger.error("Failed to delete %s: %s", path, exc)

        self.refresh_list()
        if failed:
            QMessageBox.warning(
                self,
                "Delete all logs",
                f"Deleted {deleted} file(s). {len(failed)} failed:\n" + "\n".join(failed[:5]),
            )
        else:
            QMessageBox.information(
                self,
                "Delete all logs",
                f"Deleted {deleted} older log file(s). The current log was kept.",
            )
        logger.info("Deleted %s log file(s)", deleted)


class LogsWidget(QWidget):
    """Combined live ECG + log viewer tab."""

    def __init__(self, parent: QWidget | None = None, logs_dir: Path | None = None) -> None:
        super().__init__(parent)
        self.logs_dir = logs_dir or _resolve_logs_dir()
        self._build_ui()

    def set_logs_dir(self, logs_dir: Path) -> None:
        self.logs_dir = logs_dir
        self.log_viewer.set_logs_dir(logs_dir)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(Spacing.MD)

        splitter = QSplitter(Qt.Orientation.Vertical)

        ecg_card = CardWidget("Live ECG")
        ecg_layout = ecg_card.content_layout()
        self.ecg_plot = ECGPlotWidget(window_seconds=10.0)
        ecg_layout.addWidget(self.ecg_plot)
        self.ecg_info = QLabel("Sensor: -")
        self.ecg_info.setProperty("role", "muted")
        ecg_layout.addWidget(self.ecg_info)

        logs_card = CardWidget("Application logs")
        logs_layout = logs_card.content_layout()
        self.log_viewer = LogViewerWidget(logs_dir=self.logs_dir)
        logs_layout.addWidget(self.log_viewer)

        splitter.addWidget(ecg_card)
        splitter.addWidget(logs_card)
        splitter.setSizes([320, 380])
        layout.addWidget(splitter)

    def add_samples(self, sensor_name: str, samples: List[ECGSample]) -> None:
        self.ecg_plot.set_sensor_name(sensor_name)
        self.ecg_plot.add_samples(samples)
        self.ecg_info.setText(
            f"Sensor: {sensor_name} | {len(self.ecg_plot.samples)} samples in view"
        )

    def refresh_logs(self) -> None:
        self.log_viewer.refresh_list()
