"""Baseline correction strategies."""
from typing import Optional

import numpy as np


class BaselineCorrector:
    """Apply baseline correction to window-level features.

    Methods:
    - none: return features unchanged
    - change_score: X - baseline
    - quotient: X / baseline
    """

    def __init__(self, method: str = "none"):
        if method not in ("none", "change_score", "quotient"):
            raise ValueError(f"Unknown baseline correction method: {method}")
        self.method = method
        self.baseline_ = None

    def fit(self, baseline_features: np.ndarray) -> "BaselineCorrector":
        if self.method == "none":
            return self
        self.baseline_ = np.nanmean(baseline_features, axis=0)
        self.baseline_ = np.where(self.baseline_ == 0, 1e-9, self.baseline_)
        return self

    def transform(self, X: np.ndarray) -> np.ndarray:
        if self.method == "none" or self.baseline_ is None:
            return X
        if self.method == "change_score":
            return X - self.baseline_
        if self.method == "quotient":
            return X / self.baseline_
        return X

    def fit_transform(self, baseline_features: np.ndarray, X: np.ndarray) -> np.ndarray:
        return self.fit(baseline_features).transform(X)
