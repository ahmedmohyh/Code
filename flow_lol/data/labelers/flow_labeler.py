"""Flow label creation from continuous GEQ scores."""
from typing import List, Tuple

import numpy as np
import pandas as pd

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


def compute_flow_score(raw_items, items: str = "full_subscale"):
    """Compute a Flow score from raw GEQ item responses.

    Parameters
    ----------
    raw_items:
        Either a pandas DataFrame with item-number columns (strings "5", "13",
        "25", "28", "31") or a 2-D numpy array whose last axis contains those
        five items in order.
    items:
        ``"full_subscale"`` uses items 5, 13, 25, 28, 31.
        ``"without_time_distortion"`` drops item 25 and uses 5, 13, 28, 31.

    Returns
    -------
    1-D array (or scalar for a single row) of mean Flow scores.
    """
    flow_items = ["5", "13", "25", "28", "31"]
    if items == "without_time_distortion":
        flow_items = ["5", "13", "28", "31"]
    elif items != "full_subscale":
        raise ValueError(f"Unknown item strategy: {items}")

    if hasattr(raw_items, "columns"):
        # pandas DataFrame
        values = pd.to_numeric(raw_items[flow_items], errors="coerce").to_numpy(dtype=float)
    else:
        arr = np.asarray(raw_items, dtype=float)
        # Assume last axis is in full-subscale order 5,13,25,28,31.
        item_order = ["5", "13", "25", "28", "31"]
        idx_map = {item: i for i, item in enumerate(item_order)}
        keep_idx = [idx_map[item] for item in flow_items]
        values = arr[..., keep_idx]
    return np.nanmean(values, axis=-1)
