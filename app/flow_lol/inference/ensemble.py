"""Runtime 5-model hard-majority ensemble."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import joblib
import numpy as np

from flow_lol.utils.paths import models_dir

logger = logging.getLogger(__name__)


class ClassifierEnsemble:
    """Load the five exported ECG-only models and produce a hard majority vote."""

    # Model names must match the filenames produced by scripts/export_models.py.
    ALL_MODELS = (
        "biraffe2_svm",
        "biraffe2_knn",
        "biraffe2_rf",
        "irshad_rf",
        "biraffe2_mlp",
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

        # Drop all-NaN columns that were dropped during training.
        valid_cols = ~np.all(np.isnan(X), axis=0)
        X = X[:, valid_cols]

        # Z-standardisation using training statistics.
        scaler = bundle.get("scaler")
        if scaler is not None and getattr(scaler, "active", True):
            X = scaler.transform(X)

        # Outlier handling is kept as a data-quality flag but does not block
        # prediction; real-time users may have different distributions than
        # the training set.
        outlier = bundle.get("outlier_handler")
        if outlier is not None and getattr(outlier, "strategy", "none") != "none":
            try:
                mask = outlier.transform(X)
                if not mask[0]:
                    logger.debug("Window flagged as outlier by training thresholds")
            except Exception:
                pass

        model = bundle["model"]
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
        majority_label = int(np.bincount(labels).argmax())
        n_votes = len(labels)
        n_for_majority = int(sum(1 for v in labels if v == majority_label))

        return {
            "votes": votes,
            "probabilities": probabilities,
            "ensemble_label": majority_label,
            "n_votes": n_votes,
            "n_for_majority": n_for_majority,
        }

    def is_ready(self) -> bool:
        return len(self.bundles) == len(self.enabled_names)
