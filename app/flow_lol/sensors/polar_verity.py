"""Polar Verity Sense BLE PPG streaming stub.

Verity Sense is an optical (PPG) sensor, not a true ECG sensor. The current
Phase 1.2 implementation focuses on Polar H10 ECG streaming. This module
provides the same interface so the sensor manager can instantiate either
sensor, but it does not yet implement PPG parsing.

Future work (Phase 1.x): implement the Verity Sense PPG service and decide
how to integrate PPG-derived heart-rate features with ECG-derived features.
"""

from __future__ import annotations

import logging
from typing import Callable, List, Optional

from flow_lol.sensors.buffer import ECGBuffer, ECGSample

logger = logging.getLogger(__name__)


class PolarVeritySenseStream:
    """Placeholder for Verity Sense PPG streaming."""

    def __init__(
        self,
        buffer: ECGBuffer,
        device_address: Optional[str] = None,
        device_name: str = "Polar Verity Sense",
        on_connection_change: Optional[Callable[[str], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
    ) -> None:
        self.buffer = buffer
        self.device_address = device_address
        self.device_name = device_name
        self.on_connection_change = on_connection_change
        self.on_error = on_error

    async def scan(self, timeout: float = 10.0) -> List[tuple[str, str]]:
        """Return a list of (address, name) for nearby Verity Sense devices."""
        logger.warning("Verity Sense scan not yet implemented")
        return []

    async def start(self) -> None:
        """Placeholder connect + start stream."""
        logger.warning("Verity Sense streaming not yet implemented")
        if self.on_connection_change:
            self.on_connection_change("not_implemented")
        raise NotImplementedError("Verity Sense streaming is not implemented in Phase 1.2")

    async def stop(self) -> None:
        """Placeholder stop stream."""
        if self.on_connection_change:
            self.on_connection_change("disconnected")
