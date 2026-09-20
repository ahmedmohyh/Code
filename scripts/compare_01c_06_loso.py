"""Compare Setup 01c and Setup 06 LOSO inputs/folds to find why skip counts differ.

Reads existing metrics.json files and also rebuilds label vectors to check
exactly which pseudo-subjects are shared, which labels differ, and why folds
are skipped.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import numpy as np
from flow_lol.utils.config import load_config
from flow_lol.preprocessing.outlier_handler import OutlierHandler
from flow_lol.preprocessing.normaliser import ZStandardiser
from flow_lol.features.feature_union import impute_missing
from scripts.run_experiment_fast import load_biraffe2_data_fast


def load_results(name):
    path = Path(f"results/biraffe2/{name}/metrics.json")
    with open(path) as f:
        return json.load(f)


def main():
    print("=" * 70)
    print("Comparing Setup 01c vs Setup 06 LOSO behaviour")
    print("=" * 70)

    # 1. Compare metrics.json summaries
    r01c = load_results("setup_01c_biraffe2_ecg_levels_as_subjects")
    r06 = load_results("setup_06_full_multimodal")

    for name, res in [("01c", r01c), ("06", r06)]:
        rf = res["models"]["RandomForest"]
        agg = rf["aggregate"]
        sub = rf["subject_aggregate"]
        print(f"\n{name} metrics.json:")
        print(f"  n_subjects (entered LOSO) : {agg['n_subjects']}")
        print(f"  n_skipped                 : {agg['n_skipped']}")
        print(f"  n_fit_errors              : {agg['n_fit_errors']}")
        print(f"  subject_aggregate n_used  : {sub['n_subjects_used']}")
        print(f"  subject_aggregate AUC     : {sub['auc']}")

    # 2. Rebuild X_by_subject, y_by_subject for both configs
    print("\nRebuilding data loaders...")
    cfg01c = load_config("config/biraffe2/normal_configs/setup_01c_biraffe2_ecg_levels_as_subjects.yaml")
    cfg06 = load_config("config/biraffe2/normal_configs/setup_06_full_multimodal.yaml")

    print("\nLoading 01c (ECG only)...")
    X01c, y01c, names01c, _ = load_biraffe2_data_fast(cfg01c, n_jobs=18, cache_dir="cache/biosigs")
    print("\nLoading 06 (ECG+EDA+FACE)...")
    X06, y06, names06, _ = load_biraffe2_data_fast(cfg06, n_jobs=18, cache_dir="cache/biosigs")

    s01c = set(X01c.keys())
    s06 = set(X06.keys())
    print(f"\nSubject sets:")
    print(f"  01c: {len(s01c)} subjects")
    print(f"  06:  {len(s06)} subjects")
    print(f"  intersection: {len(s01c & s06)}")
    print(f"  only in 01c: {sorted(s01c - s06)}")
    print(f"  only in 06:  {sorted(s06 - s01c)}")

    common = sorted(s01c & s06)
    label_diff = [sid for sid in common if int(y01c[sid][0]) != int(y06[sid][0])]
    print(f"\nCommon subjects with different labels: {len(label_diff)}")
    if label_diff:
        print(f"  Examples: {label_diff[:10]}")
        for sid in label_diff[:5]:
            print(f"    {sid}: 01c={int(y01c[sid][0])}, 06={int(y06[sid][0])}")

    # 3. Simulate LOSO skip condition for both setups
    print("\nSimulating LOSO skip condition (matching run_loso_cv logic)...")

    def simulate(X_by_subject, y_by_subject, outlier_strategy="train_only", z_standardise=True):
        subjects = sorted(X_by_subject.keys())
        skipped = []
        window_drop_stats = []
        for i, test_subject in enumerate(subjects):
            train_subjects = [s for j, s in enumerate(subjects) if j != i]
            X_train = np.vstack([X_by_subject[s] for s in train_subjects])
            y_train = np.hstack([y_by_subject[s] for s in train_subjects])
            X_test = X_by_subject[test_subject]
            y_test = y_by_subject[test_subject]

            # Replicate exact LOSO CV preprocessing
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

            scaler = ZStandardiser(active=z_standardise)
            X_train = scaler.fit_transform(X_train)
            X_test = scaler.transform(X_test)

            X_train = impute_missing(X_train, strategy="median")
            X_test = impute_missing(X_test, strategy="median")

            full_X = np.vstack([X_train, X_test])
            valid_cols = ~np.all(np.isnan(full_X), axis=0)
            if not np.all(valid_cols):
                X_train = X_train[:, valid_cols]
                X_test = X_test[:, valid_cols]

            reasons = []
            if len(np.unique(y_train)) < 2:
                reasons.append("single_class_train")
            if X_train.shape[0] == 0:
                reasons.append("empty_train")
            if X_test.shape[0] == 0:
                reasons.append("empty_test")
            ytrue = int(y_test[0]) if len(y_test) > 0 else -1
            if reasons:
                skipped.append((test_subject, reasons, ytrue, len(y_test)))
            window_drop_stats.append({
                "sid": test_subject,
                "n_train_before": len(train_subjects),
                "n_windows_train_before": int(sum(X_by_subject[s].shape[0] for s in train_subjects)),
                "n_windows_train_after": int(X_train.shape[0]),
                "n_windows_test_before": int(X_by_subject[test_subject].shape[0]),
                "n_windows_test_after": int(X_test.shape[0]),
                "train_dropped": int(sum(X_by_subject[s].shape[0] for s in train_subjects) - X_train.shape[0]),
                "test_dropped": int(X_by_subject[test_subject].shape[0] - X_test.shape[0]),
            })
        return skipped, window_drop_stats

    skip01c, drop01c = simulate(X01c, y01c)
    skip06, drop06 = simulate(X06, y06)

    print(f"\n01c simulated skips: {len(skip01c)}")
    print(f"06  simulated skips: {len(skip06)}")

    for name, skips in [("01c", skip01c), ("06", skip06)]:
        print(f"\n{name} skip reasons:")
        from collections import Counter
        reason_counts = Counter()
        for sid, reasons, ytrue, ntest in skips:
            reason_counts.update(reasons)
        for reason, count in reason_counts.items():
            print(f"  {reason}: {count}")

    # Window drop statistics
    def print_drop_stats(name, drop_stats):
        total_train_dropped = sum(d["train_dropped"] for d in drop_stats)
        total_train_before = sum(d["n_windows_train_before"] for d in drop_stats)
        total_test_dropped = sum(d["test_dropped"] for d in drop_stats)
        total_test_before = sum(d["n_windows_test_before"] for d in drop_stats)
        print(f"\n{name} window drops due to outlier handling:")
        print(f"  total train windows before outlier: {total_train_before}")
        print(f"  total train windows dropped: {total_train_dropped} ({total_train_dropped/total_train_before:.1%})")
        print(f"  total test windows dropped: {total_test_dropped} / {total_test_before}")
        max_train_drop = max(drop_stats, key=lambda d: d["train_dropped"])
        max_test_drop = max(drop_stats, key=lambda d: d["test_dropped"])
        print(f"  worst train fold: sid={max_train_drop['sid']}, dropped={max_train_drop['train_dropped']} windows")
        print(f"  worst test fold:  sid={max_test_drop['sid']}, dropped={max_test_drop['test_dropped']} windows")

    print_drop_stats("01c", drop01c)
    print_drop_stats("06", drop06)

    # 4. Find subjects skipped in 06 but not in 01c
    skip01c_set = {sid for sid, _, _, _ in skip01c}
    skip06_set = {sid for sid, _, _, _ in skip06}
    only06 = sorted(skip06_set - skip01c_set)
    print(f"\nSubjects skipped in 06 but NOT in 01c: {len(only06)}")
    print(f"  First 20: {only06[:20]}")
    for sid in only06[:10]:
        print(f"    {sid}: 01c windows={X01c[sid].shape[0]}, 06 windows={X06[sid].shape[0]}, label={int(y06[sid][0])}")

    # Also simulate with outlier_strategy='none' to predict the fix
    print("\nPredicting fix: simulating with outlier_strategy='none'...")
    skip01c_none, _ = simulate(X01c, y01c, outlier_strategy="none")
    skip06_none, _ = simulate(X06, y06, outlier_strategy="none")
    print(f"  01c with no outlier removal: {len(skip01c_none)} skips")
    print(f"  06  with no outlier removal: {len(skip06_none)} skips")

    # 5. Check feature NaN rates
    print("\nFeature NaN / zero-constant checks for common subjects:")
    nan01c = []
    nan06 = []
    for sid in common:
        X = X01c[sid]
        nan_frac = np.mean(np.isnan(X))
        nan01c.append(nan_frac)
        X2 = X06[sid]
        nan_frac2 = np.mean(np.isnan(X2))
        nan06.append(nan_frac2)
    print(f"  01c mean NaN fraction: {np.mean(nan01c):.4%}")
    print(f"  06  mean NaN fraction: {np.mean(nan06):.4%}")

    # 6. Save detailed report as Markdown
    out_dir = Path("results/biraffe2/setup_06_dropout")
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / "compare_01c_06_loso.md"
    lines = [
        "# Setup 01c vs Setup 06 LOSO dropout comparison",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Subjects in 01c | {len(s01c)} |",
        f"| Subjects in 06 | {len(s06)} |",
        f"| Common subjects | {len(common)} |",
        f"| Label differences | {len(label_diff)} |",
        f"| Simulated skipped in 01c | {len(skip01c)} |",
        f"| Simulated skipped in 06 | {len(skip06)} |",
        "",
        f"## Skipped in 06 but not in 01c ({len(only06)} subjects)",
        "",
        ", ".join(str(s) for s in only06) if only06 else "_None_",
        "",
        f"## Skipped in 01c but not in 06 ({len(skip01c_set - skip06_set)} subjects)",
        "",
        ", ".join(str(s) for s in sorted(skip01c_set - skip06_set)) if (skip01c_set - skip06_set) else "_None_",
        "",
    ]
    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nSaved comparison report: {report_path}")


if __name__ == "__main__":
    main()
