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
    """Thread-safe-by-GIL ring buffer for streaming ECG samples.

    Keeps the last ``capacity`` samples. Callers can request the newest
    complete window or enumerate historical windows at a configured step.
    """

    def __init__(self, capacity: int = 50000) -> None:
        self._samples: deque[ECGSample] = deque(maxlen=capacity)
        self._last_window_end: float = 0.0

    def append(self, sample: ECGSample) -> None:
        self._samples.append(sample)

    def extend(self, samples: list[ECGSample]) -> None:
        self._samples.extend(samples)

    def latest_window(
        self, window_seconds: float
    ) -> tuple[float, list[ECGSample]] | None:
        """Return the most recent complete window of ``window_seconds`` length."""
        if not self._samples:
            return None

        samples = list(self._samples)
        end = samples[-1].timestamp
        start = end - window_seconds
        if start < samples[0].timestamp:
            return None  # Not enough data yet.

        window = [s for s in samples if start <= s.timestamp <= end]
        return start, window

    def new_windows(
        self, window_seconds: float, overlap_percent: float
    ) -> Iterator[tuple[float, list[ECGSample]]]:
        """Yield windows that have become complete since the last call.

        The step size is ``window_seconds * (1 - overlap_percent / 100)``.
        Windows are only emitted once and only when complete.
        """
        if not self._samples:
            return

        step = window_seconds * (1.0 - overlap_percent / 100.0)
        if step <= 0:
            return

        samples = list(self._samples)
        end = samples[-1].timestamp
        latest_complete_end = end - window_seconds
        if latest_complete_end <= self._last_window_end:
            return

        start_times: list[float] = []
        t = self._last_window_end + step
        # Ensure first emitted window covers ``window_seconds`` back from t.
        t = max(t, samples[0].timestamp + window_seconds)
        while t <= end:
            start_times.append(t - window_seconds)
            t += step

        if not start_times:
            return

        self._last_window_end = start_times[-1] + window_seconds
        for start in start_times:
            window = [s for s in samples if start <= s.timestamp < start + window_seconds]
            yield start, window

    def clear(self) -> None:
        self._samples.clear()
        self._last_window_end = 0.0

    def __len__(self) -> int:
        return len(self._samples)
