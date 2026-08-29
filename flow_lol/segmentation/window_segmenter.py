"""Signal windowing / segmentation."""
from typing import List, Dict

import numpy as np


class WindowSegmenter:
    """Segment a continuous signal into analysis windows.

    Modes:
    - sliding: windows of length window_length_s with step_s overlap
    - fixed: non-overlapping windows of length window_length_s (step = window_length_s)
    """

    def __init__(self, window_length_s: int = 60, step_s: int = 30, sampling_rate: float = 1000.0):
        self.window_length_s = window_length_s
        self.step_s = step_s
        self.sampling_rate = sampling_rate
        self.window_samples = int(window_length_s * sampling_rate)
        self.step_samples = int(step_s * sampling_rate)

    def segment(self, signal: np.ndarray) -> List[Dict]:
        """Return list of windows with start/end sample indices."""
        n = len(signal)
        windows = []
        start = 0
        while start + self.window_samples <= n:
            end = start + self.window_samples
            windows.append({
                "start_sample": start,
                "end_sample": end,
                "start_s": start / self.sampling_rate,
                "end_s": end / self.sampling_rate,
                "signal": signal[start:end],
            })
            start += self.step_samples
        return windows
