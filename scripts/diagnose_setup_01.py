"""Diagnostic script for Setup 01.

This script inspects the ECG-only BIRAFFE2 baseline in detail:
1. Feature quality (mean, std, range, NaN rate, correlation with label).
2. Label distribution and score statistics.
3. Window counts per subject.
4. Classifier comparison (RandomForest, SVM, XGBoost, kNN, LogisticRegression).
5. Window-level vs. subject-level training.
6. Probability calibration histogram.

Run with:
    python scripts/diagnose_setup_01.py --config config/setup_01_biraffe2_ecg_baseline.yaml --n-jobs -1
"""
import argparse
import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from joblib import Parallel, delayed, cpu_count
from scipy.stats import pointbiserialr
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, roc_auc_score
from sklearn.neighbors import KNeighborsClassifier
from sklearn.svm import SVC
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).parent.parent))

from flow_lol.data.labelers.flow_labeler import FlowLabeler
from flow_lol.data.loaders.biraffe2_loader import BIRAFFE2Loader
from flow_lol.features.extractors.ecg_features import extract_ecg_features
from flow_lol.features.feature_union import features_to_matrix, impute_missing
from flow_lol.models.classical import build_classifier
from flow_lol.preprocessing.cleaners.ecg_cleaner import clean_ecg
from flow_lol.segmentation.window_segmenter import WindowSegmenter
from flow_lol.utils.config import Config, load_config
from flow_lol.validation.loso_cv import run_loso_cv

warnings.filterwarnings("ignore")


def _extract_subject_windows(args):
    """Extract features for one subject."""
    sid, loader, segmenter, config, label = args
    try:
        record = loader.load_subject(sid)
        ecg_raw = record["signal"]["ECG"].to_numpy(dtype=float)
        ecg_clean = clean_ecg(
            ecg_raw,
            sampling_rate=loader.sample_rate,
            package=config.preprocessing.cleaning_package,
        )
        windows = segmenter.segment(ecg_clean)
        feats = []
        for w in windows:
            try:
                f = extract_ecg_features(
                    w["signal"],
                    sampling_rate=loader.sample_rate,
                    package=config.features.package,
                    selected_time=config.features.ecg.time,
                    selected_frequency=config.features.ecg.frequency,
                    selected_nonlinear=config.features.ecg.nonlinear,
                )
                feats.append(f)
            except Exception:
                continue
        if not feats:
            return sid, None, None, label
        X, feature_names = features_to_matrix(feats)
        X = impute_missing(X, strategy="median")
        y = np.full(len(X), fill_value=label, dtype=int)
        return sid, X, y, label
    except Exception as e:
        return sid, None, None, f"ERROR: {e}"


def load_data(config: Config, n_jobs: int = -1, max_subjects: int = None):
    loader = BIRAFFE2Loader(config.dataset, cache_dir="cache/biosigs")
    subjects = loader.list_subjects()
    if max_subjects:
        subjects = subjects[:max_subjects]

    scores = np.array([loader.load_subject(sid)["label"] for sid in subjects])
    labeler = FlowLabeler(config.label)
    labels, mask = labeler.fit_transform(scores)

    segmenter = WindowSegmenter(
        window_length_s=config.segmentation.window_length_s,
        step_s=config.segmentation.step_s,
        sampling_rate=loader.sample_rate,
    )

    active = [(sid, loader, segmenter, config, labels[i]) for i, sid in enumerate(subjects) if mask[i]]
    n_jobs = cpu_count() if n_jobs == -1 else n_jobs

    results = Parallel(n_jobs=n_jobs, backend="loky", verbose=0)(
        delayed(_extract_subject_windows)(item) for item in tqdm(active, desc="Subjects")
    )

    X_by_subject = {}
    y_by_subject = {}
    skipped = []
    feature_names = None
    for sid, X, y, info in results:
        if X is None:
            skipped.append((sid, info))
            continue
        X_by_subject[sid] = X
        y_by_subject[sid] = y
        if feature_names is None:
            feature_names = list(config.features.ecg.time + config.features.ecg.frequency + config.features.ecg.nonlinear)

    return X_by_subject, y_by_subject, feature_names, labeler, skipped


def feature_quality_report(X_by_subject, y_by_subject, feature_names):
    """Compute per-feature statistics and correlation with label."""
    X = np.vstack([X_by_subject[s] for s in sorted(X_by_subject)])
    y = np.hstack([y_by_subject[s] for s in sorted(X_by_subject)])

    rows = []
    for i, name in enumerate(feature_names):
        col = X[:, i]
        finite = np.isfinite(col)
        n_finite = int(np.sum(finite))
        if n_finite < 2 or np.std(col[finite]) == 0:
            rows.append({
                "feature": name,
                "n_finite": n_finite,
                "n_total": len(col),
                "mean": np.nan,
                "std": 0.0,
                "min": np.nan,
                "max": np.nan,
                "corr_with_label": np.nan,
                "p_value": np.nan,
            })
            continue
        corr, pval = pointbiserialr(y[finite], col[finite])
        rows.append({
            "feature": name,
            "n_finite": n_finite,
            "n_total": len(col),
            "mean": float(np.mean(col[finite])),
            "std": float(np.std(col[finite])),
            "min": float(np.min(col[finite])),
            "max": float(np.max(col[finite])),
            "corr_with_label": float(corr),
            "p_value": float(pval),
        })
    return pd.DataFrame(rows)


