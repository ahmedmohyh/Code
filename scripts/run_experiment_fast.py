"""Fast parallel experiment runner for Flow-LoL.

This runner uses all CPU cores for feature extraction and LOSO folds.
It also caches extracted biosignal CSVs to avoid repeated zip reads.
"""
import argparse
import sys
import warnings
from pathlib import Path
from joblib import Parallel, delayed, cpu_count

import numpy as np
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).parent.parent))

from dataclasses import asdict

from flow_lol.utils.config import Config, load_config
from flow_lol.data.loaders.biraffe2_loader import BIRAFFE2Loader
from flow_lol.data.labelers.flow_labeler import FlowLabeler
from flow_lol.preprocessing.cleaners.ecg_cleaner import clean_ecg
from flow_lol.preprocessing.baseline_corrector import BaselineCorrector
from flow_lol.preprocessing.per_subject_normaliser import PerSubjectNormaliser
from flow_lol.segmentation.window_segmenter import WindowSegmenter
from flow_lol.features.extractors.ecg_features import extract_ecg_features
from flow_lol.features.feature_union import features_to_matrix, impute_missing
from flow_lol.models.classical import build_classifier, list_available_classifiers
from flow_lol.models.deep import build_deep_classifier
from flow_lol.validation.loso_cv import run_loso_cv
from flow_lol.reporting.ablation_table import save_results

warnings.filterwarnings("ignore", category=RuntimeWarning)
warnings.filterwarnings("ignore", category=FutureWarning)
# NeuroKit2 emits many DFA_alpha2 warnings for short windows; suppress them
# so the progress bar stays visible.
warnings.filterwarnings("ignore", message=".*DFA_alpha2.*")


def _extract_signal_features(signal_df, loader, segmenter, config):
    """Clean, segment and extract ECG features from one signal DataFrame."""
    if "ECG" not in signal_df.columns or signal_df.empty:
        return None
    ecg_raw = signal_df["ECG"].to_numpy(dtype=float)
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
        return None
    X, _ = features_to_matrix(feats)
    X = impute_missing(X, strategy="median")
    return X


def _process_one_subject(args_tuple):
    """Process one subject: clean, segment, extract features, optionally baseline-correct."""
    sid, loader, segmenter, config, label = args_tuple
    try:
        record = loader.load_subject(sid)
        X = _extract_signal_features(record["signal"], loader, segmenter, config)
        if X is None:
            return sid, None, None, label, 0

        baseline_correction = getattr(config.preprocessing, "baseline_correction", "none")
        if baseline_correction in ("change_score", "quotient"):
            baseline_signal = loader.load_baseline_signal(
                sid,
                max_length_s=float(config.preprocessing.baseline_length_s),
            )
            baseline_X = _extract_signal_features(baseline_signal, loader, segmenter, config)
            if baseline_X is not None and baseline_X.shape[0] > 0:
                corrector = BaselineCorrector(method=baseline_correction)
                X = corrector.fit_transform(baseline_X, X)
            else:
                print(f"  [warn {sid}] no baseline features; leaving game features uncorrected")

        y = np.full(len(X), fill_value=label, dtype=int)
        return sid, X, y, label, len(X)
    except Exception as e:
        return sid, None, None, label, f"ERROR: {e}"


def _load_label_from_metadata(loader: BIRAFFE2Loader, sid: int) -> float:
    """Read a subject's label via the loader (handles real and pseudo IDs)."""
    return loader.get_label(sid)


def _cache_subject(loader: BIRAFFE2Loader, sid: int) -> int:
    """Ensure one subject's biosignals are extracted from zip to cache."""
    loader.load_subject(sid)
    return sid


def load_biraffe2_data_fast(config: Config, n_jobs: int = -1, cache_dir: str = "cache/biosigs"):
    """Load and process BIRAFFE2 data in parallel."""
    loader = BIRAFFE2Loader(config.dataset, cache_dir=cache_dir)
    subjects = loader.list_subjects()
    print(f"Found {len(subjects)} valid subjects.")

    # Fast label lookup from metadata (no signal loading)
    scores = np.array([_load_label_from_metadata(loader, sid) for sid in subjects])
    labeler = FlowLabeler(config.label)
    labels, mask = labeler.fit_transform(scores)

    print(f"Label distribution: low={np.sum(labels == 0)}, high={np.sum(labels == 1)}, excluded={np.sum(~mask)}")
    print(f"Median={labeler.median_:.3f}, IQR={labeler.iqr_:.3f}")

    active_subjects = [sid for i, sid in enumerate(subjects) if mask[i]]

    # Pre-extract all needed biosignals from the zip once, with a progress bar.
    # After this step the parallel workers read plain CSVs, not the shared zip.
    print(f"Pre-extracting/caching {len(active_subjects)} biosignal files...")
    for sid in tqdm(
        active_subjects,
        desc="Caching",
        file=sys.stdout,
        position=0,
        leave=True,
        ascii=True,
        ncols=80,
        mininterval=1,
    ):
        _cache_subject(loader, sid)

    segmenter = WindowSegmenter(
        window_length_s=config.segmentation.window_length_s,
        step_s=config.segmentation.step_s,
        sampling_rate=loader.sample_rate,
    )

    active = [(sid, loader, segmenter, config, labels[i]) for i, sid in enumerate(subjects) if mask[i]]
    n_jobs = cpu_count() if n_jobs == -1 else n_jobs
    print(f"Processing {len(active)} subjects in parallel with {n_jobs} workers...")

    results = Parallel(n_jobs=n_jobs, backend="loky", verbose=0)(
        delayed(_process_one_subject)(item)
        for item in tqdm(
            active,
            desc="Subjects",
            total=len(active),
            file=sys.stdout,
            position=0,
            leave=True,
            ascii=True,
            ncols=80,
            mininterval=2,
        )
    )

    X_by_subject = {}
    y_by_subject = {}
    skipped = 0
    for sid, X, y, label, info in results:
        if X is None:
            skipped += 1
            print(f"  [skip {sid}] {info}")
            continue
        X_by_subject[sid] = X
        y_by_subject[sid] = y

    # Recover feature names from config
    feature_names = list(config.features.ecg.time + config.features.ecg.frequency + config.features.ecg.nonlinear)

    print(f"Subjects used: {len(X_by_subject)}, skipped: {skipped}")

    if X_by_subject:
        total_windows = sum(X.shape[0] for X in X_by_subject.values())
        first_sid = next(iter(X_by_subject))
        X_first = X_by_subject[first_sid]
        nan_frac = np.mean(np.isnan(X_first))
        print(f"Total windows across subjects: {total_windows}")
        print(f"First subject {first_sid}: shape={X_first.shape}, NaN fraction={nan_frac:.3%}")
        empty_cols = np.sum(np.all(np.isnan(X_first), axis=0))
        print(f"First subject all-NaN columns: {empty_cols}/{X_first.shape[1]}")

    return X_by_subject, y_by_subject, feature_names, labeler


