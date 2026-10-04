"""Self-contained PyTorch MLP for the app runtime.

This mirrors the architecture used by the research pipeline's
flow_lol.models.deep.MLP so exported bundles can be loaded without the
research package.
"""

from __future__ import annotations

import numpy as np
import torch
import torch.nn as nn
from sklearn.base import BaseEstimator, ClassifierMixin


class MLP(nn.Module):
    """Simple fully-connected MLP: n_features -> 128 -> 64 -> n_classes."""

    def __init__(self, n_features: int, n_classes: int = 2) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(n_features, 128),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(64, n_classes),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


class AppMLPClassifier(BaseEstimator, ClassifierMixin):
    """Sklearn-compatible wrapper around the app-side MLP.

    Behaves like the research DeepClassifierWrapper but is fully self-contained.
    """

    def __init__(
        self,
        n_features: int = 12,
        n_classes: int = 2,
        device: str = "cpu",
    ) -> None:
        self.n_features = n_features
        self.n_classes = n_classes
        self.device = device
        self.model_ = MLP(n_features, n_classes).to(device)
        self.scaler_mean_: np.ndarray | None = None
        self.scaler_std_: np.ndarray | None = None

    def set_scaler(self, mean: np.ndarray | None, std: np.ndarray | None) -> None:
        """Store the z-standardisation parameters already applied to training data."""
        self.scaler_mean_ = mean
        self.scaler_std_ = std

    def _scale(self, X: np.ndarray) -> np.ndarray:
        if self.scaler_mean_ is None or self.scaler_std_ is None:
            return X
        return (X - self.scaler_mean_) / self.scaler_std_

    def _to_tensor(self, X: np.ndarray) -> torch.Tensor:
        Xs = self._scale(X)
        return torch.tensor(Xs, dtype=torch.float32, device=self.device)

    def predict(self, X: np.ndarray) -> np.ndarray:
        self.model_.eval()
        Xt = self._to_tensor(X)
        with torch.no_grad():
            out = self.model_(Xt)
            preds = torch.argmax(out, dim=1).cpu().numpy()
        return preds

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        self.model_.eval()
        Xt = self._to_tensor(X)
        with torch.no_grad():
            out = torch.softmax(self.model_(Xt), dim=1).cpu().numpy()
        return out
