"""Grid-search hyperparameter tuning for classical classifiers.

For each config the script:
1. Loads the data once with run_experiment_fast.load_*_data_fast.
2. Runs LOSO CV for every hyperparameter combination in the grid.
3. Reports the best hyperparameters by subject-level AUC.
4. Saves the tuned results to a separate results/grid_search/<config> directory.

Supports both single-config and batch YAML modes.
"""
import argparse
import json
import subprocess
import sys
from itertools import product
from pathlib import Path

import numpy as np
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))

from flow_lol.models.classical import build_classifier
from flow_lol.utils.config import load_config
from flow_lol.validation.loso_cv import run_loso_cv
from flow_lol.reporting.ablation_table import save_results
from scripts.run_experiment_fast import (
    load_biraffe2_data_fast,
    load_irshad_data_fast,
)


# ---------------------------------------------------------------------------
# Define grids per classifier
# ---------------------------------------------------------------------------
GRIDS = {
    "RandomForest": {
        "n_estimators": [100, 200, 500],
        "max_depth": [None, 10, 20, 30],
        "min_samples_split": [2, 5, 10],
        "min_samples_leaf": [1, 2, 4],
        "class_weight": ["balanced", "balanced_subsample"],
    },
    "XGBoost": {
        "n_estimators": [100, 200, 500],
        "max_depth": [3, 4, 6],
        "learning_rate": [0.01, 0.05, 0.1],
        "subsample": [0.8, 1.0],
    },
    "SVM": {
        "C": [0.1, 1.0, 10.0],
        "kernel": ["rbf", "linear"],
        "gamma": ["scale", "auto", 0.001, 0.01],
        "class_weight": ["balanced"],
    },
    "LogisticRegression": {
        "C": [0.01, 0.1, 1.0, 10.0],
        "penalty": ["l2"],
        "solver": ["lbfgs", "saga"],
        "max_iter": [1000, 2000],
        "class_weight": ["balanced"],
    },
    "kNN": {
        "n_neighbors": [3, 5, 7, 9],
        "weights": ["uniform", "distance"],
        "p": [1, 2],
    },
}


def _make_grid(model_name: str):
    """Return list of hyperparameter dicts for a model."""
    grid = GRIDS.get(model_name, {})
    if not grid:
        return [{}]
    keys, values = zip(*grid.items())
    return [dict(zip(keys, combo)) for combo in product(*values)]


def _run_one_config(config, n_jobs: int = -1):
    """Run grid search for a single config and return best results."""
    print(f"\n{'='*60}")
    print(f"Grid search: {config.experiment_name}")
    print(f"Classical models: {config.models.classical}")
    print(f"{'='*60}")

    # Load data once
    if config.dataset.name.startswith("BIRAFFE2"):
        X_by_subject, y_by_subject, feature_names, labeler = load_biraffe2_data_fast(
            config, n_jobs=n_jobs, cache_dir="cache/biosigs"
        )
    elif config.dataset.name.startswith("Irshad"):
        X_by_subject, y_by_subject, feature_names, labeler = load_irshad_data_fast(
            config, n_jobs=n_jobs
        )
    else:
        raise NotImplementedError(f"Dataset {config.dataset.name} not implemented.")

    all_results = {}
    best_by_model = {}

    for model_name in config.models.classical:
        grid = _make_grid(model_name)
        print(f"\n--- {model_name}: {len(grid)} hyperparameter combinations ---")
        best_auc = -np.inf
        best_combo = None
        best_cv = None

        for i, params in enumerate(grid, 1):
            print(f"[{i}/{len(grid)}] {params}")

            def builder(name=model_name, p=params):
                return build_classifier(name, random_state=config.seed, **p)

            cv_results = run_loso_cv(
                X_by_subject,
                y_by_subject,
                model_builder=builder,
                z_standardise=config.preprocessing.z_standardise,
                outlier_strategy=config.preprocessing.outlier_strategy,
                run_permutation=False,
                feature_names=feature_names,
                random_state=config.seed,
                n_jobs=5,
            )
            sub_agg = cv_results.get("subject_aggregate", {})
            auc = sub_agg.get("auc", np.nan)
            print(f"      -> subject AUC = {auc:.4f}  (n={sub_agg.get('n_subjects_used', 0)})")

            if not np.isnan(auc) and auc > best_auc:
                best_auc = auc
                best_combo = params
                best_cv = cv_results

        best_by_model[model_name] = {
            "best_params": best_combo,
            "best_subject_auc": float(best_auc) if not np.isinf(best_auc) else np.nan,
            "best_cv": best_cv,
        }
        print(f"Best for {model_name}: AUC={best_auc:.4f}, params={best_combo}")
        all_results[model_name] = best_cv

    # Save results
    dataset_group = "irshad" if config.dataset.name.startswith("Irshad") else "biraffe2"
    output_dir = Path("results") / dataset_group / "grid_search" / config.experiment_name
    output_dir.mkdir(parents=True, exist_ok=True)

    final = {
        "experiment_name": config.experiment_name,
        "labeler_description": labeler.describe(),
        "feature_names": feature_names,
        "best_params_by_model": {k: v["best_params"] for k, v in best_by_model.items()},
        "best_subject_auc_by_model": {
            k: v["best_subject_auc"] for k, v in best_by_model.items()
        },
        "models": all_results,
    }
    save_results(final, {"grid_search": True}, str(output_dir))

    summary_path = output_dir / "grid_search_summary.json"
    with open(summary_path, "w") as f:
        json.dump(
            {
                "experiment": config.experiment_name,
                "best_by_model": best_by_model,
            },
            f,
            indent=2,
            default=lambda o: o.tolist() if hasattr(o, "tolist") else str(o),
        )
    print(f"\nResults saved to: {output_dir}")
    print(f"Summary saved to: {summary_path}")

    return best_by_model


