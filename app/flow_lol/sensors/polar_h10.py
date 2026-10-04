"""Polar H10 BLE ECG streaming via bleak.

Implements the Polar H10 ECG service:
  Service UUID: 0000fe55-0000-1000-8000-00805f9b34fb
  ECG characteristic: 00002b24-0000-1000-8000-00805f9b34fb
  ACC characteristic: 00002b20-0000-1000-8000-00805f9b34fb  (not used here)
  PPG characteristic: 00002b21-0000-1000-8000-00805f9b34fb (Verity Sense)
  Control characteristic: 00002b22-0000-1000-8000-00805f9b34fb

The ECG stream is started by writing a start command to the control point and
subscribing to notifications on the ECG characteristic. Each notification
contains a 1-byte frame type (0xFB for ECG) followed by a timestamp and a
series of 16-bit signed ECG samples. The H10 ECG sampling rate is 130 Hz.
"""

from __future__ import annotations

import asyncio
import logging
import struct
import time
from dataclasses import dataclass
from typing import Callable, List, Optional

from bleak import BleakClient, BleakScanner

from flow_lol.sensors.buffer import ECGBuffer, ECGSample

logger = logging.getLogger(__name__)


# Polar H10 service / characteristic UUIDs
POLAR_ECG_SERVICE_UUID = "0000fe55-0000-1000-8000-00805f9b34fb"
POLAR_ECG_CHAR_UUID = "00002b24-0000-1000-8000-00805f9b34fb"
POLAR_CONTROL_CHAR_UUID = "00002b22-0000-1000-8000-00805f9b34fb"

# Sampling rates
ECG_SAMPLE_RATE = 130  # Hz for Polar H10 ECG


def _build_start_command(sample_rate: int) -> bytes:
    """Build the Polar stream start command.

    Command format (from unofficial Polar docs):
      [0x0B] [0x88] [sample_rate u8] [type] [u8] [u8] ...
    The common minimal command used by open-source tools is:
      b'\\x0b\\x88' + sample_rate.to_bytes(1, 'little')
    """
    return bytes([0x0B, 0x88]) + sample_rate.to_bytes(1, "little")


@dataclass
class ParsedECGFrame:
    """Parsed ECG notification payload."""

    timestamp: float
    samples: List[int]
    reference_time: float


def _parse_ecg_notification(data: bytes, first_ref_time: Optional[float] = None) -> ParsedECGFrame:
    """Parse one ECG notification frame.

    Format (reconstructed from Polar H10 docs and community code):
      byte 0: frame type (0xFB for ECG)
      bytes 1-8: reference timestamp (ns) as little-endian u64
      bytes 9-12: ? (reserved / frame counter)
      remaining bytes: int16 ECG samples, little-endian
    """
    if len(data) < 10 or data[0] != 0xFB:
        raise ValueError(f"Not an ECG frame: {data[:4].hex()}")

    # Reference timestamp in 1/1024 seconds since some epoch; we only need deltas.
    ref_ticks = struct.unpack_from("<Q", data, 1)[0]
    if first_ref_time is None:
        reference_time = time.time()
    else:
        reference_time = first_ref_time

    # Skip header. The exact header size varies by firmware; 10 bytes type+timestamp is common.
    sample_data = data[10:]
    n_samples = len(sample_data) // 2
    samples = struct.unpack(f"<{n_samples}h", sample_data[: n_samples * 2])

    # Map reference ticks to wall-clock time; 1 tick unit = 1/1024 s.
    timestamp = reference_time + (ref_ticks / 1024.0)
    return ParsedECGFrame(timestamp=timestamp, samples=list(samples), reference_time=reference_time)


class PolarH10Stream:
    """Async BLE client that streams ECG from a Polar H10."""

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

        self._client: Optional[BleakClient] = None
        self._running = False
        self._ref_time: Optional[float] = None
        self._local_start: float = 0.0
        self._sample_count = 0

    async def scan(self, timeout: float = 10.0) -> List[Tuple[str, str]]:
        """Return a list of (address, name) for nearby Polar H10 devices."""
        devices = await BleakScanner.discover(timeout=timeout)
        return [(d.address, d.name or "Unknown") for d in devices if d.name and self.device_name in d.name]

    async def start(self) -> None:
        """Connect and start ECG stream."""
        if self._running:
            return

        address = self.device_address
        if not address:
            candidates = await self.scan(timeout=10.0)
            if not candidates:
                raise RuntimeError(f"No {self.device_name} device found")
            address = candidates[0][0]
            logger.info("Auto-selected %s at %s", candidates[0][1], address)

        self._client = BleakClient(address)
        try:
            await self._client.connect()
            logger.info("Connected to %s", address)
            if self.on_connection_change:
                self.on_connection_change("connected")

            await self._client.start_notify(POLAR_ECG_CHAR_UUID, self._on_ecg_notification)
            await self._client.write_gatt_char(
                POLAR_CONTROL_CHAR_UUID,
                _build_start_command(ECG_SAMPLE_RATE),
                response=False,
            )
            logger.info("ECG stream started")
            self._running = True
            self._local_start = time.time()
            self._sample_count = 0
        except Exception as exc:
            logger.exception("Failed to start H10 stream")
            if self.on_error:
                self.on_error(exc)
            raise

    async def stop(self) -> None:
        """Stop notifications and disconnect."""
        if self._client and self._client.is_connected:
            try:
                await self._client.stop_notify(POLAR_ECG_CHAR_UUID)
            except Exception:
                pass
            try:
                await self._client.disconnect()
            except Exception:
                pass
        self._running = False
        if self.on_connection_change:
            self.on_connection_change("disconnected")
        logger.info("H10 stream stopped")

    def _on_ecg_notification(self, sender: int, data: bytearray) -> None:
        try:
            frame = _parse_ecg_notification(bytes(data), first_ref_time=self._ref_time)
            if self._ref_time is None:
                self._ref_time = frame.reference_time

            # Convert 130 Hz sample index offsets to wall-clock seconds.
            dt = 1.0 / ECG_SAMPLE_RATE
            samples: List[ECGSample] = []
            for i, value in enumerate(frame.samples):
                t = self._local_start + (self._sample_count + i) * dt
                samples.append(ECGSample(timestamp=t, value=float(value)))
            self._sample_count += len(frame.samples)

            if self.on_samples:
                self.on_samples(samples)
        except Exception as exc:
            logger.warning("ECG parse error: %s", exc)
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
