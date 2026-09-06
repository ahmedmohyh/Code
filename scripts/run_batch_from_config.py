"""Run a batch of experiment configs defined in a YAML file.

The batch YAML has the following structure:

    batch_name: "my_batch"
    n_jobs: 10
    configs:
      - "config/setup_01.yaml"
      - "config/setup_02.yaml"

Each config is run sequentially. If one fails, the script records the failure
and continues with the remaining configs, then exits with code 1.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

import yaml

RUNNER = "scripts/run_experiment_fast.py"


def load_batch(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def run_single(config_path: str, n_jobs: int, root: Path) -> bool:
    print(f"\n{'=' * 70}")
    print(f"Running {config_path}")
    print("=" * 70)
    cmd = [
        sys.executable,
        str(root / RUNNER),
        "--config",
        str(root / config_path),
        "--n-jobs",
        str(n_jobs),
    ]
    result = subprocess.run(cmd, cwd=str(root))
    return result.returncode == 0


def read_subject_auc(root: Path, experiment_name: str) -> dict:
    """Try to read the subject-level AUC from the results JSON."""
    results_dir = root / "results" / experiment_name
    for filename in ("metrics.json", "results.json"):
        path = results_dir / filename
        if not path.exists():
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            models = data.get("models", data)
            for model_name, model_data in models.items():
                if not isinstance(model_data, dict):
                    continue
                sub = model_data.get("subject_aggregate", {})
                if sub:
                    return {
                        "model": model_name,
                        "accuracy": sub.get("accuracy"),
                        "f1_macro": sub.get("f1_macro"),
                        "auc": sub.get("auc"),
                        "n": sub.get("n_subjects_used"),
                    }
            return {}
        except Exception:
            continue
    return {}


def main():
    parser = argparse.ArgumentParser(description="Run a batch of experiment configs from a YAML list.")
    parser.add_argument("--batch", required=True, help="Path to the batch YAML file")
    args = parser.parse_args()

    root = Path(__file__).parent.parent
    batch = load_batch(args.batch)
    batch_name = batch.get("batch_name", Path(args.batch).stem)
    n_jobs = batch.get("n_jobs", 10)
    configs = batch.get("configs", [])

    if not configs:
        print("No configs found in batch YAML.")
        sys.exit(1)

    print(f"\nBatch: {batch_name}")
    print(f"Number of configs: {len(configs)}")
    print(f"n_jobs per config: {n_jobs}")

    results = []
    failures = []

    for cfg_path in configs:
        success = run_single(cfg_path, n_jobs, root)
        experiment_name = Path(cfg_path).stem
        metrics = read_subject_auc(root, experiment_name) if success else {}
        results.append({
            "config": cfg_path,
            "experiment": experiment_name,
            "success": success,
            **metrics,
        })
        if not success:
            failures.append(cfg_path)

    # Print summary table
    print("\n" + "=" * 70)
    print(f"Batch '{batch_name}' summary")
    print("=" * 70)
    print(f"{'Config':<55} {'Status':<8} {'Model':<18} {'AUC':<6} {'n'}")
    print("-" * 70)
    for r in results:
        status = "OK" if r["success"] else "FAIL"
        model = r.get("model", "—")
        auc = f"{r['auc']:.3f}" if r.get("auc") is not None else "—"
        n = str(r.get("n", "—"))
        print(f"{r['config']:<55} {status:<8} {model:<18} {auc:<6} {n}")

    if failures:
        print("\nFailures:")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)

    print("\nAll configs completed successfully.")


if __name__ == "__main__":
    main()
