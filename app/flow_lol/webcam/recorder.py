"""Background webcam recorder using OpenCV."""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

DEFAULT_FPS = 15
DEFAULT_WIDTH = 640
DEFAULT_HEIGHT = 480


class WebcamRecorder:
    """Record the default webcam to an MP4 file in a background thread.

    The recorder is intentionally kept separate from the classification pipeline:
    the webcam is stored for post-game reflection and is not used as a real-time
    flow input.
    """

    def __init__(
        self,
        output_dir: Path,
        enabled: bool = True,
        fps: int = DEFAULT_FPS,
        width: int = DEFAULT_WIDTH,
        height: int = DEFAULT_HEIGHT,
    ) -> None:
        self.output_dir = Path(output_dir)
        self.enabled = enabled
        self.fps = fps
        self.width = width
        self.height = height

        self._active = False
        self._thread: Optional[threading.Thread] = None
        self._output_path: Optional[Path] = None
        self._stop_event = threading.Event()

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

            # Use a more robust container codec.  'avc1' generally produces
            # playable MP4s even if the recording is very short, as long as the
            # writer is released properly.
            fourcc = cv2.VideoWriter_fourcc(*"avc1")
            writer = cv2.VideoWriter(
                str(self._output_path),
                fourcc,
                float(self.fps),
                (self.width, self.height),
            )
            if not writer.isOpened():
                # Fallback to mp4v if the H.264 codec is unavailable.
                logger.warning("avc1 writer not available, falling back to mp4v")
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

            frame_time = 1.0 / self.fps
            while not self._stop_event.is_set():
                ok, frame = cap.read()
                if not ok:
                    logger.warning("Webcam frame capture failed; stopping")
                    break
                writer.write(frame)
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
