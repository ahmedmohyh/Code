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
from flow_lol.data.loaders.irshad_loader import IrshadLoader
from flow_lol.data.labelers.flow_labeler import FlowLabeler
from flow_lol.preprocessing.cleaners.ecg_cleaner import clean_ecg
from flow_lol.preprocessing.cleaners.eda_cleaner import clean_eda
from flow_lol.preprocessing.baseline_corrector import BaselineCorrector
from flow_lol.preprocessing.per_subject_normaliser import PerSubjectNormaliser
from flow_lol.segmentation.window_segmenter import WindowSegmenter
from flow_lol.features.extractors.ecg_features import extract_ecg_features
from flow_lol.features.extractors.eda_features import extract_eda_features
from flow_lol.features.extractors.eeg_features import extract_eeg_features
from flow_lol.features.extractors.webcam_features import extract_webcam_features
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


def _extract_signal_features(signal_df, loader, segmenter, config, face_df=None, _diag_prefix=""):
    """Clean, segment and extract ECG, EDA and webcam features from one signal DataFrame.

    The function is fully backward-compatible: if only ECG is requested, it
    returns the same matrix as before. EDA and FACE features are only added
    when those modalities are present in the config.

    Returns
    -------
    (X, feature_names, diagnostics_dict)
    """
    diag = {
        "signal_rows": len(signal_df),
        "ecg_missing": False,
        "signal_empty": False,
        "n_windows": 0,
        "eda_requested": False,
        "eda_present": False,
        "eda_cleaning_ok": False,
        "eeg_requested": False,
        "eeg_present": False,
        "face_requested": False,
        "face_present": False,
        "face_windows_with_data": 0,
        "empty_ecg_windows": 0,
        "drop_reason": None,
    }

    if "ECG" not in signal_df.columns or signal_df.empty:
        diag["ecg_missing"] = "ECG" not in signal_df.columns
        diag["signal_empty"] = signal_df.empty
        diag["drop_reason"] = "no_ecg_or_empty_signal"
        return None, [], diag

    modalities = [m.upper() for m in getattr(config.dataset, "modalities", ["ECG"])]

    # --- ECG windows (used as the master time grid) ---
    ecg_raw = signal_df["ECG"].to_numpy(dtype=float)
    ecg_clean = clean_ecg(
        ecg_raw,
        sampling_rate=loader.sample_rate,
        package=config.preprocessing.cleaning_package,
    )
    windows = segmenter.segment(ecg_clean)
    diag["n_windows"] = len(windows)
    if not windows:
        diag["drop_reason"] = "no_windows"
        return None, [], diag

    ecg_feats = []
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
            ecg_feats.append(f)
            if not f:
                diag["empty_ecg_windows"] += 1
        except Exception:
            ecg_feats.append({})
            diag["empty_ecg_windows"] += 1

    # --- EDA features (same time grid) ---
    eda_feats = []
    diag["eda_requested"] = "EDA" in modalities
    diag["eda_present"] = "EDA" in signal_df.columns
    if diag["eda_requested"] and diag["eda_present"]:
        eda_raw = signal_df["EDA"].to_numpy(dtype=float)
        try:
            eda_cleaned = clean_eda(eda_raw, sampling_rate=loader.sample_rate, package="neurokit2")
            tonic = eda_cleaned["tonic"]
            phasic = eda_cleaned["phasic"]
            diag["eda_cleaning_ok"] = True
            for w in windows:
                start = w["start_sample"]
                end = w["end_sample"]
                try:
                    f = extract_eda_features(tonic[start:end], phasic[start:end], sampling_rate=loader.sample_rate)
                    eda_feats.append(f)
                except Exception:
                    eda_feats.append({})
        except Exception as e:
            print(f"  {_diag_prefix}[warn] EDA cleaning failed: {e}")

    # --- EEG features (same time grid) ---
    eeg_feats = []
    diag["eeg_requested"] = "EEG" in modalities
    eeg_channel_cols = [c for c in signal_df.columns if c.startswith("EEG.")]
    diag["eeg_present"] = len(eeg_channel_cols) > 0
    if diag["eeg_requested"] and diag["eeg_present"]:
        try:
            eeg_data = signal_df[eeg_channel_cols].to_numpy(dtype=float).T
            for w in windows:
                start = w["start_sample"]
                end = w["end_sample"]
                try:
                    f = extract_eeg_features(
                        eeg_data[:, start:end],
                        sampling_rate=loader.sample_rate,
                        channels=eeg_channel_cols,
                    )
                    eeg_feats.append(f)
                except Exception:
                    eeg_feats.append({})
        except Exception as e:
            print(f"  {_diag_prefix}[warn] EEG extraction failed: {e}")

    # --- Webcam / face features (aligned by absolute GAME-TIMESTAMP) ---
    face_feats = []
    diag["face_requested"] = "FACE" in modalities
    diag["face_present"] = face_df is not None and not face_df.empty
    if diag["face_requested"] and diag["face_present"]:
        ts_col = "GAME-TIMESTAMP"
        if ts_col in face_df.columns:
            timestamps = signal_df["TIMESTAMP"].to_numpy(dtype=float)
            for w in windows:
                try:
                    # Map window sample indices to absolute biosignal timestamps.
                    window_start_ts = timestamps[w["start_sample"]]
                    window_end_ts = timestamps[w["end_sample"] - 1]
                    f = extract_webcam_features(
                        face_df,
                        window_start_s=window_start_ts,
                        window_end_s=window_end_ts,
                        timestamp_col=ts_col,
                    )
                    face_feats.append(f)
                    if f:
                        diag["face_windows_with_data"] += 1
                except Exception:
                    face_feats.append({})

    # Merge per-window dicts
    merged = []
    for i in range(len(windows)):
        m = {}
        m.update(ecg_feats[i])
        if eda_feats:
            m.update(eda_feats[i])
        if eeg_feats:
            m.update(eeg_feats[i])
        if face_feats:
            m.update(face_feats[i])
        merged.append(m)

    if not merged or all(not m for m in merged):
        diag["drop_reason"] = "all_windows_empty"
        return None, [], diag
    X, feature_names = features_to_matrix(merged)
    X = impute_missing(X, strategy="median")
    return X, feature_names, diag


