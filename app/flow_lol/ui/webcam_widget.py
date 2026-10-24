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
    QTreeWidget,
    QTreeWidgetItem,
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
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._on_toggle = on_toggle
        self._toggle_enabled = False
        self.webcam_dir = Path(webcam_dir) if webcam_dir else default_data_dir() / "webcam"
        self._session_filter: Optional[int] = None
        self._current_folder: Optional[Path] = None
        self._current_path: Optional[Path] = None

        self.player = QMediaPlayer()
        self.video_widget = QVideoWidget()
        self.video_widget.setMinimumHeight(220)
        self.video_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self.player.setVideoOutput(self.video_widget)

        # Seek slider + time label
        self._seek_slider = QSlider(Qt.Orientation.Horizontal)
        self._seek_slider.setRange(0, 0)
        self._seek_slider.setEnabled(False)
        self._seek_slider.sliderReleased.connect(self._on_seek_released)
        self._time_label = QLabel("00:00 / 00:00")
        self._time_label.setProperty("role", "muted")

        self.player.positionChanged.connect(self._on_player_position_changed)
        self.player.durationChanged.connect(self._on_player_duration_changed)

        self._build_ui()
        self.refresh_list()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(Spacing.MD)

        # Left: session tree + snapshots
        left_card = CardWidget("Recordings")
        left_layout = left_card.content_layout()

        left_layout.addWidget(QLabel("Session folders"))
        self.session_tree = QTreeWidget()
        self.session_tree.setHeaderHidden(True)
        self.session_tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.session_tree.setAlternatingRowColors(True)
        self.session_tree.currentItemChanged.connect(self._on_tree_item_changed)
        left_layout.addWidget(self.session_tree)

        session_actions = QGridLayout()
        session_actions.setSpacing(Spacing.SM)
        self.refresh_btn = QPushButton("🔄 Refresh")
        self.refresh_btn.setToolTip("Refresh session list")
        self.refresh_btn.clicked.connect(self.refresh_list)
        self.delete_btn = QPushButton("🗑 Delete")
        self.delete_btn.setProperty("role", "danger")
        self.delete_btn.setToolTip("Delete selected session folder")
        self.delete_btn.clicked.connect(self._delete_selected_session_folder)
        self.delete_all_btn = QPushButton("🗑 All")
        self.delete_all_btn.setProperty("role", "danger")
        self.delete_all_btn.setToolTip("Delete all session folders")
        self.delete_all_btn.clicked.connect(self._delete_all_session_folders)
        session_actions.addWidget(self.refresh_btn, 0, 0)
        session_actions.addWidget(self.delete_btn, 0, 1)
        session_actions.addWidget(self.delete_all_btn, 0, 2)

        self.show_all_btn = QPushButton("👁 Show all sessions")
        self.show_all_btn.setToolTip("Clear dashboard filter and show every session")
        self.show_all_btn.clicked.connect(self._clear_session_filter)
        session_actions.addWidget(self.show_all_btn, 1, 0, 1, 3)
        left_layout.addLayout(session_actions)

        left_layout.addWidget(QLabel("Snapshots"))
        self.snapshot_list = QListWidget()
        self.snapshot_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.snapshot_list.setAlternatingRowColors(True)
        self.snapshot_list.currentItemChanged.connect(self._on_snapshot_selected)
        left_layout.addWidget(self.snapshot_list)

        snap_actions = QGridLayout()
        snap_actions.setSpacing(Spacing.SM)
        self.refresh_snap_btn = QPushButton("🔄 Refresh")
        self.refresh_snap_btn.setToolTip("Refresh snapshots for selected session")
        self.refresh_snap_btn.clicked.connect(self.refresh_snapshots)
        self.delete_snap_btn = QPushButton("🗑 One")
        self.delete_snap_btn.setProperty("role", "danger")
        self.delete_snap_btn.setToolTip("Delete selected snapshot")
        self.delete_snap_btn.clicked.connect(self._delete_selected_snapshot)
        self.delete_all_snap_btn = QPushButton("🗑 All")
        self.delete_all_snap_btn.setProperty("role", "danger")
        self.delete_all_snap_btn.setToolTip("Delete all snapshots in selected session")
        self.delete_all_snap_btn.clicked.connect(self._delete_all_snapshots)
        self.open_snap_folder_btn = QPushButton("📂 Folder")
        self.open_snap_folder_btn.setToolTip("Open snapshots folder for selected session")
        self.open_snap_folder_btn.clicked.connect(self._open_snapshots_folder)
        snap_actions.addWidget(self.refresh_snap_btn, 0, 0)
        snap_actions.addWidget(self.delete_snap_btn, 0, 1)
        snap_actions.addWidget(self.delete_all_snap_btn, 0, 2)
        snap_actions.addWidget(self.open_snap_folder_btn, 1, 0, 1, 3)
        left_layout.addLayout(snap_actions)

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
        self.image_overlay.setMinimumHeight(220)
        self.image_overlay.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self.image_overlay.hide()
        preview_stack_layout.addWidget(self.image_overlay, stretch=1)
        self.preview_stack.setMinimumHeight(240)
        self.preview_stack.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
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
        controls.addWidget(self._seek_slider, stretch=1)
        controls.addWidget(self._time_label)
        controls.addStretch()

        right_layout.addLayout(controls)

        self.info_label = QLabel("Select a recording to preview")
        self.info_label.setProperty("role", "muted")
        right_layout.addWidget(self.info_label)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left_card)
        splitter.addWidget(right_card)
        splitter.setSizes([320, 560])

        layout.addWidget(splitter)

    def set_session_filter(self, session_id: Optional[int]) -> None:
        """Show only recordings belonging to the given session. Pass None to clear."""
        self._session_filter = session_id
        self.refresh_list()
        if session_id is None:
            self.show_all_btn.hide()
            return
        self.show_all_btn.show()
        prefix = f"session_{session_id}_"
        for i in range(self.session_tree.topLevelItemCount()):
            item = self.session_tree.topLevelItem(i)
            if item is not None and item.text(0).startswith(prefix):
                self.session_tree.setCurrentItem(item)
                item.setExpanded(True)
                break

    def _clear_session_filter(self) -> None:
        """Clear the dashboard filter and show every session again."""
        self.set_session_filter(None)

    def _is_session_visible(self, folder: Path) -> bool:
        """Return True if the folder belongs to the active dashboard session filter."""
        if self._session_filter is None:
            return True
        return folder.name.startswith(f"session_{self._session_filter}_")

    def refresh_list(self) -> None:
        self.session_tree.clear()
        self._current_folder = None
        self._current_path = None
        if not self.webcam_dir.exists():
            self.webcam_dir.mkdir(parents=True, exist_ok=True)

        prefix = f"session_{self._session_filter}_" if self._session_filter is not None else None

        # Discover session folders: immediate subdirectories that contain an MP4.
        folders = sorted(
            [
                p
                for p in self.webcam_dir.iterdir()
                if p.is_dir() and any(p.glob("*.mp4")) and self._is_session_visible(p)
            ],
            reverse=True,
        )
        for folder in folders:
            folder_item = QTreeWidgetItem(self.session_tree)
            folder_item.setText(0, folder.name)
            folder_item.setData(0, Qt.ItemDataRole.UserRole, str(folder))
            folder_item.setFlags(folder_item.flags() | Qt.ItemFlag.ItemIsSelectable)
            for video in sorted(folder.glob("*.mp4"), reverse=True):
                video_item = QTreeWidgetItem(folder_item)
                video_item.setText(0, video.name)
                video_item.setData(0, Qt.ItemDataRole.UserRole, str(video))
                video_item.setFlags(video_item.flags() | Qt.ItemFlag.ItemIsSelectable)

        # Backward compatibility: also show top-level MP4 files as synthetic session folders.
        top_level_videos = sorted(
            [
                p
                for p in self.webcam_dir.iterdir()
                if p.is_file() and p.suffix.lower() == ".mp4" and (prefix is None or p.stem.startswith(prefix))
            ],
            reverse=True,
        )
        for video in top_level_videos:
            folder_item = QTreeWidgetItem(self.session_tree)
            folder_item.setText(0, video.stem)
            folder_item.setData(0, Qt.ItemDataRole.UserRole, str(self.webcam_dir))
            folder_item.setFlags(folder_item.flags() | Qt.ItemFlag.ItemIsSelectable)
            video_item = QTreeWidgetItem(folder_item)
            video_item.setText(0, video.name)
            video_item.setData(0, Qt.ItemDataRole.UserRole, str(video))
            video_item.setFlags(video_item.flags() | Qt.ItemFlag.ItemIsSelectable)

        if self.session_tree.topLevelItemCount() == 0:
            self.info_label.setText(
                "No webcam recordings found."
                if self._session_filter is None
                else f"No recordings for session {self._session_filter}."
            )
            placeholder = QTreeWidgetItem(self.session_tree)
            placeholder.setText(0, "No session recordings")
            placeholder.setFlags(Qt.ItemFlag.NoItemFlags)
        else:
            self.session_tree.setCurrentItem(self.session_tree.topLevelItem(0))

        self.refresh_snapshots()

    def _on_tree_item_changed(self, current: QTreeWidgetItem | None, previous: QTreeWidgetItem | None) -> None:
        if current is None:
            self.play_btn.setEnabled(False)
            self.stop_btn.setEnabled(False)
            self._seek_slider.setEnabled(False)
            return
        path_str = current.data(0, Qt.ItemDataRole.UserRole)
        if not path_str:
            return
        path = Path(path_str)

        if path.is_dir():
            # Folder selected: show its snapshots.
            self._current_folder = path
            self._current_path = None
            self._stop()
            self.player.setSource(QUrl())
            self.image_overlay.hide()
            self.image_overlay.clear()
            self.video_widget.show()
            self.play_btn.setEnabled(False)
            self.stop_btn.setEnabled(False)
            self._seek_slider.setEnabled(False)
            self.info_label.setText(f"Session folder: {path.name}")
            self.info_label.setProperty("role", "muted")
            self.refresh_snapshots()
            return

        # Video file selected.
        self._current_path = path
        self._current_folder = path.parent
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
        self._seek_slider.setEnabled(True)
        # Load snapshots for this session too.
        self.refresh_snapshots()

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
        self._seek_slider.setValue(0)
        self._update_time_label(0, self.player.duration())

    def _on_player_position_changed(self, position: int) -> None:
        if not self._seek_slider.isSliderDown():
            self._seek_slider.setValue(position)
        self._update_time_label(position, self.player.duration())

    def _on_player_duration_changed(self, duration: int) -> None:
        self._seek_slider.setRange(0, duration)
        self._update_time_label(self.player.position(), duration)

    def _on_seek_released(self) -> None:
        self.player.setPosition(self._seek_slider.value())

    @staticmethod
    def _format_ms(ms: int) -> str:
        seconds = max(0, ms) // 1000
        return f"{seconds // 60:02d}:{seconds % 60:02d}"

    def _update_time_label(self, position: int, duration: int) -> None:
        self._time_label.setText(f"{self._format_ms(position)} / {self._format_ms(duration)}")

    def _request_toggle(self) -> None:
        if self._on_toggle is not None:
            self._on_toggle()

    def set_recording_state(self, recording: bool, path: Optional[Path]) -> None:
        """Update the live-control UI from the worker's webcam state."""
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

    def set_toggle_enabled(self, enabled: bool, tooltip: str = "") -> None:
        """No-op: the webcam tab no longer has a local toggle button."""
        self._toggle_enabled = enabled

    def show_error(self, message: str) -> None:
        """Display a webcam-specific error message inline."""
        self.error_label.setText(message)
        self.error_label.show()
        self.camera_icon.setStyleSheet(f"font-size: 18px; color: {Colors.TEXT_MUTED};")
        self.live_status_label.setText("No active webcam recording")
        self.live_status_label.setProperty("role", "muted")

    def _snapshot_dir_for_selection(self) -> Optional[Path]:
        """Return the snapshots folder for the currently selected session."""
        if self._current_folder is not None:
            nested = self._current_folder / "snapshots"
            if nested.exists():
                return nested
            # Backward compatibility: top-level snapshots folder.
            top_level = self.webcam_dir / "snapshots"
            if top_level.exists():
                return top_level
        # Fallback: most recently recorded session folder.
        if self.session_tree.topLevelItemCount() > 0:
            first = self.session_tree.topLevelItem(0)
            if first is not None:
                path_str = first.data(0, Qt.ItemDataRole.UserRole)
                if path_str:
                    folder = Path(path_str)
                    nested = folder / "snapshots"
                    if nested.exists():
                        return nested
        # Final fallback to top-level snapshots.
        top_level = self.webcam_dir / "snapshots"
        return top_level if top_level.exists() else None

    def refresh_snapshots(self) -> None:
        """Reload the snapshots list from disk for the selected session."""
        self.snapshot_list.clear()
        snap_dir = self._snapshot_dir_for_selection()
        if snap_dir is None or not snap_dir.exists():
            placeholder = QListWidgetItem("No snapshots yet")
            placeholder.setFlags(Qt.ItemFlag.NoItemFlags)
            self.snapshot_list.addItem(placeholder)
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
        """Append a newly captured snapshot to the list if it belongs to the selected session."""
        if not isinstance(path, Path):
            path = Path(str(path))
        snap_dir = self._snapshot_dir_for_selection()
        if snap_dir is None or not path.resolve().is_relative_to(snap_dir.resolve()):
            return
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
        snap_dir = self._snapshot_dir_for_selection()
        if snap_dir is None:
            QMessageBox.information(self, "Open folder", "Select a session folder first.")
            return
        snap_dir.mkdir(parents=True, exist_ok=True)
        try:
            os.startfile(str(snap_dir))
        except Exception as exc:
            logger.error("Could not open snapshots folder: %s", exc)


    def _delete_selected_session_folder(self) -> None:
        item = self.session_tree.currentItem()
        if item is None:
            QMessageBox.information(self, "Delete", "No session folder selected.")
            return
        path_str = item.data(0, Qt.ItemDataRole.UserRole)
        if not path_str:
            return
        folder = Path(path_str)
        if not folder.is_dir():
            return

        reply = QMessageBox.question(
            self,
            "Delete session folder",
            f"Delete {folder.name} and all its videos + snapshots?<br>This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            self._stop()
            self.player.setSource(QUrl())
            self._current_path = None
            self._current_folder = None
            import shutil
            shutil.rmtree(folder)
            self.refresh_list()
            logger.info("Deleted session folder %s", folder)
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Could not delete folder:\n{exc}")
            logger.error("Failed to delete %s: %s", folder, exc)

    def _delete_all_session_folders(self) -> None:
        if not self.webcam_dir.exists():
            return
        folders = [p for p in self.webcam_dir.iterdir() if p.is_dir() and any(p.glob("*.mp4"))]
        if not folders:
            QMessageBox.information(self, "Delete all sessions", "No session folders to delete.")
            return

        reply = QMessageBox.question(
            self,
            "Delete all session folders",
            f"Delete all {len(folders)} session folder(s) and their snapshots?<br>This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self._stop()
        self.player.setSource(QUrl())
        self._current_path = None
        self._current_folder = None

        deleted = 0
        failed: list[str] = []
        import shutil
        for folder in folders:
            try:
                shutil.rmtree(folder)
                deleted += 1
            except Exception as exc:
                failed.append(f"{folder.name}: {exc}")
                logger.error("Failed to delete %s: %s", folder, exc)

        self.refresh_list()
        if failed:
            QMessageBox.warning(
                self,
                "Delete all sessions",
                f"Deleted {deleted} folder(s). {len(failed)} failed:\n" + "\n".join(failed[:5]),
            )
        else:
            QMessageBox.information(self, "Delete all sessions", f"Deleted {deleted} session folder(s).")
        logger.info("Deleted %s session folder(s)", deleted)

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
            logger.info("Deleted webcam snapshot %s", path)
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Could not delete file:\n{exc}")
            logger.error("Failed to delete %s: %s", path, exc)

    def _delete_all_snapshots(self) -> None:
        snap_dir = self._snapshot_dir_for_selection()
        if snap_dir is None or not snap_dir.exists():
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
        if failed:
            QMessageBox.warning(
                self,
                "Delete all snapshots",
                f"Deleted {deleted} file(s). {len(failed)} failed:\n" + "\n".join(failed[:5]),
            )
        else:
            QMessageBox.information(self, "Delete all snapshots", f"Deleted {deleted} snapshot file(s).")
        logger.info("Deleted %s webcam snapshot file(s)", deleted)
