"""Flow label creation from continuous GEQ scores."""
from typing import List, Tuple

import numpy as np

from flow_lol.utils.config import LabelConfig


class FlowLabeler:
    """Convert continuous flow scores into binary or discrete labels.

    Supports:
    - median split
    - median split with an exclusion margin band around the median
    - full GEQ Flow subscale vs. subscale without Time Distortion

    The margin is expressed as a fraction of the inter-quartile range (IQR).
    Scores inside [median - margin*IQR, median + margin*IQR] are excluded.
    """

    def __init__(self, config: LabelConfig):
        self.config = config

    def fit(self, scores: np.ndarray) -> "FlowLabeler":
        """Compute median and IQR on the available scores."""
        scores = np.asarray(scores, dtype=float)
        self.median_ = float(np.nanmedian(scores))
        q1 = float(np.nanquantile(scores, 0.25))
        q3 = float(np.nanquantile(scores, 0.75))
        self.iqr_ = q3 - q1
        self.low_threshold_ = self.median_ - self.config.margin * self.iqr_
        self.high_threshold_ = self.median_ + self.config.margin * self.iqr_
        return self

    def transform(self, scores: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Return labels and an inclusion mask.

        Labels are 0 = low flow, 1 = high flow. The mask is True for scores
        that are not inside the exclusion margin.
        """
        scores = np.asarray(scores, dtype=float)
        labels = np.full(len(scores), fill_value=-1, dtype=int)
        mask = np.ones(len(scores), dtype=bool)

        low = scores <= self.low_threshold_
        high = scores >= self.high_threshold_
        excluded = (scores > self.low_threshold_) & (scores < self.high_threshold_)

        labels[low] = 0
        labels[high] = 1
        mask[excluded] = False

        return labels, mask

    def fit_transform(self, scores: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        return self.fit(scores).transform(scores)

    def describe(self) -> dict:
        return {
            "method": self.config.method,
            "margin": self.config.margin,
            "items": self.config.items,
            "median": getattr(self, "median_", None),
            "iqr": getattr(self, "iqr_", None),
            "low_threshold": getattr(self, "low_threshold_", None),
            "high_threshold": getattr(self, "high_threshold_", None),
        }


def compute_flow_score(raw_items: np.ndarray, items: str = "full_subscale") -> np.ndarray:
    """Placeholder for item-level Flow score computation.

    BIRAFFE2 metadata already provides aggregated Flow scores, so this
    function currently returns the input unchanged. For datasets with raw
    item responses, implement item selection here (e.g. exclude Time Distortion).
    """
    if items == "full_subscale":
        return raw_items
    if items == "without_time_distortion":
        # When raw items are available, remove the Time Distortion column(s).
        # For pre-aggregated scores this is a no-op; the config controls which
        # aggregated column is read by the loader.
        return raw_items
    raise ValueError(f"Unknown item strategy: {items}")