def _process_one_subject(args_tuple):
    """Process one subject: clean, segment, extract features, optionally baseline-correct."""
    sid, loader, segmenter, config, label = args_tuple
    diag = {"sid": sid, "face_status": "unknown", "stage": "ok"}
    try:
        record = loader.load_subject(sid)
        face_df = record.get("face")
        diag["face_status"] = record.get("face_status", "unknown")
        X, names, feat_diag = _extract_signal_features(
            record["signal"], loader, segmenter, config, face_df=face_df,
            _diag_prefix=f"[{sid}] ",
        )
        diag.update(feat_diag)
        if X is None:
            diag["stage"] = "dropped_in_feature_extraction"
            return sid, None, None, label, diag

        baseline_correction = getattr(config.preprocessing, "baseline_correction", "none")
        if baseline_correction in ("change_score", "quotient"):
            baseline_signal = loader.load_baseline_signal(
                sid,
                max_length_s=float(config.preprocessing.baseline_length_s),
            )
            baseline_X, _, _ = _extract_signal_features(
                baseline_signal, loader, segmenter, config, face_df=face_df
            )
            if baseline_X is not None and baseline_X.shape[0] > 0:
                if baseline_X.shape[1] != X.shape[1]:
                    print(f"  [warn {sid}] baseline/game feature count mismatch ({baseline_X.shape[1]} vs {X.shape[1]}); leaving uncorrected")
                else:
                    corrector = BaselineCorrector(method=baseline_correction)
                    X = corrector.fit_transform(baseline_X, X)
            else:
                print(f"  [warn {sid}] no baseline features; leaving game features uncorrected")

        y = np.full(len(X), fill_value=label, dtype=int)
        return sid, X, y, label, (names, diag)
    except Exception as e:
        diag["stage"] = f"ERROR: {e}"
        return sid, None, None, label, diag


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
    n_levels = loader._level_count() if getattr(config.dataset, "treat_levels_as_subjects", False) else 1
    real_count = len(loader.available_files)
    print(f"[pipeline] real subjects in biosig archive: {real_count}")
    print(f"[pipeline] expected pseudo-subjects: {real_count * n_levels}")
    print(f"[pipeline] pseudo-subjects with valid label metadata: {len(subjects)}")

    # Fast label lookup from metadata (no signal loading)
    scores = np.array([_load_label_from_metadata(loader, sid) for sid in subjects])
    labeler = FlowLabeler(config.label)
    labels, mask = labeler.fit_transform(scores)

    print(f"Label distribution: low={np.sum(labels == 0)}, high={np.sum(labels == 1)}, excluded={np.sum(~mask)}")
    print(f"Median={labeler.median_:.3f}, IQR={labeler.iqr_:.3f}")

    active_subjects = [sid for i, sid in enumerate(subjects) if mask[i]]
    print(f"[pipeline] pseudo-subjects after label exclusion mask: {len(active_subjects)}")

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
    feature_names = []
    skipped = 0
    diagnostics = {
        "processed": 0,
        "kept": 0,
        "dropped_no_signal": 0,
        "dropped_no_windows": 0,
        "dropped_all_windows_empty": 0,
        "dropped_other": 0,
        "face_present_count": 0,
        "face_missing_count": 0,
        "eda_cleaning_ok_count": 0,
        "eda_cleaning_fail_count": 0,
        "total_windows_kept": 0,
        "per_subject": [],
    }
    for sid, X, y, label, info in results:
        diagnostics["processed"] += 1
        if X is None:
            skipped += 1
            if isinstance(info, dict):
                diagnostics["per_subject"].append(info)
                if info.get("drop_reason") == "no_ecg_or_empty_signal":
                    diagnostics["dropped_no_signal"] += 1
                elif info.get("drop_reason") == "no_windows":
                    diagnostics["dropped_no_windows"] += 1
                elif info.get("drop_reason") == "all_windows_empty":
                    diagnostics["dropped_all_windows_empty"] += 1
                else:
                    diagnostics["dropped_other"] += 1
                if info.get("face_present"):
                    diagnostics["face_present_count"] += 1
                else:
                    diagnostics["face_missing_count"] += 1
                if info.get("eda_cleaning_ok"):
                    diagnostics["eda_cleaning_ok_count"] += 1
                elif info.get("eda_requested"):
                    diagnostics["eda_cleaning_fail_count"] += 1
                print(f"  [skip {sid}] drop_reason={info.get('drop_reason')}, "
                      f"signal_rows={info.get('signal_rows')}, windows={info.get('n_windows')}, "
                      f"face={info.get('face_present')}, eda_ok={info.get('eda_cleaning_ok')}, "
                      f"face_status={info.get('face_status')}")
            else:
                diagnostics["dropped_other"] += 1
                print(f"  [skip {sid}] {info}")
            continue
        X_by_subject[sid] = X
        y_by_subject[sid] = y
        diagnostics["kept"] += 1
        diagnostics["total_windows_kept"] += X.shape[0]
        names, sub_diag = info if isinstance(info, tuple) else ([], {})
        if sub_diag:
            diagnostics["per_subject"].append(sub_diag)
            if sub_diag.get("face_present"):
                diagnostics["face_present_count"] += 1
            else:
                diagnostics["face_missing_count"] += 1
            if sub_diag.get("eda_cleaning_ok"):
                diagnostics["eda_cleaning_ok_count"] += 1
            elif sub_diag.get("eda_requested"):
                diagnostics["eda_cleaning_fail_count"] += 1
        if not feature_names and isinstance(names, list):
            feature_names = names

    # Recover feature names from config if the runner did not return them.
    if not feature_names:
        feature_names = list(config.features.ecg.time + config.features.ecg.frequency + config.features.ecg.nonlinear)

    print(f"Subjects used: {len(X_by_subject)}, skipped: {skipped}")
    print(
        f"[extraction diag] processed={diagnostics['processed']}, kept={diagnostics['kept']}, "
        f"dropped_no_signal={diagnostics['dropped_no_signal']}, "
        f"dropped_no_windows={diagnostics['dropped_no_windows']}, "
        f"dropped_all_windows_empty={diagnostics['dropped_all_windows_empty']}, "
        f"dropped_other={diagnostics['dropped_other']}, "
        f"face_present={diagnostics['face_present_count']}, "
        f"face_missing={diagnostics['face_missing_count']}, "
        f"eda_ok={diagnostics['eda_cleaning_ok_count']}, "
        f"eda_fail={diagnostics['eda_cleaning_fail_count']}, "
        f"total_windows_kept={diagnostics['total_windows_kept']}"
    )
    if feature_names:
        print(f"Feature count: {len(feature_names)}")

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


