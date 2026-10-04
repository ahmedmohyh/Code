"""ECG sample buffering and sliding-window creation."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Iterator


@dataclass
class ECGSample:
    """One ECG sample with a monotonic timestamp in seconds."""

    timestamp: float
    value: float


class ECGBuffer:
    """Thread-safe-by-GIL ring buffer for streaming ECG samples."""

    def __init__(self, capacity: int = 50000) -> None:
        self._samples: deque[ECGSample] = deque(maxlen=capacity)

    def append(self, sample: ECGSample) -> None:
        self._samples.append(sample)

    def windows(
        self, window_seconds: float, overlap_percent: float
    ) -> Iterator[tuple[float, list[ECGSample]]]:
        """Yield (start_timestamp, samples) windows from the current buffer.

        The iterator returns the newest complete window each time it is called.
        For real-time use, callers should poll this at the requested step size.
        """
        if not self._samples:
            return

        samples = list(self._samples)
        end = samples[-1].timestamp
        start = end - window_seconds
        step = window_seconds * (1.0 - overlap_percent / 100.0)

        # For now, return only the single latest window.
        window_samples = [s for s in samples if start <= s.timestamp <= end]
        yield start, window_samples

        # Future: yield historical windows spaced by `step` for offline replay.
        _ = step  # silence unused until fully implemented
