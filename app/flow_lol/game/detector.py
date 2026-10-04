"""LoL match detection: manual start/stop + LoL-client process detection.

Riot Games REST API integration is intentionally left as a future optional layer;
Phase 2.0 uses the locally observable client process to auto-detect matches.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Callable, Dict, List, Optional

from flow_lol.config.settings import AppSettings

logger = logging.getLogger(__name__)

# Executables that indicate an active League of Legends match.
LOL_GAME_EXECUTABLES = {"League of Legends.exe"}
# Optional: also detect the client UI, but the game executable is what matters.
LOL_CLIENT_EXECUTABLES = {"LeagueClient.exe", "LeagueClientUx.exe"}


class GameDetector:
    """Detect LoL matches manually or by watching the game process.

    Callbacks:
      on_match_start(game_mode, detected) -> None
      on_match_end() -> None
    """

    def __init__(
        self,
        settings: AppSettings,
        on_match_start: Optional[Callable[[str, bool], None]] = None,
        on_match_end: Optional[Callable[[], None]] = None,
        poll_interval: float = 2.0,
    ) -> None:
        self.settings = settings
        self.on_match_start = on_match_start
        self.on_match_end = on_match_end
        self.poll_interval = poll_interval

        self._in_match = False
        self._match_lock = asyncio.Lock()
        self._poll_task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
        self._current_game_mode: Optional[str] = None
        self._current_detected = False

    async def start(self) -> None:
        """Begin background process detection if auto-detect is enabled."""
        if not self.settings.auto_detect_game:
            logger.info("Auto-detect disabled; only manual match start/stop is available")
            return
        self._stop_event.clear()
        self._poll_task = asyncio.create_task(self._poll_loop())
        logger.info("Game detector started")

    async def stop(self) -> None:
        """Stop detection and end any active match."""
        self._stop_event.set()
        if self._poll_task is not None:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
            self._poll_task = None
        await self.end_match()
        logger.info("Game detector stopped")

    async def start_match(self, game_mode: str, detected: bool = False) -> None:
        """Manually mark the beginning of a LoL match."""
        async with self._match_lock:
            if self._in_match:
                logger.debug("start_match ignored: already in a match")
                return
            self._in_match = True
            self._current_game_mode = game_mode
            self._current_detected = detected
        logger.info("Match started: %s (detected=%s)", game_mode, detected)
        if self.on_match_start:
            try:
                self.on_match_start(game_mode, detected)
            except Exception:
                logger.exception("on_match_start callback failed")

    async def end_match(self) -> None:
        """End the current match, if any."""
        async with self._match_lock:
            if not self._in_match:
                return
            self._in_match = False
            self._current_game_mode = None
            self._current_detected = False
        logger.info("Match ended")
        if self.on_match_end:
            try:
                self.on_match_end()
            except Exception:
                logger.exception("on_match_end callback failed")

    def in_match(self) -> bool:
        return self._in_match

    def current_game_mode(self) -> Optional[str]:
        return self._current_game_mode

    async def _poll_loop(self) -> None:
        """Poll for LoL game/client processes."""
        try:
            while not self._stop_event.is_set():
                running = await self._detect_lol_processes()
                if running and not self._in_match:
                    await self.start_match("auto-detected", detected=True)
                elif not running and self._in_match and self._current_detected:
                    await self.end_match()
                await asyncio.sleep(self.poll_interval)
        except asyncio.CancelledError:
            logger.debug("Game detector poll loop cancelled")
            raise

    async def _detect_lol_processes(self) -> bool:
        """Return True if a LoL game or client process is running."""
        try:
            import psutil
        except ImportError:
            logger.warning("psutil not installed; cannot auto-detect LoL process")
            return False

        def _check() -> bool:
            try:
                for proc in psutil.process_iter(["name"]):
                    name = proc.info.get("name")
                    if name in LOL_GAME_EXECUTABLES or name in LOL_CLIENT_EXECUTABLES:
                        return True
            except Exception as exc:
                logger.debug("Process enumeration failed: %s", exc)
            return False

        try:
            return await asyncio.wait_for(
                asyncio.to_thread(_check),
                timeout=1.0,
            )
        except asyncio.TimeoutError:
            logger.warning("Process detection timed out")
            return False
