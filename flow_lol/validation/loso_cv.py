"""Leave-one-subject-out cross-validation."""
from typing import Any, Dict, List

import numpy as np
from tqdm import tqdm

from flow_lol.preprocessing.normaliser import ZStandardiser
from flow_lol.preprocessing.outlier_handler import OutlierHandler
from flow_lol.validation.metrics import add_inference_time, compute_metrics, compute_permutation_importance


def run_loso_cv(X_by_subject: Dict[int, np.ndarray],
                y_by_subject: Dict[int, np.ndarray],
                model_builder,
                z_standardise: bool = True,
                outlier_strategy: str = "train_only",
                run_permutation: bool = False,
                feature_names: List[str] = None,
                random_state: int = 42) -> Dict:
    """Run LOSO cross-validation.

    Parameters
    ----------
    X_by_subject : dict mapping subject_id -> feature matrix (n_windows, n_features)
    y_by_subject : dict mapping subject_id -> label vector (n_windows,)
    model_builder : callable that returns a fitted sklearn-compatible classifier
    z_standardise : bool
    outlier_strategy : str
    run_permutation : bool
    feature_names : list of feature names for permutation importance
    random_state : int

    Returns
    -------
    dict with fold results and aggregate metrics
    """
    subjects = sorted(X_by_subject.keys())
    all_y_true = []
    all_y_pred = []
    all_y_proba = []
    fold_results = []

    pbar = tqdm(subjects, desc="LOSO folds")
    for test_subject in pbar:
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
        else:  # none
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

        # Impute any remaining NaNs
        from flow_lol.features.feature_union import impute_missing
        X_train = impute_missing(X_train, strategy="median")
        X_test = impute_missing(X_test, strategy="median")

        if len(np.unique(y_train)) < 2:
            # Skip fold if training set has only one class
            continue

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
        fold_metrics["test_subject"] = test_subject
        fold_metrics["n_train"] = int(len(y_train))
        fold_metrics["n_test"] = int(len(y_test))

        if run_permutation and feature_names is not None:
            fold_metrics["permutation_importance"] = compute_permutation_importance(
                X_test, y_test, model, feature_names, n_repeats=5
            )

        fold_results.append(fold_metrics)
        all_y_true.append(y_test)
        all_y_pred.append(y_pred)
        if y_proba is not None:
            all_y_proba.append(y_proba)

        pbar.set_postfix({
            "acc": f"{fold_metrics['accuracy']:.3f}",
            "f1": f"{fold_metrics['f1_macro']:.3f}",
            "n_train": fold_metrics["n_train"],
            "n_test": fold_metrics["n_test"],
        })

    pbar.close()

    if not all_y_true:
        return {"fold_results": [], "aggregate": {}}

    all_y_true = np.hstack(all_y_true)
    all_y_pred = np.hstack(all_y_pred)
    all_y_proba = np.vstack(all_y_proba) if all_y_proba else None

    aggregate = compute_metrics(all_y_true, all_y_pred, all_y_proba, classes=[0, 1])
    aggregate["mean_inference_ms"] = float(np.mean([f["inference_ms"] for f in fold_results]))

    return {
        "fold_results": fold_results,
        "aggregate": aggregate,
        "n_subjects": len(subjects),
    }
