r"""Export the best thesis classifiers for app runtime use (Phase 1.1).

Run this script from the research repository root, e.g.:

    cd C:\Users\user\Downloads\Masterthesis\Code
    python app\scripts\export_models.py

It trains five final (non-cross-validated) ECG-only models on the full available
data and saves them as joblib bundles under ``app/models/``:

1. ``biraffe2_svm.joblib`` – BIRAFFE2 pseudo-subject SVM (classical).
2. ``biraffe2_knn.joblib`` – BIRAFFE2 pseudo-subject kNN (classical).
3. ``biraffe2_rf.joblib`` – BIRAFFE2 pseudo-subject RandomForest (classical).
4. ``irshad_rf.joblib`` – Irshad/PhySF ECG-only RandomForest (classical).
5. ``biraffe2_mlp.joblib`` – BIRAFFE2 pseudo-subject MLP (deep learning).

Selection is based on subject-level AUC on ECG-only setups:

* BIRAFFE2 SVM  : AUC 0.790
* BIRAFFE2 kNN  : AUC 0.761
* BIRAFFE2 RF   : AUC 0.725
* Irshad RF     : AUC 0.692
* BIRAFFE2 MLP  : AUC 0.730 (best ECG-only deep-learning model across datasets)

Each bundle contains the fitted classifier, scaler, outlier handler, baseline
corrector (if any), feature names, and the config metadata needed by the app.
At runtime the app loads all five bundles and uses hard majority vote.
"""

from __future__ import annotations

import argparse
import logging
import sys
import warnings
from pathlib import Path
from typing import Any, Dict, List, Tuple

import joblib
import numpy as np
from sklearn.base import BaseEstimator

warnings.filterwarnings("ignore", category=RuntimeWarning)

logger = logging.getLogger(__name__)


def _setup_path() -> Path:
    """Ensure the research ``flow_lol`` package is imported, not the app package."""
    script_path = Path(__file__).resolve()
    # Research repo root = app/scripts/../../
    research_root = script_path.parent.parent.parent.resolve()
    app_pkg = research_root / "app" / "flow_lol"

    # Remove app package directories from sys.path so they are not picked first.
    sys.path = [p for p in sys.path if Path(p).resolve() not in {app_pkg, app_pkg.parent}]

    # Add research root at the front.
    if str(research_root) not in sys.path:
        sys.path.insert(0, str(research_root))
    return research_root


RESEARCH_ROOT = _setup_path()

# These imports resolve to the research package.
from flow_lol.data.loaders.biraffe2_loader import BIRAFFE2Loader
from flow_lol.data.loaders.irshad_loader import IrshadLoader
from flow_lol.data.labelers.flow_labeler import FlowLabeler
from flow_lol.features.extractors.ecg_features import extract_ecg_features
from flow_lol.features.feature_union import features_to_matrix, impute_missing
from flow_lol.models.classical import build_classifier
from flow_lol.models.deep import build_deep_classifier
from flow_lol.preprocessing.baseline_corrector import BaselineCorrector
from flow_lol.preprocessing.normaliser import ZStandardiser
from flow_lol.preprocessing.outlier_handler import OutlierHandler
from flow_lol.segmentation.window_segmenter import WindowSegmenter
from flow_lol.utils.config import load_config


# ---------------------------------------------------------------------------
# Feature extraction helpers
# ---------------------------------------------------------------------------

def _extract_windows(
    signal: np.ndarray,
    sampling_rate: float,
    segmenter: WindowSegmenter,
    features_cfg: Any,
) -> Tuple[List[Dict[str, float]], List[str]]:
    """Extract classical ECG features from all windows of one signal."""
    windows = segmenter.segment(signal)
    feats: List[Dict[str, float]] = []
    for w in windows:
        try:
            f = extract_ecg_features(
                w["signal"],
                sampling_rate=sampling_rate,
                package=features_cfg.package,
                selected_time=features_cfg.ecg.time,
                selected_frequency=features_cfg.ecg.frequency,
                selected_nonlinear=features_cfg.ecg.nonlinear,
            )
            feats.append(f)
        except Exception:
            continue
    if not feats:
        return [], []
    matrix, feature_names = features_to_matrix(feats)
    # Return as list of dicts to keep feature names aligned
    dicts = [dict(zip(feature_names, row)) for row in matrix]
    return dicts, feature_names


