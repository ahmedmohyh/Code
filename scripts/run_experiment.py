"""Run one ML pipeline experiment from a YAML config."""
import argparse
import sys
import warnings
from pathlib import Path

import numpy as np
from tqdm import tqdm

# Add package root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flow_lol.utils.config import Config, load_config, save_config
from flow_lol.data.loaders.biraffe2_loader import BIRAFFE2Loader
from flow_lol.data.labelers.flow_labeler import FlowLabeler, compute_flow_score
from flow_lol.preprocessing.cleaners.ecg_cleaner import clean_ecg
from flow_lol.segmentation.window_segmenter import WindowSegmenter
from flow_lol.features.extractors.ecg_features import extract_ecg_features
from flow_lol.features.feature_union import features_to_matrix, impute_missing
from flow_lol.models.classical import build_classifier, list_available_classifiers
from flow_lol.models.deep import build_deep_classifier
from flow_lol.validation.loso_cv import run_loso_cv
from flow_lol.reporting.ablation_table import save_results

warnings.filterwarnings("ignore", category=RuntimeWarning)


def load_biraffe2_data(config: Config):
    """Load BIRAFFE2 subjects, labels and per-window features."""
    loader = BIRAFFE2Loader(config.dataset)
    subjects = loader.list_subjects()
    print(f"Found {len(subjects)} valid subjects with biosignals and labels.")

    # Build labels globally (median / margin on all subjects)
    scores = np.array([loader.load_subject(sid)["label"] for sid in tqdm(subjects, desc="Loading labels")])
    labeler = FlowLabeler(config.label)
    labels, mask = labeler.fit_transform(scores)

    print(f"Label distribution: low={np.sum(labels == 0)}, high={np.sum(labels == 1)}, "
          f"excluded={np.sum(~mask)}")
    print(f"Median={labeler.median_:.3f}, IQR={labeler.iqr_:.3f}, "
          f"thresholds=[{labeler.low_threshold_:.3f}, {labeler.high_threshold_:.3f}]")

    segmenter = WindowSegmenter(
        window_length_s=config.segmentation.window_length_s,
        step_s=config.segmentation.step_s,
        sampling_rate=loader.sample_rate,
    )

    X_by_subject = {}
    y_by_subject = {}
    skipped = 0

    sid_to_idx = {sid: i for i, sid in enumerate(subjects)}
    active_subjects = [sid for sid, m in zip(subjects, mask) if m]
    pbar = tqdm(active_subjects, desc="Cleaning + extracting features")
    for idx, sid in enumerate(active_subjects):
        record = loader.load_subject(sid)
        ecg_raw = record["signal"]["ECG"].to_numpy(dtype=float)

        # Clean whole signal
        try:
            ecg_clean = clean_ecg(
                ecg_raw,
                sampling_rate=loader.sample_rate,
                package=config.preprocessing.cleaning_package,
            )
        except Exception as e:
            pbar.write(f"  [skip subject {sid}] ECG cleaning failed: {e}")
            skipped += 1
            continue

        # Segment and extract features
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

        if len(feats) == 0:
            pbar.write(f"  [skip subject {sid}] no features extracted")
            skipped += 1
            continue

        X, feature_names = features_to_matrix(feats)
        X = impute_missing(X, strategy="median")

        X_by_subject[sid] = X
        y_by_subject[sid] = np.full(len(X), fill_value=labels[sid_to_idx[sid]], dtype=int)
        pbar.set_postfix({"windows": len(feats), "feats": X.shape[1]})

    pbar.close()
    print(f"Subjects used: {len(X_by_subject)}, skipped: {skipped}")
    return X_by_subject, y_by_subject, feature_names, labeler


def run(config: Config):
    print(f"Experiment: {config.experiment_name}")
    print(f"Dataset: {config.dataset.name}, Modalities: {config.dataset.modalities}")

    if config.dataset.name.startswith("BIRAFFE2"):
        X_by_subject, y_by_subject, feature_names, labeler = load_biraffe2_data(config)
    else:
        raise NotImplementedError(f"Dataset {config.dataset.name} not implemented yet.")

    # Build model(s)
    results_all = {}
    for model_name in config.models.classical:
        print(f"\nRunning LOSO CV for classical model: {model_name}")

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
        )
        results_all[model_name] = cv_results
        agg = cv_results["aggregate"]
        print(f"  Accuracy={agg.get('accuracy', np.nan):.3f} "
              f"F1={agg.get('f1_macro', np.nan):.3f} "
              f"AUC={agg.get('auc', np.nan):.3f} "
              f"Inference={agg.get('mean_inference_ms', np.nan):.1f}ms")

    output_dir = Path("results") / config.experiment_name
    final_results = {
        "experiment_name": config.experiment_name,
        "labeler_description": labeler.describe(),
        "feature_names": feature_names,
        "models": results_all,
    }
    save_results(final_results, config.__dict__, str(output_dir))
    print(f"\nResults saved to: {output_dir}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, help="Path to YAML config file")
    args = parser.parse_args()

    config = load_config(args.config)
    run(config)


if __name__ == "__main__":
    main()