def _load_batch(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _run_single_config(config_path: str, n_jobs: int, root: Path) -> bool:
    print(f"\n{'=' * 70}")
    print(f"Running grid search for {config_path}")
    print("=" * 70)
    cmd = [
        sys.executable,
        str(root / "scripts" / "run_grid_search.py"),
        "--config",
        str(root / config_path),
        "--n-jobs",
        str(n_jobs),
    ]
    result = subprocess.run(cmd, cwd=str(root))
    return result.returncode == 0


def _read_best_auc(root: Path, experiment_name: str) -> dict:
    for dataset_group in ("biraffe2", "irshad"):
        path = root / "results" / dataset_group / "grid_search" / experiment_name / "grid_search_summary.json"
        if not path.exists():
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            best = None
            for model_name, model_data in data.get("best_by_model", {}).items():
                auc = model_data.get("best_subject_auc")
                if auc is None:
                    continue
                if best is None or auc > best.get("auc", -1):
                    best = {
                        "model": model_name,
                        "auc": auc,
                        "params": model_data.get("best_params"),
                    }
            return best or {}
        except Exception:
            continue
    return {}


def _run_batch(batch_path: str):
    root = Path(__file__).parent.parent
    batch = _load_batch(batch_path)
    n_jobs = batch.get("n_jobs", -1)
    configs = batch.get("checkpoints", batch.get("configs", []))

    if not configs:
        print("No configs found in batch YAML.")
        sys.exit(1)

    print(f"\nGrid-search batch: {Path(batch_path).stem}")
    print(f"Number of configs: {len(configs)}")
    print(f"n_jobs per config: {n_jobs}")

    results = []
    failures = []
    for cfg_path in configs:
        success = _run_single_config(cfg_path, n_jobs, root)
        experiment_name = Path(cfg_path).stem
        best = _read_best_auc(root, experiment_name) if success else {}
        results.append({
            "config": cfg_path,
            "experiment": experiment_name,
            "success": success,
            **best,
        })
        if not success:
            failures.append(cfg_path)

    print("\n" + "=" * 70)
    print("Grid-search batch summary")
    print("=" * 70)
    print(f"{'Config':<55} {'Status':<8} {'Model':<18} {'AUC':<8}")
    print("-" * 70)
    for r in results:
        status = "OK" if r["success"] else "FAIL"
        model = r.get("model", "—")
        auc = f"{r['auc']:.3f}" if r.get("auc") is not None else "—"
        print(f"{r['config']:<55} {status:<8} {model:<18} {auc:<8}")

    if failures:
        print("\nFailures:")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)

    print("\nAll grid-search configs completed successfully.")


def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--config", help="Path to single YAML config")
    group.add_argument("--batch", help="Path to batch YAML file")
    parser.add_argument("--n-jobs", type=int, default=-1, help="Parallel workers for feature extraction (-1 = all cores)")
    args = parser.parse_args()

    if args.batch:
        _run_batch(args.batch)
    else:
        config = load_config(args.config)
        _run_one_config(config, n_jobs=args.n_jobs)


if __name__ == "__main__":
    main()
