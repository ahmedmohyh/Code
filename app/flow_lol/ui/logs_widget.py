"""Live logs tab: real-time ECG signal + on-disk log file viewer."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from flow_lol.sensors.buffer import ECGSample
from flow_lol.utils.paths import default_data_dir

logger = logging.getLogger(__name__)


class ECGPlotWidget(QWidget):
    """Simple rolling ECG plot drawn with QPainter.

    Shows the last ``window_seconds`` of samples for one sensor.
    """

    def __init__(self, window_seconds: float = 10.0, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.window_seconds = window_seconds
        self.samples: List[ECGSample] = []
        self.sensor_name: str = ""
        self.setMinimumHeight(160)
        self.setBackgroundRole(self.backgroundRole())

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
        painter.fillRect(0, 0, width, height, QColor(30, 30, 30))

        if len(self.samples) < 2:
            painter.setPen(QColor(200, 200, 200))
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

        pen = QPen(QColor(0, 255, 128))
        pen.setWidth(2)
        painter.setPen(pen)

        points: List[tuple[int, int]] = []
        margin = 10
        plot_w = width - 2 * margin
        plot_h = height - 2 * margin
        for s in self.samples:
            x = margin + int(((s.timestamp - t0) / duration) * plot_w)
            y = margin + int(((max_v - s.value) / (max_v - min_v)) * plot_h)
            points.append((x, y))

        for i in range(1, len(points)):
            painter.drawLine(points[i - 1][0], points[i - 1][1], points[i][0], points[i][1])

        painter.setPen(QColor(200, 200, 200))
        painter.drawText(
            margin,
            margin + 12,
            f"{self.sensor_name or 'ECG'} | {len(self.samples)} samples | "
            f"{min_v + pad:.1f} .. {max_v - pad:.1f} µV",
        )


class LogViewerWidget(QWidget):
    """List log files and show their contents."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.logs_dir = default_data_dir() / "logs"
        self._build_ui()
        self.refresh_list()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)

        # Left: file list
        left = QVBoxLayout()
        self.file_list = QListWidget()
        self.file_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.file_list.currentItemChanged.connect(self._on_file_selected)
        left.addWidget(QLabel("Log files"))
        left.addWidget(self.file_list)

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.refresh_list)
        left.addWidget(self.refresh_btn)

        left_widget = QWidget()
        left_widget.setLayout(left)
        left_widget.setMaximumWidth(300)

        # Right: text viewer
        self.text_view = QPlainTextEdit()
        self.text_view.setReadOnly(True)
        self.text_view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)

        layout.addWidget(left_widget)
        layout.addWidget(self.text_view, stretch=1)

    def refresh_list(self) -> None:
        self.file_list.clear()
        if not self.logs_dir.exists():
            self.text_view.setPlainText(f"Log directory not found: {self.logs_dir}")
            return

        files = sorted(self.logs_dir.glob("*.log"), reverse=True)
        for path in files:
            item = QListWidgetItem(path.name)
            item.setData(Qt.ItemDataRole.UserRole, str(path))
            self.file_list.addItem(item)

        if self.file_list.count() == 0:
            self.text_view.setPlainText("No .log files found.")
        else:
            self.file_list.setCurrentRow(0)

    def _on_file_selected(self, current: QListWidgetItem | None, previous: QListWidgetItem | None) -> None:
        if current is None:
            return
        path = current.data(Qt.ItemDataRole.UserRole)
        try:
            text = Path(path).read_text(encoding="utf-8", errors="replace")
            # Show the newest lines at the bottom by default
            self.text_view.setPlainText(text)
            scrollbar = self.text_view.verticalScrollBar()
            if scrollbar is not None:
                scrollbar.setValue(scrollbar.maximum())
        except Exception as exc:
            self.text_view.setPlainText(f"Could not read {path}: {exc}")


class LogsWidget(QWidget):
    """Combined live ECG + log viewer tab."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        ecg_group = QGroupBox("Live ECG")
        ecg_layout = QVBoxLayout(ecg_group)
        self.ecg_plot = ECGPlotWidget(window_seconds=10.0)
        ecg_layout.addWidget(self.ecg_plot)
        self.ecg_info = QLabel("Sensor: -")
        ecg_layout.addWidget(self.ecg_info)

        logs_group = QGroupBox("Application logs")
        logs_layout = QVBoxLayout(logs_group)
        self.log_viewer = LogViewerWidget()
        logs_layout.addWidget(self.log_viewer)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(ecg_group)
        splitter.addWidget(logs_group)
        splitter.setSizes([250, 350])
        layout.addWidget(splitter)

    def add_samples(self, sensor_name: str, samples: List[ECGSample]) -> None:
        self.ecg_plot.set_sensor_name(sensor_name)
        self.ecg_plot.add_samples(samples)
        self.ecg_info.setText(f"Sensor: {sensor_name} | {len(self.ecg_plot.samples)} samples in view")

    def refresh_logs(self) -> None:
        self.log_viewer.refresh_list()
