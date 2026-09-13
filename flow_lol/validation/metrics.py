"""Classification metrics for flow detection."""
import time
from typing import Dict, Optional

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


EDA_FEATURES = {
    "SCL_mean", "SCL_std", "phasic_max", "phasic_sum",
    "SCR_count", "SCR_rate",
}

_FACE_EMOTIONS = [
    "NEUTRAL", "HAPPINESS", "ANGER", "CONTEMPT", "DISGUST",
    "FEAR", "SADNESS", "SURPRISE",
]
FACE_FEATURES = {"face_observations"}
for _emotion in _FACE_EMOTIONS:
    for _stat in ("mean", "std", "max"):
        FACE_FEATURES.add(f"{_emotion}_{_stat}")


def feature_group(name: str) -> str:
    """Assign a feature name to ECG, EDA, or FACE family."""
    if name in EDA_FEATURES:
        return "EDA"
    if name in FACE_FEATURES:
        return "FACE"
    return "ECG"


def compute_permutation_importance(X: np.ndarray, y: np.ndarray, model,
                                   feature_names: list, n_repeats: int = 10,
                                   random_state: int = 42) -> Dict:
    """Shuffle each feature column and measure the mean drop in accuracy.

    Returns a dict mapping feature name -> mean accuracy drop.
    """
    baseline_preds = model.predict(X)
    baseline_acc = accuracy_score(y, baseline_preds)
    importances = {}
    rng = np.random.default_rng(random_state)
    for i, name in enumerate(feature_names):
        scores = []
        for _ in range(n_repeats):
            X_perm = X.copy()
            rng.shuffle(X_perm[:, i])
            preds = model.predict(X_perm)
            scores.append(baseline_acc - accuracy_score(y, preds))
        importances[name] = float(np.mean(scores))
    return importances


def aggregate_permutation_importance(fold_results: list) -> Optional[Dict]:
    """Average per-feature permutation importance across LOSO folds.

    Returns
    -------
    dict with keys:
      - per_feature: {name: {mean, std, group, n_folds}}
      - per_group:   {group: {mean, std, n_features, top_feature}}
      - n_folds:     number of folds that contributed
    """
    importances = [f["permutation_importance"] for f in fold_results
                   if "permutation_importance" in f]
    if not importances:
        return None

    all_names = set().union(*importances)
    per_feature = {}
    for name in sorted(all_names):
        vals = [d[name] for d in importances if name in d]
        per_feature[name] = {
            "mean": float(np.mean(vals)),
            "std": float(np.std(vals)),
            "group": feature_group(name),
            "n_folds": len(vals),
        }

    group_features = {}
    for name, stats in per_feature.items():
        group = stats["group"]
        group_features.setdefault(group, []).append((name, stats["mean"]))

    per_group = {}
    for group, items in group_features.items():
        means = [m for _, m in items]
        top_name, top_mean = max(items, key=lambda x: x[1])
        per_group[group] = {
            "mean": float(np.mean(means)),
            "std": float(np.std(means)),
            "n_features": len(items),
            "top_feature": top_name,
            "top_feature_score": float(top_mean),
        }

    return {
        "per_feature": per_feature,
        "per_group": per_group,
        "n_folds": len(importances),
    }
