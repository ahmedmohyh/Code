"""Run a batch of experiment configs defined in a YAML file.

The batch YAML has the following structure:

    batch_name: "my_batch"
    n_jobs: 10
    configs:
      - "config/biraffe2/normal_configs/setup_01.yaml"
      - "config/biraffe2/normal_configs/setup_02.yaml"

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


def _progress_path(root: Path, batch_name: str) -> Path:
    return root / "cache" / "batch_progress" / f".{batch_name}_progress.json"


def _load_progress(path: Path) -> set:
    if not path.exists():
        return set()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return set(data.get("completed", []))
    except Exception:
        return set()


def _save_progress(path: Path, completed: set, failed: list):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"completed": sorted(completed), "failed": failed}, f, indent=2)


def main():
    parser = argparse.ArgumentParser(description="Run a batch of experiment configs from a YAML list.")
    parser.add_argument("--batch", required=True, help="Path to the batch YAML file")
    parser.add_argument("--resume", action="store_true", help="Skip configs that already completed successfully")
    args = parser.parse_args()

    root = Path(__file__).parent.parent
    batch = load_batch(args.batch)
    batch_name = batch.get("batch_name", Path(args.batch).stem)
    n_jobs = batch.get("n_jobs", 10)
    configs = batch.get("configs", [])

    if not configs:
        print("No configs found in batch YAML.")
        sys.exit(1)

    progress_path = _progress_path(root, batch_name)
    completed = _load_progress(progress_path)

    print(f"\nBatch: {batch_name}")
    print(f"Number of configs: {len(configs)}")
    print(f"n_jobs per config: {n_jobs}")
    if args.resume:
        print(f"Resuming: {len(completed)} already completed")
    print(f"Progress file: {progress_path}")

    results = []
    failures = []

    for cfg_path in configs:
        experiment_name = Path(cfg_path).stem
        if args.resume and cfg_path in completed:
            print(f"\n[SKIP] {cfg_path} — already completed")
            metrics = read_subject_auc(root, experiment_name)
            results.append({
                "config": cfg_path,
                "experiment": experiment_name,
                "success": True,
                "skipped": True,
                **metrics,
            })
            continue

        success = run_single(cfg_path, n_jobs, root)
        metrics = read_subject_auc(root, experiment_name) if success else {}
        results.append({
            "config": cfg_path,
            "experiment": experiment_name,
            "success": success,
            **metrics,
        })
        if success:
            completed.add(cfg_path)
            _save_progress(progress_path, completed, failures)
        else:
            failures.append(cfg_path)
            _save_progress(progress_path, completed, failures)

    # Print summary table
    print("\n" + "=" * 70)
    print(f"Batch '{batch_name}' summary")
    print("=" * 70)
    print(f"{'Config':<55} {'Status':<8} {'Model':<18} {'AUC':<6} {'n'}")
    print("-" * 70)
    for r in results:
        if r.get("skipped"):
            status = "SKIP"
        else:
            status = "OK" if r["success"] else "FAIL"
        model = r.get("model", "—")
        auc = f"{r['auc']:.3f}" if r.get("auc") is not None else "—"
        n = str(r.get("n", "—"))
        print(f"{r['config']:<55} {status:<8} {model:<18} {auc:<6} {n}")

    if failures:
        print("\nFailures:")
        for f in failures:
            print(f"  - {f}")
        print(f"\nTo resume, run the same command with --resume")
        sys.exit(1)

    print("\nAll configs completed successfully.")
    if progress_path.exists():
        progress_path.unlink()


if __name__ == "__main__":
    main()
