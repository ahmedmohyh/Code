"""Game session detector stub."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class GameDetector:
    def __init__(self, auto_detect: bool = True, riot_api_key: str | None = None) -> None:
        self.auto_detect = auto_detect
        self.riot_api_key = riot_api_key
        self._in_match = False

    def poll(self) -> bool:
        """Return True if a match is currently running.

        Phase 5 will add LoL-client process detection and, later, Riot API.
        """
        return self._in_match

    def manual_start(self) -> None:
        self._in_match = True
        logger.info("Match manually started")

    def manual_stop(self) -> None:
        self._in_match = False
        logger.info("Match manually stopped")
