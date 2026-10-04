"""Sensor manager: orchestrate Polar H10 and/or Verity Sense streams."""

from __future__ import annotations

import asyncio
import logging
from typing import Callable, Dict, List, Optional

from flow_lol.config.settings import AppSettings
from flow_lol.sensors.buffer import ECGBuffer, ECGSample
from flow_lol.sensors.polar_h10 import PolarH10BufferedStream
from flow_lol.sensors.polar_verity import PolarVeritySenseStream

logger = logging.getLogger(__name__)


class SensorManager:
    """Owns one ECG buffer per active sensor and manages streaming lifecycle."""

    def __init__(
        self,
        settings: AppSettings,
        on_connection_change: Optional[Callable[[str, str], None]] = None,
        on_error: Optional[Callable[[str, Exception], None]] = None,
        on_samples: Optional[Callable[[str, List[ECGSample]], None]] = None,
    ) -> None:
        self.settings = settings
        self.on_connection_change = on_connection_change
        self.on_error = on_error
        self.on_samples = on_samples

        self.buffers: Dict[str, ECGBuffer] = {}
        self.streams: Dict[str, PolarH10BufferedStream | PolarVeritySenseStream] = {}
        self._running = False

    def _make_callback(self, name: str) -> Callable[[str], None]:
        def cb(status: str) -> None:
            logger.info("[%s] status: %s", name, status)
            if self.on_connection_change:
                self.on_connection_change(name, status)
        return cb

    def _make_error_callback(self, name: str) -> Callable[[Exception], None]:
        def cb(exc: Exception) -> None:
            logger.error("[%s] error: %s", name, exc)
            if self.on_error:
                self.on_error(name, exc)
        return cb

    def _make_samples_callback(self, name: str) -> Callable[[List[ECGSample]], None]:
        def cb(samples: List[ECGSample]) -> None:
            if self.on_samples:
                self.on_samples(name, samples)
        return cb

    async def start(self) -> None:
        """Start enabled sensor streams."""
        if self._running:
            return
        self._running = True

        if self.settings.use_h10:
            buffer = ECGBuffer()
            self.buffers["h10"] = buffer
            stream = PolarH10BufferedStream(
                buffer=buffer,
                device_address=None,
                device_name="Polar H10",
                on_connection_change=self._make_callback("h10"),
                on_error=self._make_error_callback("h10"),
                on_samples_extra=self._make_samples_callback("h10"),
            )
            self.streams["h10"] = stream
            await stream.start()

        if self.settings.use_verity:
            logger.warning("Verity Sense streaming requested but not implemented")

    async def stop(self) -> None:
        """Stop all sensor streams."""
        for name, stream in self.streams.items():
            try:
                await stream.stop()
            except Exception as exc:
                logger.error("Error stopping %s: %s", name, exc)
        self.streams.clear()
        self.buffers.clear()
        self._running = False

    def get_buffer(self, name: str = "h10") -> Optional[ECGBuffer]:
        return self.buffers.get(name)

    def is_running(self) -> bool:
        return self._running
