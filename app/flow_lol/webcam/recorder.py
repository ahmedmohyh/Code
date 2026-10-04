"""Webcam recorder stub."""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class WebcamRecorder:
    def __init__(self, output_dir: Path, enabled: bool = True) -> None:
        self.output_dir = output_dir
        self.enabled = enabled
        self._active = False

    def start(self, session_id: int) -> None:
        if not self.enabled:
            return
        self._active = True
        logger.info("Webcam recording started for session %s", session_id)

    def stop(self) -> None:
        if not self._active:
            return
        self._active = False
        logger.info("Webcam recording stopped")
