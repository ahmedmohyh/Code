"""Leave-one-subject-out cross-validation with optional parallel folds."""
import sys
from typing import Any, Dict, List

import numpy as np
from joblib import Parallel, delayed, cpu_count
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, roc_auc_score
from tqdm import tqdm

from flow_lol.preprocessing.normaliser import ZStandardiser
from flow_lol.preprocessing.outlier_handler import OutlierHandler
from flow_lol.validation.metrics import add_inference_time, compute_metrics, compute_permutation_importance


def _run_single_fold(
    test_subject: int,
    subjects: List[int],
    X_by_subject: Dict[int, np.ndarray],
    y_by_subject: Dict[int, np.ndarray],
    model_builder,
    z_standardise: bool,
    outlier_strategy: str,
    run_permutation: bool,
    feature_names: List[str],
):
    """Run one LOSO fold and return metrics."""
    train_subjects = [s for s in subjects if s != test_subject]

    X_train = np.vstack([X_by_subject[s] for s in train_subjects])
    y_train = np.hstack([y_by_subject[s] for s in train_subjects])

    X_test = X_by_subject[test_subject]
    y_test = y_by_subject[test_subject]

    # Outlier handling
    outlier = OutlierHandler(strategy=outlier_strategy)
    if outlier_strategy == "train_only":
        train_mask = outlier.fit_transform(X_train)
        test_mask = outlier.transform(X_test)
    elif outlier_strategy == "full_data":
        full_X = np.vstack([X_train, X_test])
        full_mask = outlier.fit_transform(full_X)
        train_mask = full_mask[:len(X_train)]
        test_mask = full_mask[len(X_train):]
    else:
        train_mask = np.ones(len(X_train), dtype=bool)
        test_mask = np.ones(len(X_test), dtype=bool)

    X_train = X_train[train_mask]
    y_train = y_train[train_mask]
    X_test = X_test[test_mask]
    y_test = y_test[test_mask]

    # Z-standardisation
    scaler = ZStandardiser(active=z_standardise)
    X_train = scaler.fit_transform(X_train)
    X_test = scaler.transform(X_test)

    # Impute
    from flow_lol.features.feature_union import impute_missing
    X_train = impute_missing(X_train, strategy="median")
    X_test = impute_missing(X_test, strategy="median")

    # Drop columns that are all-NaN in the combined data; scikit-learn models
    # cannot handle entirely non-informative columns.
    full_X = np.vstack([X_train, X_test])
    valid_cols = ~np.all(np.isnan(full_X), axis=0)
    if not np.all(valid_cols):
        X_train = X_train[:, valid_cols]
        X_test = X_test[:, valid_cols]

    if len(np.unique(y_train)) < 2 or X_train.shape[0] == 0 or X_test.shape[0] == 0:
        return {
            "test_subject": test_subject,
            "n_train": int(len(y_train)),
            "n_test": int(len(y_test)),
            "accuracy": np.nan,
            "f1_macro": np.nan,
            "precision_low": np.nan,
            "recall_low": np.nan,
            "precision_high": np.nan,
            "recall_high": np.nan,
            "auc": np.nan,
            "inference_ms": np.nan,
            "skipped": True,
        }

    try:
        model = model_builder()
        model.fit(X_train, y_train)

        y_pred = model.predict(X_test)
        y_proba = None
        if hasattr(model, "predict_proba"):
            try:
                y_proba = model.predict_proba(X_test)
            except Exception:
                pass

        inference_ms = add_inference_time(model, X_test)
        fold_metrics = compute_metrics(y_test, y_pred, y_proba, classes=[0, 1])
        fold_metrics["inference_ms"] = inference_ms

        # Subject-level aggregation: one prediction per test subject.
        # Required for a meaningful ROC-AUC in BIRAFFE2 because all windows
        # of a subject share the same label, so window-level AUC is undefined.
        subject_true = int(np.bincount(y_test.astype(int)).argmax())
        subject_pred = int(np.bincount(y_pred.astype(int)).argmax())
        if y_proba is not None:
            subject_score = float(np.mean(y_proba[:, 1] if y_proba.ndim > 1 else y_proba))
        else:
            subject_score = float(subject_pred)
        fold_metrics["subject_true"] = subject_true
        fold_metrics["subject_pred"] = subject_pred
        fold_metrics["subject_score"] = subject_score
    except Exception as e:
        fold_metrics = {
            "accuracy": np.nan,
            "f1_macro": np.nan,
            "precision_low": np.nan,
            "recall_low": np.nan,
            "precision_high": np.nan,
            "recall_high": np.nan,
            "auc": np.nan,
            "inference_ms": np.nan,
            "fit_error": str(e),
        }

    fold_metrics["test_subject"] = test_subject
    fold_metrics["n_train"] = int(len(y_train))
    fold_metrics["n_test"] = int(len(y_test))

    if run_permutation and feature_names is not None:
        fold_metrics["permutation_importance"] = compute_permutation_importance(
            X_test, y_test, model, feature_names, n_repeats=5
        )

    return fold_metrics