def _build_Xy(
    X_by_subject: Dict[int, np.ndarray],
    y_by_subject: Dict[int, np.ndarray],
    feature_names: List[str],
) -> Tuple[np.ndarray, np.ndarray, List[str]]:
    """Stack subject-level window matrices into global X, y."""
    subjects = sorted(X_by_subject.keys())
    X = np.vstack([X_by_subject[s] for s in subjects])
    y = np.hstack([y_by_subject[s] for s in subjects])
    return X, y, feature_names


def _fit_and_save(
    model: BaseEstimator,
    X: np.ndarray,
    y: np.ndarray,
    feature_names: List[str],
    outlier: OutlierHandler,
    scaler: ZStandardiser,
    baseline: BaselineCorrector,
    metadata: Dict[str, Any],
    output_path: Path,
) -> None:
    """Fit model on preprocessed data and save a joblib bundle."""
    # Drop all-NaN columns
    valid_cols = ~np.all(np.isnan(X), axis=0)
    if not np.all(valid_cols):
        dropped = [fn for fn, ok in zip(feature_names, valid_cols) if not ok]
        X = X[:, valid_cols]
        feature_names = [fn for fn, ok in zip(feature_names, valid_cols) if ok]
        metadata["dropped_all_nan_features"] = dropped

    if len(np.unique(y)) < 2:
        raise ValueError("Only one class present after preprocessing; cannot fit model.")

    logger.info("Fitting %s on %d windows, %d features", metadata["model_name"], X.shape[0], X.shape[1])
    model.fit(X, y)

    # Move PyTorch models to CPU before saving so bundles are portable.
    if hasattr(model, "to"):
        try:
            model.to("cpu")
        except Exception:
            pass
    if hasattr(model, "device"):
        model.device = "cpu"

    bundle = {
        "model": model,
        "scaler": _scaler_to_dict(scaler),
        "outlier_handler": _outlier_to_dict(outlier),
        "baseline_corrector": _baseline_to_dict(baseline),
        "feature_names": feature_names,
        "metadata": metadata,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, output_path)
    logger.info("Saved model bundle to %s", output_path.resolve())


def _safe_clean_ecg(
    signal: np.ndarray, sampling_rate: float, package: str, context: str
) -> Optional[np.ndarray]:
    """Clean ECG if signal is long enough; otherwise return None."""

    # neurokit2's Butterworth filter needs at least ~18 samples of padding.
    min_samples = max(100, int(2 * sampling_rate))
    if signal.size < min_samples:
        logger.warning(
            "[%s] signal too short for cleaning (%d < %d samples); skipping",
            context,
            signal.size,
            min_samples,
        )
        return None
    try:
        from flow_lol.preprocessing.cleaners.ecg_cleaner import clean_ecg

        return clean_ecg(signal, sampling_rate=sampling_rate, package=package)
    except Exception as exc:
        logger.warning("[%s] ECG cleaning failed: %s", context, exc)
        return None


def _scaler_to_dict(scaler: ZStandardiser) -> Dict[str, Any]:
    """Convert a fitted ZStandardiser to a JSON-serializable dict."""
    return {
        "type": "ZStandardiser",
        "active": getattr(scaler, "active", True),
        "mean_": scaler.mean_.tolist() if scaler.mean_ is not None else None,
        "std_": scaler.std_.tolist() if scaler.std_ is not None else None,
    }


def _outlier_to_dict(outlier: OutlierHandler) -> Dict[str, Any]:
    """Convert a fitted OutlierHandler to a JSON-serializable dict."""
    return {
        "type": "OutlierHandler",
        "strategy": getattr(outlier, "strategy", "none"),
        "factor": getattr(outlier, "factor", 1.5),
        "lower_": outlier.lower_.tolist() if outlier.lower_ is not None else None,
        "upper_": outlier.upper_.tolist() if outlier.upper_ is not None else None,
    }


def _baseline_to_dict(baseline: BaselineCorrector) -> Dict[str, Any]:
    """Convert a fitted BaselineCorrector to a JSON-serializable dict."""
    return {
        "type": "BaselineCorrector",
        "method": getattr(baseline, "method", "none"),
        "baseline_": baseline.baseline_.tolist() if baseline.baseline_ is not None else None,
    }


