"""Classification metrics for flow detection."""
import time
from typing import Dict

import numpy as np
from sklearn.metrics import (accuracy_score, f1_score, precision_score, recall_score, roc_auc_score,
                             confusion_matrix)


def compute_metrics(y_true: np.ndarray, y_pred: np.ndarray, y_proba: np.ndarray,
                    classes: list = None) -> Dict:
    """Compute all required metrics."""
    if classes is None:
        classes = sorted(np.unique(y_true).tolist())

    metrics = {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "f1_macro": float(f1_score(y_true, y_pred, average="macro", zero_division=0)),
    }

    # Per-class precision and recall
    precisions = precision_score(y_true, y_pred, labels=classes, average=None, zero_division=0)
    recalls = recall_score(y_true, y_pred, labels=classes, average=None, zero_division=0)
    for cls, p, r in zip(classes, precisions, recalls):
        label_name = "low" if cls == 0 else "high"
        metrics[f"precision_{label_name}"] = float(p)
        metrics[f"recall_{label_name}"] = float(r)

    # AUC
    if len(classes) == 2 and y_proba is not None:
        try:
            metrics["auc"] = float(roc_auc_score(y_true, y_proba[:, 1] if y_proba.ndim > 1 else y_proba))
        except Exception:
            metrics["auc"] = np.nan
    else:
        metrics["auc"] = np.nan

    metrics["confusion_matrix"] = confusion_matrix(y_true, y_pred, labels=classes).tolist()
    return metrics


def add_inference_time(model, X_test: np.ndarray, n_runs: int = 3) -> float:
    """Measure average inference time in milliseconds."""
    times = []
    for _ in range(n_runs):
        t0 = time.perf_counter()
        model.predict(X_test)
        times.append((time.perf_counter() - t0) * 1000.0)
    return float(np.mean(times))


def compute_permutation_importance(X: np.ndarray, y: np.ndarray, model,
                                   feature_names: list, n_repeats: int = 10) -> Dict:
    """Shuffle each feature group and measure drop in accuracy."""
    baseline_preds = model.predict(X)
    baseline_acc = accuracy_score(y, baseline_preds)
    importances = {}
    rng = np.random.default_rng(42)
    for i, name in enumerate(feature_names):
        scores = []
        for _ in range(n_repeats):
            X_perm = X.copy()
            rng.shuffle(X_perm[:, i])
            preds = model.predict(X_perm)
            scores.append(baseline_acc - accuracy_score(y, preds))
        importances[name] = float(np.mean(scores))
    return importances
