"""One-time migration of legacy flat webcam files into per-session folders.

Old layout (pre-folder):
    data/webcam/session_1_20261021_120000.mp4
    data/webcam/snapshots/snapshot_20261021_120005_123.jpg

New layout:
    data/webcam/session_1_20261021_120000/session_1_20261021_120000.mp4
    data/webcam/session_1_20261021_120000/snapshots/snapshot_20261021_120005_123.jpg
"""

from __future__ import annotations

import logging
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_SESSION_VIDEO_RE = re.compile(r"^session_(\d+)_(\d{8}_\d{6})\.mp4$", re.IGNORECASE)
_SNAPSHOT_RE = re.compile(r"snapshot_(\d{8}_\d{6})_\d+\.jpg$", re.IGNORECASE)


def _parse_filename_timestamp(name: str) -> Optional[datetime]:
    """Parse YYYYMMDD_HHMMSS from a session video or snapshot filename."""
    for pattern in (_SESSION_VIDEO_RE, _SNAPSHOT_RE):
        match = pattern.match(name)
        if match:
            # Video regex has the timestamp in group 2; snapshot regex has it in group 1.
            ts = match.group(2) if match.lastindex and match.lastindex >= 2 else match.group(1)
            try:
                return datetime.strptime(ts, "%Y%m%d_%H%M%S")
            except ValueError:
                return None
    return None


def _video_start_dt(path: Path) -> Optional[datetime]:
    dt = _parse_filename_timestamp(path.name)
    if dt is not None:
        return dt
    try:
        return datetime.fromtimestamp(path.stat().st_mtime)
    except Exception:
        return None


def _collect_session_folders(webcam_dir: Path) -> list[Path]:
    """Return all immediate subdirectories that contain an MP4 video."""
    folders: list[Path] = []
    for folder in webcam_dir.iterdir():
        if folder.is_dir() and any(folder.glob("*.mp4")):
            folders.append(folder)
    return folders


def _build_video_start_index(session_folders: list[Path]) -> list[tuple[Path, datetime]]:
    """Build an index of session folders with the parsed start time of their video."""
    index: list[tuple[Path, datetime]] = []
    for folder in session_folders:
        videos = list(folder.glob("*.mp4"))
        if not videos:
            continue
        dt = _video_start_dt(videos[0])
        if dt is not None:
            index.append((folder, dt))
    index.sort(key=lambda x: x[1])
    return index


def migrate_legacy_webcam_layout(webcam_dir: Path) -> None:
    """Move top-level MP4s and loose snapshots into per-session folders.

    This is safe to run repeatedly: already-organized files are skipped.
    """
    webcam_dir = Path(webcam_dir)
    if not webcam_dir.exists():
        return

    # Step 1: Move any top-level MP4s into per-session folders.
    top_level_mp4s = sorted(
        [p for p in webcam_dir.iterdir() if p.is_file() and p.suffix.lower() == ".mp4"],
        key=lambda p: p.name,
    )
    for video in top_level_mp4s:
        target_folder = webcam_dir / video.stem
        target_folder.mkdir(parents=True, exist_ok=True)
        destination = target_folder / video.name
        if destination.resolve() != video.resolve():
            try:
                shutil.move(str(video), str(destination))
                logger.info("Moved video %s -> %s", video, destination)
            except Exception as exc:
                logger.error("Could not move %s: %s", video, exc)

    # Step 2: Assign loose snapshots from the top-level snapshots folder to the
    # nearest session folder by start time. This also runs when the videos were
    # already moved in a previous attempt.
    loose_snap_dir = webcam_dir / "snapshots"
    if loose_snap_dir.exists():
        video_starts = _build_video_start_index(_collect_session_folders(webcam_dir))
        if video_starts:
            for snap in sorted(loose_snap_dir.glob("*.jpg")):
                snap_dt = _parse_filename_timestamp(snap.name)
                if snap_dt is None:
                    try:
                        snap_dt = datetime.fromtimestamp(snap.stat().st_mtime)
                    except Exception:
                        continue

                nearest = min(
                    video_starts,
                    key=lambda x: abs((x[1] - snap_dt).total_seconds()),
                )
                target_folder = nearest[0]
                target_snap_dir = target_folder / "snapshots"
                target_snap_dir.mkdir(parents=True, exist_ok=True)
                destination = target_snap_dir / snap.name
                if destination.exists():
                    continue
                try:
                    shutil.move(str(snap), str(destination))
                    logger.info("Moved snapshot %s -> %s", snap, destination)
                except Exception as exc:
                    logger.error("Could not move %s: %s", snap, exc)

        # Remove the now-empty top-level snapshots folder.
        try:
            if loose_snap_dir.exists() and not any(loose_snap_dir.iterdir()):
                loose_snap_dir.rmdir()
                logger.info("Removed empty top-level snapshots folder")
        except Exception as exc:
            logger.debug("Could not remove top-level snapshots folder: %s", exc)
