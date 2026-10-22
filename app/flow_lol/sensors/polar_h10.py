"""Polar H10 BLE ECG streaming.

Uses the ``polar_python`` package to handle the Polar PMD protocol.

Important Windows note: if an explicit MAC address is configured, the app builds
a ``BLEDevice`` from that address and connects directly.  This bypasses
``BleakScanner.discover()``, which on Windows often cannot see devices that are
already paired/connected to the OS ([bleak #1254](https://github.com/hbldh/bleak/issues/1254)).
If no address is configured, the app falls back to scanning.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Callable, List, Optional

from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from polar_python.device import PolarDevice
from polar_python.models import ECGData

from flow_lol.sensors.buffer import ECGBuffer, ECGSample

logger = logging.getLogger(__name__)

ECG_SAMPLE_RATE = 130  # Hz for Polar H10 ECG


class PolarH10Stream:
    """Async client that streams ECG from a Polar H10 via polar_python."""

    def __init__(
        self,
        device_address: Optional[str] = None,
        device_name: str = "Polar H10",
        on_connection_change: Optional[Callable[[str], None]] = None,
        on_samples: Optional[Callable[[List[ECGSample]], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
    ) -> None:
        self.device_address = device_address
        self.device_name = device_name
        self.on_connection_change = on_connection_change
        self.on_samples = on_samples
        self.on_error = on_error

        self._device: Optional[PolarDevice] = None
        self._running = False
        self._local_start: float = 0.0
        self._sample_count = 0

    async def scan(self, timeout: float = 10.0) -> List[tuple[str, str]]:
        """Return a list of (address, name) for nearby Polar H10 devices."""
        devices = await BleakScanner.discover(timeout=timeout)
        return [
            (d.address, d.name or "Unknown")
            for d in devices
            if d.name and self.device_name in d.name
        ]

    async def _find_device(self, address: Optional[str], timeout: float = 10.0) -> Optional[BLEDevice]:
        """Return a BLEDevice, using direct address lookup when possible.

        If an address is known, construct a BLEDevice manually.  This tells bleak
        to skip its implicit scan on Windows and use
        ``BluetoothLEDevice.from_bluetooth_address_async`` directly.
        """
        if address:
            logger.info("Using configured H10 address %s (no scan)", address)
            return BLEDevice(address, name=self.device_name, details=None)

        logger.info("Scanning for %s...", self.device_name)
        return await BleakScanner.find_device_by_filter(
            lambda bd, ad: bd.name and self.device_name in bd.name,
            timeout=timeout,
        )

    async def start(self, max_attempts: int = 3) -> None:
        """Connect and start ECG stream, with retries if the device is not found."""
        if self._running:
            return

        last_exc: Optional[Exception] = None

        for attempt in range(1, max_attempts + 1):
            try:
                bleak_device = await self._find_device(self.device_address)

                if bleak_device is None:
                    raise RuntimeError(
                        f"No {self.device_name} device found. "
                        "Make sure the H10 is blinking blue and not already connected to Windows."
                    )

                logger.info(
                    "Auto-selected %s at %s", bleak_device.name, bleak_device.address
                )

                self._device = PolarDevice(bleak_device)
                await self._device.connect()
                logger.info("Connected to %s", bleak_device.address)

                if self.on_connection_change:
                    self.on_connection_change("connected")

                try:
                    await self._device.start_ecg_stream(
                        ecg_callback=self._on_ecg_data,
                        sample_rate=ECG_SAMPLE_RATE,
                        resolution=14,
                    )
                except Exception as stream_exc:
                    err = str(stream_exc)
                    if "Insufficient Authentication" in err or "authentication" in err.lower():
                        logger.warning(
                            "ECG stream needs pairing; calling OS pair() for %s",
                            bleak_device.address,
                        )
                        try:
                            await self._device._client.pair()
                            logger.info("Pairing completed; retrying ECG stream")
                        except Exception as pair_exc:
                            logger.warning("Pairing call failed: %s", pair_exc)
                        await self._device.start_ecg_stream(
                            ecg_callback=self._on_ecg_data,
                            sample_rate=ECG_SAMPLE_RATE,
                            resolution=14,
                        )
                    else:
                        raise

                logger.info("ECG stream started")
                self._running = True
                self._local_start = time.time()
                self._sample_count = 0
                return
            except Exception as exc:
                last_exc = exc
                err = str(exc)
                logger.warning(
                    "H10 connection attempt %d/%d failed: %s",
                    attempt,
                    max_attempts,
                    exc,
                )

                # If Windows already holds the connection, the failure usually
                # mentions GATT authentication or that the device is unavailable.
                if "Insufficient Authentication" in err or "authentication" in err.lower():
                    logger.warning(
                        "Pairing may be required. Remove the H10 from Windows Bluetooth, "
                        "put the strap back on to make it blink blue, and try again."
                    )

                if self._device is not None:
                    try:
                        await self._device.disconnect()
                    except Exception:
                        pass
                    self._device = None
                if attempt < max_attempts:
                    await asyncio.sleep(4.0)

        logger.exception("Failed to start H10 stream after %d attempts", max_attempts)
        if self.on_error and last_exc is not None:
            self.on_error(last_exc)
        raise last_exc if last_exc is not None else RuntimeError(
            "Failed to start H10 stream. If Windows shows the H10 as connected, "
            "remove it from Windows Bluetooth and let the app connect directly."
        )

    async def stop(self) -> None:
        """Stop streaming and disconnect."""
        if self._device is not None:
            try:
                await self._device.stop_ecg_stream()
            except Exception:
                pass
            try:
                await self._device.disconnect()
            except Exception:
                pass
            self._device = None
        self._running = False
        if self.on_connection_change:
            self.on_connection_change("disconnected")
        logger.info("H10 stream stopped")

    def _on_ecg_data(self, data: ECGData) -> None:
        """Receive ECGData from polar_python and forward ECGSamples."""
        try:
            samples_attr = getattr(data, "samples", None)
            if samples_attr is None:
                samples_attr = getattr(data, "data", None)
            if samples_attr is None:
                return

            values = list(samples_attr)
            if not values:
                return

            dt = 1.0 / ECG_SAMPLE_RATE
            samples: List[ECGSample] = []
            for i, value in enumerate(values):
                t = self._local_start + (self._sample_count + i) * dt
                samples.append(ECGSample(timestamp=t, value=float(value)))
            self._sample_count += len(values)

            if self.on_samples:
                self.on_samples(samples)
        except Exception as exc:
            logger.warning("ECG data callback error: %s", exc)
            if self.on_error:
                self.on_error(exc)

    async def __aenter__(self) -> "PolarH10Stream":
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.stop()


class PolarH10BufferedStream(PolarH10Stream):
    """PolarH10Stream that writes samples into an ECGBuffer."""

    def __init__(
        self,
        buffer: ECGBuffer,
        device_address: Optional[str] = None,
        device_name: str = "Polar H10",
        on_connection_change: Optional[Callable[[str], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
        on_samples_extra: Optional[Callable[[List[ECGSample]], None]] = None,
    ) -> None:
        def _on_samples(samples: List[ECGSample]) -> None:
            buffer.extend(samples)
            if on_samples_extra:
                on_samples_extra(samples)

        super().__init__(
            device_address=device_address,
            device_name=device_name,
            on_connection_change=on_connection_change,
            on_samples=_on_samples,
            on_error=on_error,
        )
        self.buffer = buffer
