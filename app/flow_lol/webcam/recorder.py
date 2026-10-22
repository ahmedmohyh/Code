"""Background webcam recorder using OpenCV."""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Callable, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_FPS = 15
DEFAULT_WIDTH = 640
DEFAULT_HEIGHT = 480
SNAPSHOT_INTERVAL_SECONDS = 5


class WebcamRecorder:
    """Record the default webcam to an MP4 file in a background thread.

    The recorder is intentionally kept separate from the classification pipeline:
    the webcam is stored for post-game reflection and is not used as a real-time
    flow input.
    """

    def __init__(
        self,
        output_dir: Path,
        snapshot_dir: Optional[Path] = None,
        enabled: bool = True,
        fps: int = DEFAULT_FPS,
        width: int = DEFAULT_WIDTH,
        height: int = DEFAULT_HEIGHT,
        snapshot_interval_seconds: int = SNAPSHOT_INTERVAL_SECONDS,
        on_snapshot: Optional[Callable[[Path], None]] = None,
    ) -> None:
        self.output_dir = Path(output_dir)
        self.snapshot_dir = Path(snapshot_dir) if snapshot_dir else self.output_dir / "snapshots"
        self.enabled = enabled
        self.fps = fps
        self.width = width
        self.height = height
        self.snapshot_interval_seconds = snapshot_interval_seconds
        self.on_snapshot = on_snapshot

        self._active = False
        self._thread: Optional[threading.Thread] = None
        self._output_path: Optional[Path] = None
        self._stop_event = threading.Event()
        self._snapshots: List[Path] = []

    def start(self, session_id: int) -> Optional[Path]:
        """Start recording if enabled. Returns the output path or None."""
        if not self.enabled:
            logger.info("Webcam recording disabled")
            return None
        if self._active:
            logger.warning("Webcam recorder already active")
            return self._output_path

        self.output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        self._output_path = self.output_dir / f"session_{session_id}_{timestamp}.mp4"

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._record_loop,
            name=f"webcam-{session_id}",
            daemon=True,
        )
        self._active = True
        self._thread.start()
        logger.info("Webcam recording started: %s", self._output_path)
        return self._output_path

    def stop(self) -> Optional[Path]:
        """Stop recording and return the final output path."""
        if not self._active:
            return self._output_path
        self._stop_event.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=8.0)
        self._active = False
        logger.info("Webcam recording stopped: %s", self._output_path)
        path = self._output_path
        self._output_path = None
        self._thread = None
        return path

    def is_recording(self) -> bool:
        """Return True if the recorder is currently active."""
        return self._active

    def _record_loop(self) -> None:
        try:
            import cv2
        except ImportError:
            logger.error("OpenCV not installed; cannot record webcam")
            self._active = False
            return

        cap: Optional[object] = None
        writer: Optional[object] = None
        try:
            cap = cv2.VideoCapture(0)
            if not cap.isOpened():
                logger.error("Could not open default webcam")
                return

            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            cap.set(cv2.CAP_PROP_FPS, self.fps)

            # On Windows the openh264 DLL is usually missing, so avc1 fails and
            # falls back only after several seconds. Use mp4v directly for fast,
            # reliable startup. The resulting MP4 plays in the in-app Qt player.
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            writer = cv2.VideoWriter(
                str(self._output_path),
                fourcc,
                float(self.fps),
                (self.width, self.height),
            )
            if not writer.isOpened():
                logger.error("Could not open video writer for %s", self._output_path)
                return

            # Read a few frames to stabilise the camera before writing.
            for _ in range(3):
                cap.read()

            self.snapshot_dir.mkdir(parents=True, exist_ok=True)
            frame_time = 1.0 / self.fps
            frame_count = 0
            snapshot_frames = max(1, int(self.fps * self.snapshot_interval_seconds))
            while not self._stop_event.is_set():
                ok, frame = cap.read()
                if not ok:
                    logger.warning("Webcam frame capture failed; stopping")
                    break
                writer.write(frame)
                frame_count += 1
                if frame_count % snapshot_frames == 0:
                    self._save_snapshot(frame)
                # Small sleep to keep the loop at roughly the target FPS.
                time.sleep(frame_time)
        except Exception as exc:
            logger.exception("Webcam recorder error: %s", exc)
        finally:
            # Releasing the writer finalises the MP4 container ('moov' atom).
            if writer is not None:
                writer.release()
            if cap is not None:
                cap.release()

    def _save_snapshot(self, frame: object) -> None:
        """Save a single frame as a JPG snapshot."""
        try:
            import cv2

            timestamp = time.strftime("%Y%m%d_%H%M%S")
            path = self.snapshot_dir / f"snapshot_{timestamp}_{int(time.time() * 1000) % 1000}.jpg"
            cv2.imwrite(str(path), frame)
            self._snapshots.append(path)
            logger.debug("Webcam snapshot saved: %s", path)
            if self.on_snapshot:
                self.on_snapshot(path)
        except Exception as exc:
            logger.warning("Could not save webcam snapshot: %s", exc)

    def get_snapshots(self) -> List[Path]:
        """Return paths of snapshots captured during this recording."""
        return list(self._snapshots)

    @staticmethod
    def is_available() -> bool:
        """Return True if a webcam can be opened without starting a recording."""
        try:
            import cv2

            cap = cv2.VideoCapture(0)
            available = cap.isOpened()
            cap.release()
            return available
        except Exception:
            return False
