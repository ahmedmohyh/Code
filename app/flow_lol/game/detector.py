"""LoL match detection: manual + LCU API + process fallback.

Priority:
1. LCU API (local League Client, no external key) – gives exact queue type.
2. Process detection via psutil – only signals "LoL is running".
3. Manual start/stop via the UI – always available.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Callable, Optional

from flow_lol.config.settings import AppSettings
from flow_lol.game.lcu_client import LcuClient

logger = logging.getLogger(__name__)

# Executables that indicate an active League of Legends match.
LOL_GAME_EXECUTABLES = {"League of Legends.exe"}
LOL_CLIENT_EXECUTABLES = {"LeagueClient.exe", "LeagueClientUx.exe"}


class GameDetector:
    """Detect LoL matches manually, via the local LCU API, or via process scan.

    Callbacks:
      on_match_start(game_mode, detected) -> None
      on_match_end() -> None
      on_game_event(event_dict) -> None
    """

    def __init__(
        self,
        settings: AppSettings,
        on_match_start: Optional[Callable[[str, bool], None]] = None,
        on_match_end: Optional[Callable[[], None]] = None,
        on_game_event: Optional[Callable[[dict], None]] = None,
        poll_interval: float = 2.0,
    ) -> None:
        self.settings = settings
        self.on_match_start = on_match_start
        self.on_match_end = on_match_end
        self.on_game_event = on_game_event
        self.poll_interval = poll_interval

        self._in_match = False
        self._match_lock = asyncio.Lock()
        self._poll_task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
        self._current_game_mode: Optional[str] = None
        self._current_detected = False

        self._lcu = LcuClient(
            on_match_start=self._on_lcu_match_start,
            on_match_end=self._on_lcu_match_end,
            on_game_event=self._on_lcu_game_event,
            poll_interval=poll_interval,
        )

    async def start(self) -> None:
        """Begin background detection if auto-detect is enabled."""
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
        await self._lcu.close()
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
            self._lcu.reset_event_tracking()
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
        """Try LCU first; fall back to process detection."""
        try:
            lcu_available = False
            while not self._stop_event.is_set():
                if not lcu_available:
                    lcu_available = await self._lcu.is_available()
                    if lcu_available:
                        logger.info("LCU API available; using local League Client for match detection")
                    else:
                        logger.debug("LCU not available; using process detection fallback")

                if lcu_available:
                    still_available = await self._lcu.poll_once()
                    if not still_available:
                        logger.warning("LCU client lost; switching to process detection")
                        lcu_available = False
                    elif self._in_match:
                        # While the match is in progress, poll live game events too.
                        await self._lcu.poll_events_once()
                else:
                    await self._detect_by_process()

                await asyncio.sleep(self.poll_interval)
        except asyncio.CancelledError:
            logger.debug("Game detector poll loop cancelled")
            raise

    async def _detect_by_process(self) -> None:
        """Detect match start/end via running LoL executables."""
        running = await self._detect_lol_processes()
        if running and not self._in_match:
            await self.start_match("auto-detected", detected=True)
        elif not running and self._in_match and self._current_detected:
            await self.end_match()

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

    def _on_lcu_match_start(self, game_mode: str, detected: bool) -> None:
        """Forward LCU start event to the worker callback."""
        # run_coroutine_threadsafe would be needed if this were called from another thread,
        # but LcuClient calls this from the same asyncio loop.
        asyncio.create_task(self.start_match(game_mode, detected=detected))

    def _on_lcu_game_event(self, event: dict) -> None:
        """Forward a live game event to the worker callback."""
        if self.on_game_event:
            try:
                self.on_game_event(event)
            except Exception:
                logger.exception("on_game_event callback failed")

    def _on_lcu_match_end(self) -> None:
        """Forward LCU end event to the worker callback."""
        asyncio.create_task(self.end_match())
