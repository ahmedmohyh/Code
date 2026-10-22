"""Webcam recordings tab with a modern card-based layout."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Callable, Optional

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QPixmap
from PyQt6.QtMultimedia import QMediaPlayer
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtWidgets import (
    QAbstractItemView,
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

from flow_lol.ui.components import CardWidget, CompactActionBar, ToggleActionButton
from flow_lol.ui.styles import Colors, Spacing
from flow_lol.utils.paths import default_data_dir

logger = logging.getLogger(__name__)


class WebcamWidget(QWidget):
    """Tab for managing webcam recordings inside the app."""

    def __init__(
        self,
        on_toggle: Optional[Callable[[], None]] = None,
        webcam_dir: Optional[Path] = None,
        snapshot_dir: Optional[Path] = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._on_toggle = on_toggle
        self._toggle_enabled = True
        self.webcam_dir = Path(webcam_dir) if webcam_dir else default_data_dir() / "webcam"
        self.snapshot_dir = Path(snapshot_dir) if snapshot_dir else self.webcam_dir / "snapshots"
        self._current_path: Optional[Path] = None

        self.player = QMediaPlayer()
        self.video_widget = QVideoWidget()
        self.player.setVideoOutput(self.video_widget)

        self._build_ui()
        self.refresh_list()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(Spacing.MD)

        # Left: recordings list + snapshots
        left_card = CardWidget("Recordings")
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
        self.delete_all_btn = actions.add_button("🗑 Delete all videos")
        self.delete_all_btn.setProperty("role", "danger")
        self.delete_all_btn.clicked.connect(self._delete_all_videos)
        actions.add_stretch()
        left_layout.addWidget(actions)

        left_layout.addWidget(QLabel("Snapshots"))
        self.snapshot_list = QListWidget()
        self.snapshot_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.snapshot_list.setAlternatingRowColors(True)
        self.snapshot_list.currentItemChanged.connect(self._on_snapshot_selected)
        left_layout.addWidget(self.snapshot_list)

        snap_actions = CompactActionBar()
        self.refresh_snap_btn = snap_actions.add_button("🔄 Refresh")
        self.refresh_snap_btn.clicked.connect(self.refresh_snapshots)
        self.delete_snap_btn = snap_actions.add_button("🗑 Delete selected snapshot")
        self.delete_snap_btn.setProperty("role", "danger")
        self.delete_snap_btn.clicked.connect(self._delete_selected_snapshot)
        self.delete_all_snap_btn = snap_actions.add_button("🗑 Delete all snapshots")
        self.delete_all_snap_btn.setProperty("role", "danger")
        self.delete_all_snap_btn.clicked.connect(self._delete_all_snapshots)
        self.open_snap_folder_btn = snap_actions.add_button("📂 Open folder")
        self.open_snap_folder_btn.clicked.connect(self._open_snapshots_folder)
        snap_actions.add_stretch()
        left_layout.addWidget(snap_actions)

        left_card.setMaximumWidth(360)

        # Right: preview + live control
        right_card = CardWidget("Preview / live control")
        right_layout = right_card.content_layout()

        self.preview_stack = QWidget()
        preview_stack_layout = QVBoxLayout(self.preview_stack)
        preview_stack_layout.setContentsMargins(0, 0, 0, 0)
        preview_stack_layout.setSpacing(0)
        preview_stack_layout.addWidget(self.video_widget, stretch=1)

        self.image_overlay = QLabel()
        self.image_overlay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_overlay.setStyleSheet("background-color: #000000;")
        self.image_overlay.hide()
        preview_stack_layout.addWidget(self.image_overlay, stretch=1)
        right_layout.addWidget(self.preview_stack, stretch=1)

        # Active camera indicator
        camera_indicator_layout = QHBoxLayout()
        camera_indicator_layout.setSpacing(Spacing.SM)
        self.camera_icon = QLabel("📹")
        self.camera_icon.setStyleSheet(f"font-size: 18px; color: {Colors.TEXT_MUTED};")
        camera_indicator_layout.addWidget(self.camera_icon)
        self.live_status_label = QLabel("No active webcam recording")
        self.live_status_label.setWordWrap(True)
        self.live_status_label.setProperty("role", "muted")
        camera_indicator_layout.addWidget(self.live_status_label)
        camera_indicator_layout.addStretch()
        right_layout.addLayout(camera_indicator_layout)

        self.error_label = QLabel("")
        self.error_label.setWordWrap(True)
        self.error_label.setProperty("role", "error")
        self.error_label.hide()
        right_layout.addWidget(self.error_label)

        controls = QHBoxLayout()
        controls.setSpacing(Spacing.SM)

        self.play_btn = QPushButton("▶")
        self.play_btn.setProperty("role", "icon")
        self.play_btn.setToolTip("Play / pause selected recording")
        self.play_btn.clicked.connect(self._toggle_playback)
        self.play_btn.setEnabled(False)

        self.stop_btn = QPushButton("⏹")
        self.stop_btn.setProperty("role", "icon")
        self.stop_btn.setToolTip("Stop playback")
        self.stop_btn.clicked.connect(self._stop)
        self.stop_btn.setEnabled(False)

        controls.addWidget(self.play_btn)
        controls.addWidget(self.stop_btn)
        controls.addStretch()

        right_layout.addLayout(controls)

        self.toggle_btn = ToggleActionButton(
            idle_text="▶  Enable webcam",
            active_text="■  Disable webcam",
            idle_role="primary",
            active_role="danger",
        )
        self.toggle_btn.setEnabled(self._on_toggle is not None)
        self.toggle_btn.clicked.connect(self._request_toggle)
        right_layout.addWidget(self.toggle_btn)

        self.info_label = QLabel("Select a recording to preview")
        self.info_label.setProperty("role", "muted")
        right_layout.addWidget(self.info_label)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left_card)
        splitter.addWidget(right_card)
        splitter.setSizes([320, 560])

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

        self.refresh_snapshots()

    def _on_file_selected(self, current: QListWidgetItem | None, previous: QListWidgetItem | None) -> None:
        if current is None:
            self.play_btn.setEnabled(False)
            self.stop_btn.setEnabled(False)
            return
        path_str = current.data(Qt.ItemDataRole.UserRole)
        path = Path(path_str)
        self._current_path = path
        self.image_overlay.hide()
        self.image_overlay.clear()
        self.video_widget.show()
        size_mb = path.stat().st_size / (1024 * 1024)
        self.info_label.setText(f"{path.name} ({size_mb:.1f} MB)")
        self.info_label.setProperty("role", "")
        self._stop()
        self.player.setSource(QUrl.fromLocalFile(str(path)))
        self.play_btn.setEnabled(True)
        self.stop_btn.setEnabled(True)

    def _toggle_playback(self) -> None:
        state = self.player.playbackState()
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
            self.play_btn.setText("▶")
        else:
            self.player.play()
            self.play_btn.setText("⏸")

    def _stop(self) -> None:
        self.player.stop()
        self.play_btn.setText("▶")

    def _request_toggle(self) -> None:
        if self._on_toggle is not None:
            self._on_toggle()

    def set_recording_state(self, recording: bool, path: Optional[Path]) -> None:
        """Update the live-control UI from the worker's webcam state."""
        self.toggle_btn.set_active(recording)
        self.error_label.hide()
        color = Colors.DANGER if recording else Colors.TEXT_MUTED
        self.camera_icon.setStyleSheet(f"font-size: 18px; color: {color};")
        if recording and path is not None:
            self.live_status_label.setText(f"Recording: {path.name}")
            self.live_status_label.setProperty("role", "")
        elif recording:
            self.live_status_label.setText("Recording active")
            self.live_status_label.setProperty("role", "")
        else:
            self.live_status_label.setText("No active webcam recording")
            self.live_status_label.setProperty("role", "muted")
        # Keep callback availability independent; use set_toggle_enabled from
        # the outside to reflect session/sensor readiness.
        self.toggle_btn.setEnabled(self._on_toggle is not None and self._toggle_enabled)

    def set_toggle_enabled(self, enabled: bool, tooltip: str = "") -> None:
        """Enable or disable the live webcam toggle from the host window."""
        self._toggle_enabled = enabled
        self.toggle_btn.setEnabled(enabled and self._on_toggle is not None)
        self.toggle_btn.setToolTip(tooltip)

    def show_error(self, message: str) -> None:
        """Display a webcam-specific error message inline."""
        self.error_label.setText(message)
        self.error_label.show()
        self.toggle_btn.set_active(False)
        self.camera_icon.setStyleSheet(f"font-size: 18px; color: {Colors.TEXT_MUTED};")
        self.live_status_label.setText("No active webcam recording")
        self.live_status_label.setProperty("role", "muted")

    def refresh_snapshots(self) -> None:
        """Reload the snapshots list from disk."""
        self.snapshot_list.clear()
        snap_dir = self.snapshot_dir
        if not snap_dir.exists():
            return
        files = sorted(snap_dir.glob("*.jpg"), reverse=True)
        for path in files:
            item = QListWidgetItem(path.name)
            item.setData(Qt.ItemDataRole.UserRole, str(path))
            self.snapshot_list.addItem(item)
        if self.snapshot_list.count() == 0:
            placeholder = QListWidgetItem("No snapshots yet")
            placeholder.setFlags(Qt.ItemFlag.NoItemFlags)
            self.snapshot_list.addItem(placeholder)

    def add_snapshot(self, path: object) -> None:
        """Append a newly captured snapshot to the list."""
        if not isinstance(path, Path):
            path = Path(str(path))
        item = QListWidgetItem(path.name)
        item.setData(Qt.ItemDataRole.UserRole, str(path))
        # Remove placeholder if present.
        first_item = self.snapshot_list.item(0)
        if (
            self.snapshot_list.count() == 1
            and first_item is not None
            and first_item.data(Qt.ItemDataRole.UserRole) is None
        ):
            self.snapshot_list.clear()
        self.snapshot_list.insertItem(0, item)
        self.snapshot_list.setCurrentRow(0)

    def _on_snapshot_selected(self, current: QListWidgetItem | None, previous: QListWidgetItem | None) -> None:
        if current is None:
            return
        path_str = current.data(Qt.ItemDataRole.UserRole)
        if not path_str:
            return

        # Snapshots are static images; show them in a QLabel overlay instead of
        # trying to play them through the video player (which caused them to
        # flash and disappear).
        self.player.setSource(QUrl())
        self.video_widget.hide()
        self.image_overlay.show()
        self._load_snapshot_image(Path(path_str))
        self.play_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        self.info_label.setText(f"Snapshot: {Path(path_str).name}")
        self.info_label.setProperty("role", "")

    def _load_snapshot_image(self, path: Path) -> None:
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            self.image_overlay.setText(f"Could not load {path.name}")
            self.image_overlay.setStyleSheet("background-color: #000000; color: #ffffff; font-size: 16px;")
            return
        scaled = pixmap.scaled(
            self.image_overlay.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.image_overlay.setPixmap(scaled)
        self.image_overlay.setStyleSheet("background-color: #000000;")

    def resizeEvent(self, event) -> None:
        """Rescale the current snapshot when the preview area is resized."""
        super().resizeEvent(event)
        if self.image_overlay.isVisible():
            current_item = self.snapshot_list.currentItem()
            if current_item is not None:
                path_str = current_item.data(Qt.ItemDataRole.UserRole)
                if path_str:
                    self._load_snapshot_image(Path(path_str))

    def _open_snapshots_folder(self) -> None:
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)
        try:
            os.startfile(str(self.snapshot_dir))
        except Exception as exc:
            logger.error("Could not open snapshots folder: %s", exc)

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
            f"Delete {path.name}?<br>This cannot be undone.",
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

    def _delete_all_videos(self) -> None:
        if not self.webcam_dir.exists():
            return
        files = sorted(self.webcam_dir.glob("*.mp4"))
        if not files:
            QMessageBox.information(self, "Delete all videos", "No videos to delete.")
            return

        reply = QMessageBox.question(
            self,
            "Delete all videos",
            f"Delete all {len(files)} video recording(s) in {self.webcam_dir}?<br>This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        # Release any open media handle first.
        self._stop()
        self.player.setSource(QUrl())
        self._current_path = None

        deleted = 0
        failed: list[str] = []
        for path in files:
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
                "Delete all videos",
                f"Deleted {deleted} file(s). {len(failed)} failed:\n" + "\n".join(failed[:5]),
            )
        else:
            QMessageBox.information(self, "Delete all videos", f"Deleted {deleted} video file(s).")
        logger.info("Deleted %s webcam video file(s)", deleted)

    def _delete_selected_snapshot(self) -> None:
        item = self.snapshot_list.currentItem()
        if item is None:
            QMessageBox.information(self, "Delete", "No snapshot selected.")
            return
        path_str = item.data(Qt.ItemDataRole.UserRole)
        if not path_str:
            return
        path = Path(path_str)

        reply = QMessageBox.question(
            self,
            "Delete snapshot",
            f"Delete {path.name}?<br>This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            self.image_overlay.hide()
            self.image_overlay.clear()
            path.unlink()
            self.refresh_snapshots()
            self.info_label.setText("Select a recording to preview")
            self.info_label.setProperty("role", "muted")
            self.play_btn.setEnabled(False)
            self.stop_btn.setEnabled(False)
            logger.info("Deleted webcam snapshot %s", path)
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Could not delete file:\n{exc}")
            logger.error("Failed to delete %s: %s", path, exc)

    def _delete_all_snapshots(self) -> None:
        snap_dir = self.snapshot_dir
        if not snap_dir.exists():
            QMessageBox.information(self, "Delete all snapshots", "No snapshots to delete.")
            return
        files = sorted(snap_dir.glob("*.jpg"))
        if not files:
            QMessageBox.information(self, "Delete all snapshots", "No snapshots to delete.")
            return

        reply = QMessageBox.question(
            self,
            "Delete all snapshots",
            f"Delete all {len(files)} snapshot(s) in {snap_dir}?<br>This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self.image_overlay.hide()
        self.image_overlay.clear()

        deleted = 0
        failed: list[str] = []
        for path in files:
            try:
                path.unlink()
                deleted += 1
            except Exception as exc:
                failed.append(f"{path.name}: {exc}")
                logger.error("Failed to delete %s: %s", path, exc)

        self.refresh_snapshots()
        self.info_label.setText("Select a recording to preview")
        self.info_label.setProperty("role", "muted")
        if failed:
            QMessageBox.warning(
                self,
                "Delete all snapshots",
                f"Deleted {deleted} file(s). {len(failed)} failed:\n" + "\n".join(failed[:5]),
            )
        else:
            QMessageBox.information(self, "Delete all snapshots", f"Deleted {deleted} snapshot file(s).")
        logger.info("Deleted %s webcam snapshot file(s)", deleted)
