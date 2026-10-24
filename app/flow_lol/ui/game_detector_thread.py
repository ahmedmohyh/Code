"""Background thread that runs the League game detector independently.

This lets the UI show the LOL / GAME indicators from the moment the app opens,
even if the Polar H10 sensor is not connected yet. When a session is active, the
same match events are forwarded to the SensorWorker so they can be written to
the database.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from PyQt6.QtCore import QThread, pyqtSignal

from flow_lol.config.settings import AppSettings
from flow_lol.game.detector import GameDetector

logger = logging.getLogger(__name__)


class GameDetectorThread(QThread):
    """Run GameDetector in its own asyncio event loop."""

    match_started = pyqtSignal(str, bool)
    match_ended = pyqtSignal()
    game_event = pyqtSignal(object)
    client_state_changed = pyqtSignal(bool, str)

    def __init__(
        self,
        settings: AppSettings,
        parent: Optional["QObject"] = None,
    ) -> None:
        super().__init__(parent)
        self.settings = settings
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._stop_event: Optional[asyncio.Event] = None
        self._detector: Optional[GameDetector] = None

    def run(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._stop_event = asyncio.Event()

        self._detector = GameDetector(
            settings=self.settings,
            on_match_start=self._on_match_start,
            on_match_end=self._on_match_end,
            on_game_event=self._on_game_event,
            on_client_state_change=self._on_client_state_change,
        )

        try:
            self._loop.run_until_complete(self._detector.start())
            self._loop.run_until_complete(self._stop_event.wait())
        finally:
            self._loop.run_until_complete(self._detector.stop())
            self._loop.close()
            self._loop = None

    def _on_match_start(self, game_mode: str, detected: bool) -> None:
        self.match_started.emit(game_mode, detected)

    def _on_match_end(self) -> None:
        self.match_ended.emit()

    def _on_game_event(self, event: dict) -> None:
        self.game_event.emit(event)

    def _on_client_state_change(self, connected: bool, phase: str) -> None:
        self.client_state_changed.emit(connected, phase)

    def start_match(self, game_mode: str, detected: bool = False) -> None:
        """Request a manual match start from the UI thread."""
        if self._loop is None or self._detector is None:
            logger.warning("Cannot start match: detector thread not running")
            return
        asyncio.run_coroutine_threadsafe(
            self._detector.start_match(game_mode, detected=detected),
            self._loop,
        )

    def end_match(self) -> None:
        """Request a manual match end from the UI thread."""
        if self._loop is None or self._detector is None:
            logger.warning("Cannot end match: detector thread not running")
            return
        asyncio.run_coroutine_threadsafe(
            self._detector.end_match(),
            self._loop,
        )

    def stop(self) -> None:
        """Stop the detector loop and wait for the thread to finish."""
        if self._stop_event is not None:
            self._stop_event.set()
        self.wait(5000)
