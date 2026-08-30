"""Deep-learning classifier interface (PyTorch)."""
from typing import Any, Dict, List, Optional

import numpy as np
import torch
import torch.nn as nn
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.preprocessing import StandardScaler


class DeepClassifierWrapper(BaseEstimator, ClassifierMixin):
    """Sklearn-compatible wrapper for PyTorch classifiers."""

    def __init__(self, model_name: str = "MLP", n_features: int = 10,
                 n_classes: int = 2, max_epochs: int = 50, batch_size: int = 32,
                 lr: float = 1e-3, random_state: int = 42):
        self.model_name = model_name
        self.n_features = n_features
        self.n_classes = n_classes
        self.max_epochs = max_epochs
        self.batch_size = batch_size
        self.lr = lr
        self.random_state = random_state
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model_ = None
        self.scaler_ = StandardScaler()

    def fit(self, X: np.ndarray, y: np.ndarray):
        torch.manual_seed(self.random_state)
        Xs = self.scaler_.fit_transform(X)
        Xt = torch.tensor(Xs, dtype=torch.float32).to(self.device)
        yt = torch.tensor(y, dtype=torch.long).to(self.device)

        if self.model_name == "MLP":
            self.model_ = MLP(self.n_features, self.n_classes).to(self.device)
        elif self.model_name == "LSTM":
            self.model_ = LSTMClassifier(self.n_features, self.n_classes).to(self.device)
        elif self.model_name == "CNN1D":
            self.model_ = CNN1D(self.n_features, self.n_classes).to(self.device)
        else:
            raise ValueError(f"Unknown deep model: {self.model_name}")

        criterion = nn.CrossEntropyLoss()
        optimizer = torch.optim.Adam(self.model_.parameters(), lr=self.lr)

        dataset = torch.utils.data.TensorDataset(Xt, yt)
        loader = torch.utils.data.DataLoader(dataset, batch_size=self.batch_size, shuffle=True)

        self.model_.train()
        for _ in range(self.max_epochs):
            for xb, yb in loader:
                optimizer.zero_grad()
                out = self.model_(xb)
                loss = criterion(out, yb)
                loss.backward()
                optimizer.step()
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        self.model_.eval()
        Xs = self.scaler_.transform(X)
        Xt = torch.tensor(Xs, dtype=torch.float32).to(self.device)
        with torch.no_grad():
            out = self.model_(Xt)
            preds = torch.argmax(out, dim=1).cpu().numpy()
        return preds

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        self.model_.eval()
        Xs = self.scaler_.transform(X)
        Xt = torch.tensor(Xs, dtype=torch.float32).to(self.device)
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


def build_deep_classifier(name: str, n_features: int, n_classes: int = 2, random_state: int = 42) -> Any:
    return DeepClassifierWrapper(model_name=name, n_features=n_features, n_classes=n_classes, random_state=random_state)