# ---------------------------------------------------------------------------
# BIRAFFE2 feature matrix builder
# ---------------------------------------------------------------------------

def _build_biraffe2_Xy(
    config_path: Path,
) -> Tuple[Dict[int, np.ndarray], Dict[int, np.ndarray], List[str], Dict[str, Any]]:
    """Load BIRAFFE2 pseudo-subjects and build window-level X, y matrices."""
    config = load_config(str(config_path))
    loader = BIRAFFE2Loader(config.dataset)
    subjects = loader.list_subjects()

    scores = np.array([loader.load_subject(sid)["label"] for sid in subjects])
    labeler = FlowLabeler(config.label)
    labels, mask = labeler.fit_transform(scores)

    segmenter = WindowSegmenter(
        window_length_s=config.segmentation.window_length_s,
        step_s=config.segmentation.step_s,
        sampling_rate=loader.sample_rate,
    )

    X_by_subject: Dict[int, np.ndarray] = {}
    y_by_subject: Dict[int, np.ndarray] = {}
    feature_names: List[str] = []

    active_subjects = [sid for sid, m in zip(subjects, mask) if m]
    for sid in active_subjects:
        record = loader.load_subject(sid)
        ecg_raw = record["signal"]["ECG"].to_numpy(dtype=float)
        ecg_clean = _safe_clean_ecg(
            ecg_raw, sampling_rate=loader.sample_rate, package=config.preprocessing.cleaning_package, context=f"subject {sid}"
        )
        if ecg_clean is None:
            logger.warning("[skip subject %s] ECG could not be cleaned", sid)
            continue

        feats, fnames = _extract_windows(
            ecg_clean, loader.sample_rate, segmenter, config.features
        )
        if not feats:
            logger.warning("[skip subject %s] no features extracted", sid)
            continue

        X = np.array([[f.get(name, np.nan) for name in fnames] for f in feats])

        baseline = BaselineCorrector(method=config.preprocessing.baseline_correction)
        if config.preprocessing.baseline_correction != "none":
            baseline_signal = loader.load_baseline_signal(
                sid, max_length_s=config.preprocessing.baseline_length_s
            )
            if baseline_signal is not None and not baseline_signal.empty:
                baseline_ecg = baseline_signal["ECG"].to_numpy(dtype=float)
                baseline_clean = _safe_clean_ecg(
                    baseline_ecg,
                    sampling_rate=loader.sample_rate,
                    package=config.preprocessing.cleaning_package,
                    context=f"subject {sid} baseline",
                )
                if baseline_clean is None:
                    logger.warning(
                        "[subject %s] baseline ECG could not be cleaned; skipping baseline correction",
                        sid,
                    )
                    baseline = BaselineCorrector(method="none")
                else:
                    baseline_feats, _ = _extract_windows(
                        baseline_clean, loader.sample_rate, segmenter, config.features
                    )
                    if baseline_feats:
                        baseline_matrix = np.array(
                            [[f.get(name, np.nan) for name in fnames] for f in baseline_feats]
                        )
                        baseline_matrix = impute_missing(baseline_matrix, strategy="median")
                        X = baseline.fit_transform(baseline_matrix, X)
                    else:
                        logger.warning(
                            "[subject %s] could not extract baseline features; skipping baseline correction",
                            sid,
                        )
                        baseline = BaselineCorrector(method="none")
            else:
                logger.warning(
                    "[subject %s] no baseline signal available; skipping baseline correction", sid
                )
                baseline = BaselineCorrector(method="none")

        X = impute_missing(X, strategy="median")

        X_by_subject[sid] = X
        y_by_subject[sid] = np.full(len(X), fill_value=labels[subjects.index(sid)], dtype=int)
        if not feature_names:
            feature_names = fnames

    if not X_by_subject:
        raise RuntimeError("No BIRAFFE2 subjects produced usable features.")

    metadata = {
        "source": "BIRAFFE2",
        "experiment_name": config.experiment_name,
        "config_path": str(config_path),
        "n_subjects": len(X_by_subject),
        "window_length_s": config.segmentation.window_length_s,
        "step_s": config.segmentation.step_s,
        "sampling_rate_hz": loader.sample_rate,
        "feature_names": feature_names,
        "labeler_description": labeler.describe(),
        "class_labels": {0: "low", 1: "high"},
        "baseline_correction": config.preprocessing.baseline_correction,
        "outlier_strategy": config.preprocessing.outlier_strategy,
        "z_standardise": config.preprocessing.z_standardise,
    }
    return X_by_subject, y_by_subject, feature_names, metadata