def load_irshad_data_fast(config: Config, n_jobs: int = -1):
    """Load and process Irshad/PhySF data in parallel."""
    zip_path = config.dataset.external_zip_path or config.dataset.path
    loader = IrshadLoader(zip_path, modalities=config.dataset.modalities)
    subjects = loader.list_subjects()
    print(f"[pipeline] Irshad subjects in archive: {len(subjects)}")
    labels = np.array([loader.get_label(sid) for sid in subjects])
    print(f"Label distribution: low={np.sum(labels == 0)}, high={np.sum(labels == 1)}")

    segmenter = WindowSegmenter(
        window_length_s=config.segmentation.window_length_s,
        step_s=config.segmentation.step_s,
        sampling_rate=loader.sample_rate,
    )

    active = [(sid, loader, segmenter, config, labels[i]) for i, sid in enumerate(subjects)]

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
    feature_names = []
    skipped = 0
    diagnostics = {
        "processed": 0,
        "kept": 0,
        "dropped_no_signal": 0,
        "dropped_no_windows": 0,
        "dropped_all_windows_empty": 0,
        "dropped_other": 0,
        "face_present_count": 0,
        "face_missing_count": 0,
        "eda_cleaning_ok_count": 0,
        "eda_cleaning_fail_count": 0,
        "total_windows_kept": 0,
        "per_subject": [],
    }
    for sid, X, y, label, info in results:
        diagnostics["processed"] += 1
        if X is None:
            skipped += 1
            if isinstance(info, dict):
                diagnostics["per_subject"].append(info)
                if info.get("drop_reason") == "no_ecg_or_empty_signal":
                    diagnostics["dropped_no_signal"] += 1
                elif info.get("drop_reason") == "no_windows":
                    diagnostics["dropped_no_windows"] += 1
                elif info.get("drop_reason") == "all_windows_empty":
                    diagnostics["dropped_all_windows_empty"] += 1
                else:
                    diagnostics["dropped_other"] += 1
                if info.get("face_present"):
                    diagnostics["face_present_count"] += 1
                else:
                    diagnostics["face_missing_count"] += 1
                if info.get("eda_cleaning_ok"):
                    diagnostics["eda_cleaning_ok_count"] += 1
                elif info.get("eda_requested"):
                    diagnostics["eda_cleaning_fail_count"] += 1
                print(f"  [skip {sid}] drop_reason={info.get('drop_reason')}, "
                      f"signal_rows={info.get('signal_rows')}, windows={info.get('n_windows')}, "
                      f"face={info.get('face_present')}, eda_ok={info.get('eda_cleaning_ok')}, "
                      f"face_status={info.get('face_status')}")
            else:
                diagnostics["dropped_other"] += 1
                print(f"  [skip {sid}] {info}")
            continue
        X_by_subject[sid] = X
        y_by_subject[sid] = y
        diagnostics["kept"] += 1
        diagnostics["total_windows_kept"] += X.shape[0]
        names, sub_diag = info if isinstance(info, tuple) else ([], {})
        if sub_diag:
            diagnostics["per_subject"].append(sub_diag)
            if sub_diag.get("face_present"):
                diagnostics["face_present_count"] += 1
            else:
                diagnostics["face_missing_count"] += 1
            if sub_diag.get("eda_cleaning_ok"):
                diagnostics["eda_cleaning_ok_count"] += 1
            elif sub_diag.get("eda_requested"):
                diagnostics["eda_cleaning_fail_count"] += 1
        if not feature_names and isinstance(names, list):
            feature_names = names

    # Recover feature names from config if the runner did not return them.
    if not feature_names:
        feature_names = list(config.features.ecg.time + config.features.ecg.frequency + config.features.ecg.nonlinear)

    print(f"Subjects used: {len(X_by_subject)}, skipped: {skipped}")
    print(
        f"[extraction diag] processed={diagnostics['processed']}, kept={diagnostics['kept']}, "
        f"dropped_no_signal={diagnostics['dropped_no_signal']}, "
        f"dropped_no_windows={diagnostics['dropped_no_windows']}, "
        f"dropped_all_windows_empty={diagnostics['dropped_all_windows_empty']}, "
        f"dropped_other={diagnostics['dropped_other']}, "
        f"face_present={diagnostics['face_present_count']}, "
        f"face_missing={diagnostics['face_missing_count']}, "
        f"eda_ok={diagnostics['eda_cleaning_ok_count']}, "
        f"eda_fail={diagnostics['eda_cleaning_fail_count']}, "
        f"total_windows_kept={diagnostics['total_windows_kept']}"
    )
    if feature_names:
        print(f"Feature count: {len(feature_names)}")

    if X_by_subject:
        total_windows = sum(X.shape[0] for X in X_by_subject.values())
        first_sid = next(iter(X_by_subject))
        X_first = X_by_subject[first_sid]
        nan_frac = np.mean(np.isnan(X_first))
        print(f"Total windows across subjects: {total_windows}")
        print(f"First subject {first_sid}: shape={X_first.shape}, NaN fraction={nan_frac:.3%}")
        empty_cols = np.sum(np.all(np.isnan(X_first), axis=0))
        print(f"First subject all-NaN columns: {empty_cols}/{X_first.shape[1]}")

    # Dummy labeler that exposes describe() so the reporting layer stays happy.
    class _IrshadLabeler:
        def describe(self):
            return {"method": "filename", "classes": ["no_flow", "flow"]}

    return X_by_subject, y_by_subject, feature_names, _IrshadLabeler()


def run(config: Config, n_jobs: int = -1):
    print(f"Experiment: {config.experiment_name}")
    print(f"Dataset: {config.dataset.name}, Modalities: {config.dataset.modalities}")

    if config.dataset.name.startswith("BIRAFFE2"):
        X_by_subject, y_by_subject, feature_names, labeler = load_biraffe2_data_fast(config, n_jobs=n_jobs)
    elif config.dataset.name.startswith("Irshad"):
        X_by_subject, y_by_subject, feature_names, labeler = load_irshad_data_fast(config, n_jobs=n_jobs)
    else:
        raise NotImplementedError(f"Dataset {config.dataset.name} not implemented yet.")

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

    dataset_group = "irshad" if config.dataset.name.startswith("Irshad") else "biraffe2"
    output_dir = Path("results") / dataset_group / config.experiment_name
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