def run(config: Config, n_jobs: int = -1):
    print(f"Experiment: {config.experiment_name}")
    print(f"Dataset: {config.dataset.name}, Modalities: {config.dataset.modalities}")

    if not config.dataset.name.startswith("BIRAFFE2"):
        raise NotImplementedError(f"Dataset {config.dataset.name} not implemented yet.")

    X_by_subject, y_by_subject, feature_names, labeler = load_biraffe2_data_fast(config, n_jobs=n_jobs)

    if not X_by_subject:
        raise RuntimeError("No subjects produced features.")

    # Per-subject normalization (optional, before LOSO)
    if getattr(config.preprocessing, "per_subject_normalize", False):
        print("Applying per-subject normalization...")
        normaliser = PerSubjectNormaliser(active=True)
        X_by_subject = normaliser.transform_dict(X_by_subject)
        print("Per-subject normalization done.")

    # Determine number of features from first subject
    first_sid = next(iter(X_by_subject))
    n_features = X_by_subject[first_sid].shape[1]

    results_all = {}

    # Classical models
    for model_name in config.models.classical:
        print(f"\nRunning LOSO CV for {model_name}")

        def builder(name=model_name):
            return build_classifier(name, random_state=config.seed)

        cv_results = run_loso_cv(
            X_by_subject, y_by_subject,
            model_builder=builder,
            z_standardise=config.preprocessing.z_standardise,
            outlier_strategy=config.preprocessing.outlier_strategy,
            run_permutation=config.validation.permutation,
            feature_names=feature_names,
            random_state=config.seed,
            n_jobs=5,
        )
        results_all[model_name] = cv_results
        agg = cv_results["aggregate"]
        sub_agg = cv_results.get("subject_aggregate", {})
        print(f"  Window-level: Accuracy={agg.get('accuracy', np.nan):.3f} "
              f"F1={agg.get('f1_macro', np.nan):.3f} "
              f"AUC={agg.get('auc', np.nan):.3f}")
        print(f"  Subject-level: Accuracy={sub_agg.get('accuracy', np.nan):.3f} "
              f"F1={sub_agg.get('f1_macro', np.nan):.3f} "
              f"AUC={sub_agg.get('auc', np.nan):.3f} "
              f"n={sub_agg.get('n_subjects_used', 0)}")

    # Deep-learning models
    for model_name in config.models.deep:
        print(f"\nRunning LOSO CV for deep model {model_name}")

        def deep_builder(name=model_name, n=n_features):
            return build_deep_classifier(name, n_features=n, random_state=config.seed)

        cv_results = run_loso_cv(
            X_by_subject, y_by_subject,
            model_builder=deep_builder,
            z_standardise=config.preprocessing.z_standardise,
            outlier_strategy=config.preprocessing.outlier_strategy,
            run_permutation=config.validation.permutation,
            feature_names=feature_names,
            random_state=config.seed,
            n_jobs=1,  # PyTorch models train on GPU/CPU; avoid fold-level parallelism
        )
        results_all[model_name] = cv_results
        agg = cv_results["aggregate"]
        sub_agg = cv_results.get("subject_aggregate", {})
        print(f"  Window-level: Accuracy={agg.get('accuracy', np.nan):.3f} "
              f"F1={agg.get('f1_macro', np.nan):.3f} "
              f"AUC={agg.get('auc', np.nan):.3f}")
        print(f"  Subject-level: Accuracy={sub_agg.get('accuracy', np.nan):.3f} "
              f"F1={sub_agg.get('f1_macro', np.nan):.3f} "
              f"AUC={sub_agg.get('auc', np.nan):.3f} "
              f"n={sub_agg.get('n_subjects_used', 0)}")

    output_dir = Path("results") / config.experiment_name
    final_results = {
        "experiment_name": config.experiment_name,
        "labeler_description": labeler.describe(),
        "feature_names": feature_names,
        "models": results_all,
    }
    save_results(final_results, asdict(config), str(output_dir))
    print(f"\nResults saved to: {output_dir}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--n-jobs", type=int, default=-1, help="Number of parallel workers for feature extraction (-1 = all cores)")
    args = parser.parse_args()
    config = load_config(args.config)
    run(config, n_jobs=args.n_jobs)


if __name__ == "__main__":
    main()
