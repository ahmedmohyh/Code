"""Outlier handling strategies."""
from typing import Tuple

import numpy as np


class OutlierHandler:
    """Remove or flag outliers in the feature matrix.

    Strategies:
    - none: keep all rows
    - train_only: compute IQR thresholds on the training fold only, apply to train and test separately
    - full_data: compute thresholds on the full dataset (sensitivity check; may leak information)
    """

    def __init__(self, strategy: str = "train_only", factor: float = 1.5):
        self.strategy = strategy
        self.factor = factor
        self.lower_ = None
        self.upper_ = None

    def fit(self, X: np.ndarray) -> "OutlierHandler":
        if self.strategy == "none":
            return self
        q1 = np.nanquantile(X, 0.25, axis=0)
        q3 = np.nanquantile(X, 0.75, axis=0)
        iqr = q3 - q1
        self.lower_ = q1 - self.factor * iqr
        self.upper_ = q3 + self.factor * iqr
        return self

    def transform(self, X: np.ndarray) -> np.ndarray:
        if self.strategy == "none" or self.lower_ is None:
            return np.ones(len(X), dtype=bool)
        inside = np.all((X >= self.lower_) & (X <= self.upper_), axis=1)
        return inside

    def fit_transform(self, X: np.ndarray) -> np.ndarray:
        return self.fit(X).transform(X)
