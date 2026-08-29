"""Z-standardisation switch (per fold)."""
import numpy as np


class ZStandardiser:
    """Fit on training data, transform train and test."""

    def __init__(self, active: bool = True):
        self.active = active
        self.mean_ = None
        self.std_ = None

    def fit(self, X: np.ndarray) -> "ZStandardiser":
        if self.active:
            self.mean_ = np.nanmean(X, axis=0)
            self.std_ = np.nanstd(X, axis=0)
            self.std_ = np.where(self.std_ == 0, 1.0, self.std_)
        return self

    def transform(self, X: np.ndarray) -> np.ndarray:
        if not self.active or self.mean_ is None:
            return X
        return (X - self.mean_) / self.std_

    def fit_transform(self, X: np.ndarray) -> np.ndarray:
        return self.fit(X).transform(X)
