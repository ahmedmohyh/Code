"""Self-contained PyTorch deep classifiers for the app runtime.

These mirror the architectures in flow_lol.models.deep so exported bundles can
be loaded without the research package.
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


class LSTM(nn.Module):
    """Single-layer LSTM over a single time step: (batch, 1, features)."""

    def __init__(self, n_features: int, n_classes: int = 2, hidden: int = 64) -> None:
        super().__init__()
        self.lstm = nn.LSTM(n_features, hidden, batch_first=True)
        self.fc = nn.Linear(hidden, n_classes)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = x.unsqueeze(1)  # (batch, 1, features)
        _, (hn, _) = self.lstm(x)
        return self.fc(hn.squeeze(0))


class CNN1D(nn.Module):
    """1-D CNN over the feature vector: (batch, 1, features).

    Requires ``n_features`` to be divisible by 4 because of two MaxPool1d(2)
    layers. The exporter must reject or pad incompatible feature counts.
    """

    def __init__(self, n_features: int, n_classes: int = 2) -> None:
        super().__init__()
        if n_features % 4 != 0:
            raise ValueError(f"CNN1D requires n_features divisible by 4, got {n_features}")
        self.conv = nn.Sequential(
            nn.Conv1d(1, 16, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.MaxPool1d(2),
            nn.Conv1d(16, 32, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.MaxPool1d(2),
        )
        self.fc = nn.Linear(32 * (n_features // 4), n_classes)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = x.unsqueeze(1)  # (batch, 1, features)
        x = self.conv(x)
        x = x.view(x.size(0), -1)
        return self.fc(x)


class _AppTorchClassifier(BaseEstimator, ClassifierMixin):
    """Shared sklearn-compatible wrapper for app-side torch classifiers."""

    _model_cls = MLP

    def __init__(
        self,
        n_features: int = 12,
        n_classes: int = 2,
        device: str = "cpu",
    ) -> None:
        self.n_features = n_features
        self.n_classes = n_classes
        self.device = device
        self.model_ = self._model_cls(n_features, n_classes).to(device)
        self.scaler_mean_: np.ndarray | None = None
        self.scaler_std_: np.ndarray | None = None

    def set_scaler(self, mean: np.ndarray | None, std: np.ndarray | None) -> None:
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


class AppMLPClassifier(_AppTorchClassifier):
    """Sklearn-compatible wrapper around the app-side MLP."""

    _model_cls = MLP


class AppLSTMClassifier(_AppTorchClassifier):
    """Sklearn-compatible wrapper around the app-side LSTM."""

    _model_cls = LSTM


class AppCNN1DClassifier(_AppTorchClassifier):
    """Sklearn-compatible wrapper around the app-side CNN1D."""

    _model_cls = CNN1D