def _mean(values):
    arr = np.asarray(values, dtype=float)
    arr = arr[~np.isnan(arr)]
    return float(np.mean(arr)) if len(arr) else np.nan


def _subject_level_aggregate(fold_results: List[Dict]) -> Dict:
    """Compute aggregate metrics from one prediction per subject.

    BIRAFFE2 has one global label per subject, so window-level test folds are
    single-class. Aggregating to one score/label per subject gives a valid
    ROC-AUC and a more meaningful accuracy/F1 for the thesis.
    """
    valid = [f for f in fold_results if "subject_true" in f]
    if not valid:
        return {}

    y_true = np.array([f["subject_true"] for f in valid])
    y_pred = np.array([f["subject_pred"] for f in valid])
    y_score = np.array([f["subject_score"] for f in valid])
    classes = [0, 1]

    precisions = precision_score(y_true, y_pred, labels=classes, average=None, zero_division=0)
    recalls = recall_score(y_true, y_pred, labels=classes, average=None, zero_division=0)

    agg = {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "f1_macro": float(f1_score(y_true, y_pred, average="macro", zero_division=0)),
        "precision_low": float(precisions[0]),
        "recall_low": float(recalls[0]),
        "precision_high": float(precisions[1]),
        "recall_high": float(recalls[1]),
        "auc": np.nan,
        "n_subjects_used": int(len(valid)),
    }
    if len(np.unique(y_true)) == 2:
        try:
            agg["auc"] = float(roc_auc_score(y_true, y_score))
        except Exception:
            pass
    return agg


def run_loso_cv(
    X_by_subject: Dict[int, np.ndarray],
    y_by_subject: Dict[int, np.ndarray],
    model_builder,
    z_standardise: bool = True,
    outlier_strategy: str = "train_only",
    run_permutation: bool = False,
    feature_names: List[str] = None,
    random_state: int = 42,
    n_jobs: int = 1,
) -> Dict:
    """Run LOSO cross-validation, optionally in parallel.

    n_jobs controls fold parallelism. Use n_jobs=5 with models using 4 cores each
    to saturate a 20-core CPU without oversubscription.
    """
    subjects = sorted(X_by_subject.keys())

    if n_jobs == -1:
        n_jobs = max(1, cpu_count() // 4)

    if n_jobs > 1:
        fold_results = Parallel(n_jobs=n_jobs, backend="loky", verbose=0)(
            delayed(_run_single_fold)(
                test_subject, subjects, X_by_subject, y_by_subject,
                model_builder, z_standardise, outlier_strategy,
                run_permutation, feature_names
            )
            for test_subject in tqdm(
                subjects,
                desc=f"LOSO folds ({n_jobs} workers)",
                file=sys.stdout,
                position=0,
                leave=True,
                ascii=True,
                ncols=80,
                mininterval=2,
            )
        )
        fold_results = [f for f in fold_results if f is not None]
    else:
        fold_results = []
        pbar = tqdm(
            subjects,
            desc="LOSO folds",
            file=sys.stdout,
            position=0,
            leave=True,
            ascii=True,
            ncols=80,
            mininterval=2,
        )
        for test_subject in pbar:
            f = _run_single_fold(
                test_subject, subjects, X_by_subject, y_by_subject,
                model_builder, z_standardise, outlier_strategy,
                run_permutation, feature_names
            )
            if f is None:
                continue
            fold_results.append(f)
            pbar.set_postfix({
                "acc": f"{f['accuracy']:.3f}",
                "f1": f"{f['f1_macro']:.3f}",
            })
        pbar.close()

    if not fold_results:
        return {"fold_results": [], "aggregate": {}}

    window_aggregate = {
        "accuracy": _mean([f["accuracy"] for f in fold_results]),
        "f1_macro": _mean([f["f1_macro"] for f in fold_results]),
        "precision_low": _mean([f["precision_low"] for f in fold_results]),
        "recall_low": _mean([f["recall_low"] for f in fold_results]),
        "precision_high": _mean([f["precision_high"] for f in fold_results]),
        "recall_high": _mean([f["recall_high"] for f in fold_results]),
        "auc": _mean([f["auc"] for f in fold_results]),
        "mean_inference_ms": _mean([f["inference_ms"] for f in fold_results]),
        "n_subjects": len(subjects),
        "n_skipped": int(sum(f.get("skipped", False) for f in fold_results)),
        "n_fit_errors": int(sum("fit_error" in f for f in fold_results)),
    }

    subject_aggregate = _subject_level_aggregate(fold_results)

    return {
        "fold_results": fold_results,
        "aggregate": window_aggregate,
        "subject_aggregate": subject_aggregate,
        "n_subjects": len(subjects),
    }
