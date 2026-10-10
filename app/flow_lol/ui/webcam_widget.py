"""Webcam recordings tab: list, play, and delete MP4 recordings."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable, Optional

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtMultimedia import QMediaPlayer
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtWidgets import (
    QAbstractItemView,
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

from flow_lol.utils.paths import default_data_dir

logger = logging.getLogger(__name__)


class WebcamWidget(QWidget):
    """Tab for managing webcam recordings inside the app."""

    def __init__(
        self,
        on_toggle: Optional[Callable[[], None]] = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._on_toggle = on_toggle
        self.webcam_dir = default_data_dir() / "webcam"
        self._current_path: Optional[Path] = None

        self.player = QMediaPlayer()
        self.video_widget = QVideoWidget()
        self.player.setVideoOutput(self.video_widget)

        self._build_ui()
        self.refresh_list()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)

        left_group = QGroupBox("Recordings")
        left_layout = QVBoxLayout(left_group)

        self.file_list = QListWidget()
        self.file_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.file_list.currentItemChanged.connect(self._on_file_selected)
        left_layout.addWidget(self.file_list)

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.refresh_list)
        left_layout.addWidget(self.refresh_btn)

        self.delete_btn = QPushButton("Delete selected")
        self.delete_btn.setStyleSheet("QPushButton { background-color: #f44336; color: white; }")
        self.delete_btn.clicked.connect(self._delete_selected)
        left_layout.addWidget(self.delete_btn)

        left_group.setMaximumWidth(350)

        right_group = QGroupBox("Preview / Live control")
        right_layout = QVBoxLayout(right_group)
        right_layout.addWidget(self.video_widget, stretch=1)

        controls = QHBoxLayout()
        self.play_btn = QPushButton("Play")
        self.play_btn.clicked.connect(self._play)
        self.pause_btn = QPushButton("Pause")
        self.pause_btn.clicked.connect(self._pause)
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.clicked.connect(self._stop)
        controls.addWidget(self.play_btn)
        controls.addWidget(self.pause_btn)
        controls.addWidget(self.stop_btn)
        controls.addStretch()

        self.live_status_label = QLabel("No active webcam recording")
        self.live_status_label.setWordWrap(True)
        right_layout.addWidget(self.live_status_label)

        self.toggle_btn = QPushButton("Enable webcam")
        self.toggle_btn.setEnabled(self._on_toggle is not None)
        self.toggle_btn.clicked.connect(self._request_toggle)
        right_layout.addWidget(self.toggle_btn)

        right_layout.addLayout(controls)

        self.info_label = QLabel("Select a recording to preview")
        right_layout.addWidget(self.info_label)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left_group)
        splitter.addWidget(right_group)
        splitter.setSizes([300, 550])

        layout.addWidget(splitter)

    def refresh_list(self) -> None:
        self.file_list.clear()
        if not self.webcam_dir.exists():
            self.webcam_dir.mkdir(parents=True, exist_ok=True)

        files = sorted(self.webcam_dir.glob("*.mp4"), reverse=True)
        for path in files:
            item = QListWidgetItem(path.name)
            item.setData(Qt.ItemDataRole.UserRole, str(path))
            self.file_list.addItem(item)

        if self.file_list.count() == 0:
            self.info_label.setText("No webcam recordings found.")
        else:
            self.file_list.setCurrentRow(0)

    def _on_file_selected(self, current: QListWidgetItem | None, previous: QListWidgetItem | None) -> None:
        if current is None:
            return
        path_str = current.data(Qt.ItemDataRole.UserRole)
        path = Path(path_str)
        self._current_path = path
        size_mb = path.stat().st_size / (1024 * 1024)
        self.info_label.setText(f"{path.name} ({size_mb:.1f} MB)")
        self._stop()
        self.player.setSource(QUrl.fromLocalFile(str(path)))

    def _play(self) -> None:
        self.player.play()

    def _pause(self) -> None:
        self.player.pause()

    def _stop(self) -> None:
        self.player.stop()

    def _request_toggle(self) -> None:
        if self._on_toggle is not None:
            self._on_toggle()

    def set_recording_state(self, recording: bool, path: Optional[Path]) -> None:
        """Update the live-control UI from the worker's webcam state."""
        if recording and path is not None:
            self.live_status_label.setText(f"Recording: {path.name}")
            self.toggle_btn.setText("Disable webcam")
        elif recording:
            self.live_status_label.setText("Recording active")
            self.toggle_btn.setText("Disable webcam")
        else:
            self.live_status_label.setText("No active webcam recording")
            self.toggle_btn.setText("Enable webcam")
        self.toggle_btn.setEnabled(self._on_toggle is not None)

    def _delete_selected(self) -> None:
        item = self.file_list.currentItem()
        if item is None:
            QMessageBox.information(self, "Delete", "No recording selected.")
            return
        path_str = item.data(Qt.ItemDataRole.UserRole)
        path = Path(path_str)

        reply = QMessageBox.question(
            self,
            "Delete recording",
            f"Delete {path.name}?\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            # Release the media player's file handle before deleting on Windows.
            self._stop()
            self.player.setSource(QUrl())
            self._current_path = None
            path.unlink()
            self.refresh_list()
            logger.info("Deleted webcam recording %s", path)
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Could not delete file:\n{exc}")
            logger.error("Failed to delete %s: %s", path, exc)
