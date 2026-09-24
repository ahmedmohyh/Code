"""Deep-learning classifier interface (PyTorch)."""
import sys
from typing import Any, Dict, List, Optional

import numpy as np
import torch
import torch.nn as nn
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.preprocessing import StandardScaler


class DeepClassifierWrapper(BaseEstimator, ClassifierMixin):
    """Sklearn-compatible wrapper for PyTorch classifiers.

    Optimized for small tabular LOSO folds: CUDA if available, larger default
    batch size, non-blocking transfers, and optional ``torch.compile``.
    """

    def __init__(self, model_name: str = "MLP", n_features: int = 10,
                 n_classes: int = 2, max_epochs: int = 25, batch_size: int = 128,
                 lr: float = 1e-3, random_state: int = 42,
                 pin_memory: bool = False, compile_model: bool = False):
        self.model_name = model_name
        self.n_features = n_features
        self.n_classes = n_classes
        self.max_epochs = max_epochs
        self.batch_size = batch_size
        self.lr = lr
        self.random_state = random_state
        self.pin_memory = pin_memory
        self.compile_model = compile_model
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model_ = None
        self.scaler_ = StandardScaler()

    def fit(self, X: np.ndarray, y: np.ndarray):
        torch.manual_seed(self.random_state)
        # Avoid CPU oversubscription inside a worker when multiple folds run in
        # parallel; PyTorch CPU threads are not the bottleneck on a small network.
        torch.set_num_threads(1)

        Xs = self.scaler_.fit_transform(X)
        Xt = torch.tensor(Xs, dtype=torch.float32)
        yt = torch.tensor(y, dtype=torch.long)
        if self.pin_memory and self.device.type == "cuda":
            Xt = Xt.pin_memory().to(self.device, non_blocking=True)
            yt = yt.pin_memory().to(self.device, non_blocking=True)
        else:
            Xt = Xt.to(self.device)
            yt = yt.to(self.device)

        if self.model_name == "MLP":
            self.model_ = MLP(self.n_features, self.n_classes).to(self.device)
        elif self.model_name == "LSTM":
            self.model_ = LSTMClassifier(self.n_features, self.n_classes).to(self.device)
        elif self.model_name == "CNN1D":
            self.model_ = CNN1D(self.n_features, self.n_classes).to(self.device)
        else:
            raise ValueError(f"Unknown deep model: {self.model_name}")

        # torch.compile is disabled by default on Windows because the required
        # Triton backend is often missing; eager mode is safer and fast enough
        # for the tiny networks used in this LOSO pipeline.
        if self.compile_model and hasattr(torch, "compile") and self.device.type == "cuda" and sys.platform != "win32":
            try:
                self.model_ = torch.compile(self.model_)
            except Exception:
                pass  # torch.compile is optional; fall back to eager mode

        criterion = nn.CrossEntropyLoss()
        optimizer = torch.optim.Adam(self.model_.parameters(), lr=self.lr)

        dataset = torch.utils.data.TensorDataset(Xt, yt)
        loader = torch.utils.data.DataLoader(
            dataset,
            batch_size=min(self.batch_size, len(dataset)),
            shuffle=True,
            num_workers=0,  # Data is already in memory; workers add overhead
            pin_memory=self.pin_memory and self.device.type == "cuda",
        )

        self.model_.train()
        for _ in range(self.max_epochs):
            for xb, yb in loader:
                xb = xb.to(self.device, non_blocking=True)
                yb = yb.to(self.device, non_blocking=True)
                optimizer.zero_grad(set_to_none=True)
                out = self.model_(xb)
                loss = criterion(out, yb)
                loss.backward()
                optimizer.step()
        return self

    def _to_tensor(self, X: np.ndarray) -> torch.Tensor:
        Xs = self.scaler_.transform(X)
        Xt = torch.tensor(Xs, dtype=torch.float32)
        if self.pin_memory and self.device.type == "cuda":
            Xt = Xt.pin_memory().to(self.device, non_blocking=True)
        else:
            Xt = Xt.to(self.device)
        return Xt

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


class MLP(nn.Module):
    def __init__(self, n_features: int, n_classes: int):
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

    def forward(self, x):
        return self.net(x)


class LSTMClassifier(nn.Module):
    def __init__(self, n_features: int, n_classes: int, hidden: int = 64):
        super().__init__()
        self.lstm = nn.LSTM(n_features, hidden, batch_first=True)
        self.fc = nn.Linear(hidden, n_classes)

    def forward(self, x):
        x = x.unsqueeze(1)  # (batch, 1, features)
        _, (hn, _) = self.lstm(x)
        return self.fc(hn.squeeze(0))


class CNN1D(nn.Module):
    def __init__(self, n_features: int, n_classes: int):
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv1d(1, 16, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.MaxPool1d(2),
            nn.Conv1d(16, 32, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.MaxPool1d(2),
        )
        self.fc = nn.Linear(32 * (n_features // 4), n_classes)

    def forward(self, x):
        x = x.unsqueeze(1)  # (batch, 1, features)
        x = self.conv(x)
        x = x.view(x.size(0), -1)
        return self.fc(x)


def build_deep_classifier(name: str, n_features: int, n_classes: int = 2,
                          random_state: int = 42, max_epochs: int = 25,
                          batch_size: int = 128) -> Any:
    return DeepClassifierWrapper(
        model_name=name,
        n_features=n_features,
        n_classes=n_classes,
        max_epochs=max_epochs,
        batch_size=batch_size,
        random_state=random_state,
    )
