"""Run all ablation setups that need no new loaders.

This script sequentially runs:
- Setup 02: median-split margin 0.1
- Setup 03: without Time Distortion (uses pre-aggregated column for now)
- Setup 04: no z-standardisation
- Setup 05: no outlier removal
- Setup 07: 5-minute fixed window
- Setup 09: heartpy cleaning/features

Outputs are written to results/<experiment_name>/ as usual.
"""
import subprocess
import sys
from pathlib import Path

CONFIGS = [
    "config/setup_02_label_margin_01.yaml",
    "config/setup_03_without_time_distortion.yaml",
    "config/setup_04_no_zscore.yaml",
    "config/setup_05_no_outlier.yaml",
    "config/setup_07_5min_window.yaml",
    "config/setup_09_heartpy.yaml",
]

RUNNER = "scripts/run_experiment_fast.py"
N_JOBS = "-1"


def main():
    root = Path(__file__).parent.parent
    failures = []
    for cfg in CONFIGS:
        print(f"\n{'=' * 60}")
        print(f"Running {cfg}")
        print("=" * 60)
        cmd = [
            sys.executable,
            str(root / RUNNER),
            "--config",
            str(root / cfg),
            "--n-jobs",
            N_JOBS,
        ]
        result = subprocess.run(cmd, cwd=str(root))
        if result.returncode != 0:
            failures.append(cfg)
            print(f"[FAIL] {cfg}")
        else:
            print(f"[OK] {cfg}")

    print("\n" + "=" * 60)
    print("Batch run finished.")
    if failures:
        print(f"Failures ({len(failures)}):")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    else:
        print("All setups completed successfully.")


if __name__ == "__main__":
    main()
