"""Runtime 5-model hard-majority ensemble."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import torch

from flow_lol.inference.deep_models import (
    AppCNN1DClassifier,
    AppLSTMClassifier,
    AppMLPClassifier,
)
from flow_lol.utils.paths import models_dir

logger = logging.getLogger(__name__)




def _apply_z_standardiser(X: np.ndarray, scaler: dict[str, Any], valid_cols: np.ndarray | None = None) -> np.ndarray:
    """Apply mean/std normalisation from a fitted scaler dict.

    If ``valid_cols`` is provided and columns were actually dropped from ``X``,
    drop the same entries from mean/std before scaling. This keeps training and
    runtime column counts aligned when some features are NaN at runtime.
    """
    if not scaler.get("active", True):
        return X
    mean = scaler.get("mean_")
    std = scaler.get("std_")
    if mean is None or std is None:
        return X
    mean = np.array(mean)
    std = np.array(std)
    if (
        valid_cols is not None
        and mean.shape[0] == valid_cols.shape[0]
        and X.shape[1] == int(valid_cols.sum())
    ):
        mean = mean[valid_cols]
        std = std[valid_cols]
    return (X - mean) / std


def _apply_outlier(X: np.ndarray, outlier: dict[str, Any]) -> np.ndarray:
    """Return outlier-in-mask using stored IQR thresholds."""
    strategy = outlier.get("strategy", "none")
    if strategy == "none":
        return np.ones(len(X), dtype=bool)
    lower = outlier.get("lower_")
    upper = outlier.get("upper_")
    if lower is None or upper is None:
        return np.ones(len(X), dtype=bool)
    lower = np.array(lower)
    upper = np.array(upper)
    inside = np.all((X >= lower) & (X <= upper), axis=1)
    return inside


def _apply_baseline(X: np.ndarray, baseline: dict[str, Any]) -> np.ndarray:
    """Apply change-score or quotient baseline correction."""
    method = baseline.get("method", "none")
    if method == "none":
        return X
    b = baseline.get("baseline_")
    if b is None:
        return X
    b = np.array(b)
    if method == "change_score":
        return X - b
    if method == "quotient":
        b = np.where(b == 0, 1e-9, b)
        return X / b
    return X


class ClassifierEnsemble:
    """Load the five exported ECG-only models and produce a hard majority vote."""

    # Model names must match the filenames produced by scripts/export_models.py.
    ALL_MODELS = (
        "biraffe2_svm",
        "biraffe2_knn",
        "biraffe2_rf",
        "irshad_rf",
        "biraffe2_mlp",
        "biraffe2_lr",
        "biraffe2_xgb",
        "biraffe2_lstm",
        "biraffe2_cnn",
        "irshad_lr",
        "irshad_mlp",
    )

    def __init__(self, enabled_names: tuple[str, ...] = ALL_MODELS) -> None:
        self.enabled_names = enabled_names
        self.bundles: dict[str, dict[str, Any]] = {}
        self.feature_names: list[str] = []

    def load(self) -> None:
        root = models_dir()
        for name in self.enabled_names:
            path = root / f"{name}.joblib"
            if not path.exists():
                logger.warning("Model file not found: %s", path)
                continue
            bundle = joblib.load(path)
            self.bundles[name] = bundle
            fnames = bundle.get("feature_names", [])
            if not self.feature_names and fnames:
                self.feature_names = list(fnames)
            logger.info("Loaded model %s (%s)", name, bundle.get("metadata", {}).get("model_name", name))

    def _vector_from_features(self, features: dict[str, float], bundle: dict[str, Any]) -> np.ndarray:
        """Build a feature vector aligned with the model's training feature names."""
        fnames = bundle.get("feature_names", self.feature_names)
        return np.array([[features.get(name, np.nan) for name in fnames]])

    def _apply_bundle(self, bundle: dict[str, Any], X: np.ndarray) -> tuple[int, float | None]:
        """Return (label, probability_of_flow) after applying bundle preprocessing."""
        X = X.copy()

        # Baseline correction first (if the bundle uses it at runtime).
        baseline = bundle.get("baseline_corrector")
        if baseline is not None:
            X = _apply_baseline(X, baseline)

        # Identify all-NaN columns but do NOT drop them. The exported models were
        # trained on a fixed 12-feature vector; dropping columns at runtime makes
        # sklearn complain about mismatched feature counts. Instead, impute any
        # NaN with the training mean (which becomes 0 after z-score scaling).
        scaler = bundle.get("scaler")
        if scaler is not None and scaler.get("active", True):
            mean = scaler.get("mean_")
            if mean is not None:
                mean_arr = np.array(mean)
                for col_idx in range(X.shape[1]):
                    if col_idx < len(mean_arr) and np.isnan(X[0, col_idx]):
                        X[0, col_idx] = mean_arr[col_idx]
            X = _apply_z_standardiser(X, scaler)
        else:
            # No scaler: replace remaining NaN with 0 so the model sees a clean vector.
            X = np.nan_to_num(X, nan=0.0)

        # Outlier handling is kept as a data-quality flag but does not block
        # prediction; real-time users may have different distributions than
        # the training set.
        outlier = bundle.get("outlier_handler")
        if outlier is not None and outlier.get("strategy", "none") != "none":
            try:
                mask = _apply_outlier(X, outlier)
                if not mask[0]:
                    logger.debug("Window flagged as outlier by training thresholds")
            except Exception:
                pass

        model = bundle["model"]

        # Deep models are exported as plain dicts so the bundle has no research-package
        # dependency; reconstruct the app-side classifier here.
        if isinstance(model, dict) and model.get("type", "").startswith("torch_"):
            n_features = int(model.get("n_features", X.shape[1]))
            n_classes = int(model.get("n_classes", 2))
            model_type = model.get("type")
            if model_type == "torch_lstm":
                clf = AppLSTMClassifier(n_features=n_features, n_classes=n_classes, device="cpu")
            elif model_type == "torch_cnn1d":
                clf = AppCNN1DClassifier(n_features=n_features, n_classes=n_classes, device="cpu")
            else:
                clf = AppMLPClassifier(n_features=n_features, n_classes=n_classes, device="cpu")
            clf.model_.load_state_dict(model["state_dict"])
            mean = model.get("scaler_mean")
            std = model.get("scaler_std")
            if mean is not None and std is not None:
                clf.set_scaler(np.array(mean), np.array(std))

            label = int(clf.predict(X)[0])
            proba = None
            try:
                proba = float(clf.predict_proba(X)[0, 1])
            except Exception:
                pass
            return label, proba

        # Ensure deep-learning models run on CPU if the bundle was moved there.
        if hasattr(model, "device"):
            model.device = "cpu"
        if hasattr(model, "to"):
            try:
                model.to("cpu")
            except Exception:
                pass

        label = int(model.predict(X)[0])
        proba = None
        if hasattr(model, "predict_proba"):
            try:
                proba = float(model.predict_proba(X)[0, 1])
            except Exception:
                pass
        return label, proba

    @staticmethod
    def _majority_with_tiebreak(labels: list[int], probabilities: dict[str, float | None], votes: dict[str, int]) -> tuple[int, bool, int]:
        """Return (label, was_tie, n_for_label) using probabilities to break ties."""
        counts = np.bincount(labels)
        majority_label = int(counts.argmax())
        n_for_majority = int(sum(1 for v in labels if v == majority_label))

        # Check for an exact tie with the runner-up.
        if len(counts) > 1 and counts.max() == counts[1 - majority_label]:
            # Tie-break using mean P(flow) of models that voted each label.
            mean_proba: dict[int, list[float]] = {0: [], 1: []}
            for name, label in votes.items():
                proba = probabilities.get(name)
                if proba is not None:
                    mean_proba[label].append(proba)

            mean_0 = np.mean(mean_proba[0]) if mean_proba[0] else 0.5
            mean_1 = np.mean(mean_proba[1]) if mean_proba[1] else 0.5

            # Higher mean P(flow) means more confidence for label 1.
            if mean_1 > mean_0:
                return 1, True, n_for_majority
            if mean_0 > mean_1:
                return 0, True, n_for_majority

            # Even probabilities are tied: default to 0 for safety and log later.
            return 0, True, n_for_majority

        return majority_label, False, n_for_majority

    def predict(self, features: dict[str, float]) -> dict[str, Any]:
        """Run all loaded models and return votes plus the hard majority label."""
        votes: dict[str, int] = {}
        probabilities: dict[str, float | None] = {}

        for name, bundle in self.bundles.items():
            try:
                X = self._vector_from_features(features, bundle)
                label, proba = self._apply_bundle(bundle, X)
                votes[name] = label
                probabilities[name] = proba
            except Exception as exc:
                logger.error("Prediction failed for %s: %s", name, exc)

        if not votes:
            return {"error": "no model produced a vote"}

        labels = list(votes.values())
        n_votes = len(labels)
        majority_label, was_tie, n_for_majority = self._majority_with_tiebreak(
            labels, probabilities, votes
        )

        if was_tie:
            logger.warning(
                "Ensemble tie detected (%s vs %s). Tie-break label=%s",
                n_for_majority,
                n_votes - n_for_majority,
                majority_label,
            )

        return {
            "votes": votes,
            "probabilities": probabilities,
            "ensemble_label": majority_label,
            "n_votes": n_votes,
            "n_for_majority": n_for_majority,
            "tie_break": was_tie,
        }

    def is_ready(self) -> bool:
        return len(self.bundles) == len(self.enabled_names)