def _preprocess_for_training(
    X_by_subject: Dict[int, np.ndarray],
    y_by_subject: Dict[int, np.ndarray],
    feature_names: List[str],
    outlier_strategy: str,
    z_standardise: bool,
) -> Tuple[np.ndarray, np.ndarray, OutlierHandler, ZStandardiser, List[str]]:
    """Stack, outlier-filter, scale, and drop all-NaN columns."""
    X, y, feature_names = _build_Xy(X_by_subject, y_by_subject, feature_names)
    outlier = OutlierHandler(strategy=outlier_strategy)
    mask_out = outlier.fit_transform(X)
    X = X[mask_out]
    y = y[mask_out]

    scaler = ZStandardiser(active=z_standardise)
    X = scaler.fit_transform(X)

    valid_cols = ~np.all(np.isnan(X), axis=0)
    if not np.all(valid_cols):
        X = X[:, valid_cols]
        feature_names = [fn for fn, ok in zip(feature_names, valid_cols) if ok]

    return X, y, outlier, scaler, feature_names


# ---------------------------------------------------------------------------
# BIRAFFE2 model exporters
# ---------------------------------------------------------------------------

def export_biraffe2_classical(
    config_path: Path,
    output_path: Path,
    model_name: str,
    Xy_cache: Tuple[Dict[int, np.ndarray], Dict[int, np.ndarray], List[str], Dict[str, Any]] | None = None,
) -> None:
    """Train and export a classical BIRAFFE2 model (SVM / kNN / RF)."""
    if Xy_cache is None:
        X_by_subject, y_by_subject, feature_names, meta = _build_biraffe2_Xy(config_path)
    else:
        X_by_subject, y_by_subject, feature_names, meta = Xy_cache

    X, y, outlier, scaler, feature_names = _preprocess_for_training(
        X_by_subject, y_by_subject, feature_names, meta["outlier_strategy"], meta["z_standardise"]
    )

    config = load_config(str(config_path))
    model = build_classifier(model_name, random_state=config.seed)
    meta = dict(meta)
    meta["model_name"] = f"BIRAFFE2 {model_name}"
    meta["family"] = "classical"

    # No runtime baseline correction for classical models; it was applied per window above.
    baseline = BaselineCorrector(method="none")
    _fit_and_save(model, X, y, feature_names, outlier, scaler, baseline, meta, output_path)


def export_biraffe2_mlp(
    config_path: Path,
    output_path: Path,
    Xy_cache: Tuple[Dict[int, np.ndarray], Dict[int, np.ndarray], List[str], Dict[str, Any]] | None = None,
) -> None:
    """Train and export the BIRAFFE2 MLP deep-learning model."""
    if Xy_cache is None:
        X_by_subject, y_by_subject, feature_names, meta = _build_biraffe2_Xy(config_path)
    else:
        X_by_subject, y_by_subject, feature_names, meta = Xy_cache

    X, y, outlier, scaler, feature_names = _preprocess_for_training(
        X_by_subject, y_by_subject, feature_names, meta["outlier_strategy"], meta["z_standardise"]
    )

    config = load_config(str(config_path))
    model = build_deep_classifier(
        "MLP", n_features=X.shape[1], n_classes=2, random_state=config.seed
    )
    meta = dict(meta)
    meta["model_name"] = "BIRAFFE2 MLP"
    meta["family"] = "deep"
    baseline = BaselineCorrector(method="none")
    _fit_and_save(model, X, y, feature_names, outlier, scaler, baseline, meta, output_path)


# ---------------------------------------------------------------------------
# Irshad exporter
# ---------------------------------------------------------------------------

