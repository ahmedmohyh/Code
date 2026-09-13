"""Diagnose why Setup 06 pseudo-subjects are dropped, without running LOSO CV.

This script loads the Setup 06 config, processes every pseudo-subject, and
reports per-subject diagnostics:
  - Why a subject was dropped (no signal / no windows / empty features / error)
  - Whether EDA and FACE data were present and usable
  - How many windows were extracted
  - Which features were produced

No models are trained. Results are printed and saved to
results/setup_06_dropout/diagnostic_report.txt and per_subject_diagnostics.csv.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from flow_lol.utils.config import load_config
from flow_lol.data.loaders.biraffe2_loader import BIRAFFE2Loader
from flow_lol.data.labelers.flow_labeler import FlowLabeler
from scripts.run_experiment_fast import (
    _extract_signal_features,
    _process_one_subject,
    _cache_subject,
)
from flow_lol.segmentation.window_segmenter import WindowSegmenter
from tqdm import tqdm
import numpy as np
import pandas as pd

CONFIG_PATH = Path("config/setup_06_full_multimodal.yaml")
CACHE_DIR = "cache/biosigs"
OUTPUT_DIR = Path("results/setup_06_dropout")


def main():
    config = load_config(str(CONFIG_PATH))
    print(f"Config: {config.experiment_name}")
    print(f"Modalities: {config.dataset.modalities}")
    print(f"Window: {config.segmentation.window_length_s}s, step {config.segmentation.step_s}s")
    print(f"Score columns: {config.dataset.score_column}")
    print(f"treat_levels_as_subjects: {config.dataset.treat_levels_as_subjects}")
    print("-" * 70)

    loader = BIRAFFE2Loader(config.dataset, cache_dir=CACHE_DIR)
    subjects = loader.list_subjects()
    n_levels = loader._level_count() if config.dataset.treat_levels_as_subjects else 1
    real_count = len(loader.available_files)
    expected = real_count * n_levels

    print(f"Real subjects in biosig archive: {real_count}")
    print(f"Expected pseudo-subjects: {expected}")
    print(f"Pseudo-subjects with valid label metadata: {len(subjects)}")

    # Cache all files first so we can re-use the fast path.
    print(f"\nPre-extracting/caching {len(subjects)} biosignal files...")
    for sid in tqdm(subjects, desc="Caching", ascii=True, ncols=80):
        _cache_subject(loader, sid)

    segmenter = WindowSegmenter(
        window_length_s=config.segmentation.window_length_s,
        step_s=config.segmentation.step_s,
        sampling_rate=loader.sample_rate,
    )

    scores = np.array([loader.get_label(sid) for sid in subjects])
    labeler = FlowLabeler(config.label)
    labels, mask = labeler.fit_transform(scores)
    print(f"\nLabel distribution: low={np.sum(labels == 0)}, high={np.sum(labels == 1)}, excluded={np.sum(~mask)}")
    print(f"Median score={labeler.median_:.3f}, IQR={labeler.iqr_:.3f}")

    active = [(sid, loader, segmenter, config, labels[i]) for i, sid in enumerate(subjects) if mask[i]]
    print(f"\nProcessing {len(active)} pseudo-subjects sequentially for diagnostics...")

    rows = []
    kept_sids = []
    for item in tqdm(active, desc="Subjects", ascii=True, ncols=80):
        sid, X, y, label, info = _process_one_subject(item)
        if isinstance(info, tuple):
            names, sub_diag = info
        else:
            sub_diag = info if isinstance(info, dict) else {}
            names = []

        row = {
            "sid": sid,
            "real_id": sid // 1000,
            "level": sid % 1000,
            "label": int(label) if label is not None else -1,
            "kept": X is not None,
            "drop_reason": sub_diag.get("drop_reason") if isinstance(sub_diag, dict) else None,
            "signal_rows": sub_diag.get("signal_rows") if isinstance(sub_diag, dict) else None,
            "n_windows": sub_diag.get("n_windows") if isinstance(sub_diag, dict) else None,
            "empty_ecg_windows": sub_diag.get("empty_ecg_windows") if isinstance(sub_diag, dict) else None,
            "eda_requested": sub_diag.get("eda_requested") if isinstance(sub_diag, dict) else None,
            "eda_present": sub_diag.get("eda_present") if isinstance(sub_diag, dict) else None,
            "eda_cleaning_ok": sub_diag.get("eda_cleaning_ok") if isinstance(sub_diag, dict) else None,
            "face_requested": sub_diag.get("face_requested") if isinstance(sub_diag, dict) else None,
            "face_present": sub_diag.get("face_present") if isinstance(sub_diag, dict) else None,
            "face_status": sub_diag.get("face_status") if isinstance(sub_diag, dict) else None,
            "face_windows_with_data": sub_diag.get("face_windows_with_data") if isinstance(sub_diag, dict) else None,
            "stage": sub_diag.get("stage") if isinstance(sub_diag, dict) else None,
            "n_features": X.shape[1] if X is not None else 0,
            "n_kept_windows": X.shape[0] if X is not None else 0,
        }
        rows.append(row)
        if X is not None:
            kept_sids.append(sid)

    df = pd.DataFrame(rows)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_DIR / "per_subject_diagnostics.csv", index=False)

    # Summary report
    report = []
    report.append(f"Setup 06 diagnostic run")
    report.append(f"Real subjects in biosig archive: {real_count}")
    report.append(f"Expected pseudo-subjects: {expected}")
    report.append(f"Pseudo-subjects with valid label metadata: {len(subjects)}")
    report.append(f"Pseudo-subjects after label mask: {len(active)}")
    report.append(f"Pseudo-subjects kept with features: {len(kept_sids)}")
    report.append("")

    report.append("Drop reason counts:")
    for reason, count in df["drop_reason"].value_counts(dropna=False).items():
        report.append(f"  {reason}: {count}")
    report.append("")

    report.append("EDA availability among dropped subjects:")
    dropped = df[~df["kept"]]
    report.append(f"  eda_requested={dropped['eda_requested'].sum()}")
    report.append(f"  eda_present={dropped['eda_present'].sum()}")
    report.append(f"  eda_cleaning_ok={dropped['eda_cleaning_ok'].sum()}")
    report.append("EDA availability among kept subjects:")
    kept = df[df["kept"]]
    report.append(f"  eda_requested={kept['eda_requested'].sum()}")
    report.append(f"  eda_present={kept['eda_present'].sum()}")
    report.append(f"  eda_cleaning_ok={kept['eda_cleaning_ok'].sum()}")
    report.append("")

    report.append("FACE availability among dropped subjects:")
    report.append(f"  face_requested={dropped['face_requested'].sum()}")
    report.append(f"  face_present={dropped['face_present'].sum()}")
    report.append(f"  face_windows_with_data>0={(dropped['face_windows_with_data'] > 0).sum()}")
    report.append("FACE availability among kept subjects:")
    report.append(f"  face_requested={kept['face_requested'].sum()}")
    report.append(f"  face_present={kept['face_present'].sum()}")
    report.append(f"  face_windows_with_data>0={(kept['face_windows_with_data'] > 0).sum()}")
    report.append("")

    report.append("Subjects with zero windows despite non-empty signal:")
    zero_win = df[(~df["kept"]) & (df["drop_reason"] == "no_windows")]
    report.append(f"  count={len(zero_win)}")
    for _, r in zero_win.iterrows():
        report.append(f"    sid={r['sid']}, signal_rows={r['signal_rows']}, level={r['level']}")
    report.append("")

    report.append("First 20 dropped subjects:")
    for _, r in dropped.head(20).iterrows():
        report.append(
            f"  sid={r['sid']} reason={r['drop_reason']} rows={r['signal_rows']} "
            f"windows={r['n_windows']} empty_ecg={r['empty_ecg_windows']} "
            f"eda_ok={r['eda_cleaning_ok']} face_present={r['face_present']} "
            f"face_data={r['face_windows_with_data']}>0"
        )

    report_text = "\n".join(report)
    (OUTPUT_DIR / "diagnostic_report.txt").write_text(report_text, encoding="utf-8")
    print("\n" + report_text)
    print(f"\nSaved CSV: {OUTPUT_DIR / 'per_subject_diagnostics.csv'}")
    print(f"Saved report: {OUTPUT_DIR / 'diagnostic_report.txt'}")


if __name__ == "__main__":
    main()