def classifier_comparison(X_by_subject, y_by_subject, config):
    """Run LOSO with multiple classifiers and report subject-level AUC."""
    models = ["RandomForest", "SVM", "kNN", "LogisticRegression"]
    try:
        import xgboost  # noqa: F401
        models.append("XGBoost")
    except ImportError:
        pass

    rows = []
    for name in models:
        def builder(name=name):
            if name == "LogisticRegression":
                return LogisticRegression(max_iter=1000, class_weight="balanced", random_state=config.seed)
            return build_classifier(name, random_state=config.seed)

        cv = run_loso_cv(
            X_by_subject, y_by_subject,
            model_builder=builder,
            z_standardise=config.preprocessing.z_standardise,
            outlier_strategy=config.preprocessing.outlier_strategy,
            n_jobs=5,
        )
        sub = cv.get("subject_aggregate", {})
        win = cv.get("aggregate", {})
        rows.append({
            "model": name,
            "window_accuracy": win.get("accuracy", np.nan),
            "window_f1": win.get("f1_macro", np.nan),
            "window_auc": win.get("auc", np.nan),
            "subject_accuracy": sub.get("accuracy", np.nan),
            "subject_f1": sub.get("f1_macro", np.nan),
            "subject_auc": sub.get("auc", np.nan),
            "n_subjects_used": sub.get("n_subjects_used", 0),
        })
    return pd.DataFrame(rows)


def subject_level_baseline(X_by_subject, y_by_subject, config):
    """Train on one aggregated feature vector per subject (mean of windows)."""
    subjects = sorted(X_by_subject.keys())
    X_subject = np.vstack([X_by_subject[s].mean(axis=0) for s in subjects])
    y_subject = np.array([int(np.bincount(y_by_subject[s].astype(int)).argmax()) for s in subjects])

    from sklearn.model_selection import LeaveOneOut
    preds = []
    scores = []
    trues = []
    for train_idx, test_idx in LeaveOneOut().split(X_subject):
        X_train, X_test = X_subject[train_idx], X_subject[test_idx]
        y_train, y_test = y_subject[train_idx], y_subject[test_idx]

        # z-standardise
        mean = np.nanmean(X_train, axis=0)
        std = np.nanstd(X_train, axis=0)
        std = np.where(std == 0, 1.0, std)
        X_train = (X_train - mean) / std
        X_test = (X_test - mean) / std
        X_train = impute_missing(X_train, strategy="median")
        X_test = impute_missing(X_test, strategy="median")

        model = build_classifier("RandomForest", random_state=config.seed)
        model.fit(X_train, y_train)
        preds.append(int(model.predict(X_test)[0]))
        if hasattr(model, "predict_proba"):
            scores.append(float(model.predict_proba(X_test)[0, 1]))
        else:
            scores.append(float(preds[-1]))
        trues.append(int(y_test[0]))

    preds = np.array(preds)
    trues = np.array(trues)
    scores = np.array(scores)
    return {
        "accuracy": float(accuracy_score(trues, preds)),
        "f1_macro": float(f1_score(trues, preds, average="macro", zero_division=0)),
        "auc": float(roc_auc_score(trues, scores)) if len(np.unique(trues)) == 2 else np.nan,
        "n_subjects": len(trues),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--n-jobs", type=int, default=-1)
    parser.add_argument("--max-subjects", type=int, default=None)
    args = parser.parse_args()

    config = load_config(args.config)
    out_dir = Path("results") / f"diagnose_{config.experiment_name}"
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Diagnostic run for {config.experiment_name}")
    X_by_subject, y_by_subject, feature_names, labeler, skipped = load_data(
        config, n_jobs=args.n_jobs, max_subjects=args.max_subjects
    )

    report = {
        "experiment_name": config.experiment_name,
        "labeler_description": labeler.describe(),
        "n_subjects": len(X_by_subject),
        "skipped_subjects": skipped,
        "total_windows": int(sum(X.shape[0] for X in X_by_subject.values())),
    }

    print(f"\nSubjects used: {report['n_subjects']}, skipped: {len(skipped)}, windows: {report['total_windows']}")

    # 1. Feature quality
    print("\n=== Feature quality ===")
    feat_df = feature_quality_report(X_by_subject, y_by_subject, feature_names)
    print(feat_df.to_string(index=False))
    feat_df.to_csv(out_dir / "feature_quality.csv", index=False)

    # 2. Classifier comparison
    print("\n=== Classifier comparison (subject-level metrics) ===")
    clf_df = classifier_comparison(X_by_subject, y_by_subject, config)
    print(clf_df.to_string(index=False))
    clf_df.to_csv(out_dir / "classifier_comparison.csv", index=False)

    # 3. Subject-level baseline (one row per subject)
    print("\n=== Subject-level baseline (mean features per subject) ===")
    sub_baseline = subject_level_baseline(X_by_subject, y_by_subject, config)
    print(json.dumps(sub_baseline, indent=2))

    report["classifier_comparison"] = clf_df.to_dict(orient="records")
    report["subject_level_baseline"] = sub_baseline

    with open(out_dir / "diagnostic_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"\nDiagnostic report saved to: {out_dir}")


if __name__ == "__main__":
    main()