def export_irshad_rf(
    config_path: Path,
    output_path: Path,
) -> None:
    """Train and export the Irshad/PhySF ECG-only RandomForest."""
    config = load_config(str(config_path))
    logger.info("Irshad config: %s", config.experiment_name)

    loader = IrshadLoader(config.dataset.path, modalities=config.dataset.modalities)
    subjects = loader.list_subjects()
    logger.info("Found %d subjects", len(subjects))

    segmenter = WindowSegmenter(
        window_length_s=config.segmentation.window_length_s,
        step_s=config.segmentation.step_s,
        sampling_rate=loader.sample_rate,
    )

    X_by_subject: Dict[int, np.ndarray] = {}
    y_by_subject: Dict[int, np.ndarray] = {}
    feature_names: List[str] = []

    for sid in subjects:
        label = loader.get_label(sid)
        record = loader.load_subject(sid)
        ecg_raw = record["signal"]["ECG"].to_numpy(dtype=float)

        ecg_clean = _safe_clean_ecg(
            ecg_raw,
            sampling_rate=loader.sample_rate,
            package=config.preprocessing.cleaning_package,
            context=f"irshad subject {sid}",
        )
        if ecg_clean is None:
            logger.warning("[skip subject %s] ECG could not be cleaned", sid)
            continue

        feats, fnames = _extract_windows(
            ecg_clean, loader.sample_rate, segmenter, config.features
        )
        if not feats:
            logger.warning("[skip subject %s] no features extracted", sid)
            continue

        X = np.array([[f.get(name, np.nan) for name in fnames] for f in feats])
        X = impute_missing(X, strategy="median")

        X_by_subject[sid] = X
        y_by_subject[sid] = np.full(len(X), fill_value=label, dtype=int)
        if not feature_names:
            feature_names = fnames

    if not X_by_subject:
        raise RuntimeError("No Irshad subjects produced usable features.")

    X, y, outlier, scaler, feature_names = _preprocess_for_training(
        X_by_subject,
        y_by_subject,
        feature_names,
        config.preprocessing.outlier_strategy,
        config.preprocessing.z_standardise,
    )

    model = build_classifier("RandomForest", random_state=config.seed)
    baseline = BaselineCorrector(method="none")

    metadata = {
        "source": "Irshad_PhySF",
        "model_name": "Irshad RandomForest",
        "family": "classical",
        "experiment_name": config.experiment_name,
        "config_path": str(config_path),
        "n_subjects": len(X_by_subject),
        "window_length_s": config.segmentation.window_length_s,
        "step_s": config.segmentation.step_s,
        "sampling_rate_hz": loader.sample_rate,
        "feature_names": feature_names,
        "class_labels": {0: "no_flow", 1: "flow"},
        "outlier_strategy": config.preprocessing.outlier_strategy,
        "z_standardise": config.preprocessing.z_standardise,
        "baseline_correction": "none",
    }

    _fit_and_save(model, X, y, feature_names, outlier, scaler, baseline, metadata, output_path)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Export thesis classifiers for the Flow-LoL app.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=RESEARCH_ROOT / "app" / "models",
        help="Directory where model bundles are written",
    )
    parser.add_argument(
        "--biraffe2-config",
        type=Path,
        default=RESEARCH_ROOT
        / "config"
        / "biraffe2"
        / "extreme_percentile_configs"
        / "setup_12_biraffe2_baseline_correction_extreme_percentile_classical.yaml",
        help="BIRAFFE2 YAML config for classical models and MLP",
    )
    parser.add_argument(
        "--irshad-config",
        type=Path,
        default=RESEARCH_ROOT / "config" / "irshad" / "setup_08b_irshad_physf_ecg_only.yaml",
        help="Irshad YAML config for the RandomForest",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(message)s",
    )

    logger.info("Research root: %s", RESEARCH_ROOT)
    logger.info("Output directory: %s", args.output_dir.resolve())

    # Build BIRAFFE2 features once and reuse for all BIRAFFE2 models.
    logger.info("Building BIRAFFE2 feature cache...")
    biraffe2_cache = _build_biraffe2_Xy(args.biraffe2_config)

    out = args.output_dir
    export_biraffe2_classical(args.biraffe2_config, out / "biraffe2_svm.joblib", "SVM", biraffe2_cache)
    export_biraffe2_classical(args.biraffe2_config, out / "biraffe2_knn.joblib", "kNN", biraffe2_cache)
    export_biraffe2_classical(args.biraffe2_config, out / "biraffe2_rf.joblib", "RandomForest", biraffe2_cache)
    export_biraffe2_mlp(args.biraffe2_config, out / "biraffe2_mlp.joblib", biraffe2_cache)
    export_irshad_rf(args.irshad_config, out / "irshad_rf.joblib")

    logger.info("Phase 1.1 complete: five ECG-only models exported to %s", out.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
