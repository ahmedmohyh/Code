"""Generate classical-only variants of BIRAFFE2 extreme-percentile configs.

Reads every config in config/biraffe2/extreme_percentile_configs/ whose models
section contains deep-learning models, and writes a new config with:

- experiment_name suffixed with `_classical`
- `models.classical` set to all available classical classifiers
- `models.deep` set to `[]`

Also writes a batch YAML to run them all.

Usage:
    python scripts/_gen_extreme_percentile_classical_configs.py
"""
from pathlib import Path
import yaml

CONFIG_ROOT = Path("config/biraffe2/extreme_percentile_configs")
BATCH_PATH = Path("config/biraffe2/batch_extreme_percentile_classical.yaml")

CLASSICAL_MODELS = [
    "RandomForest",
    "XGBoost",
    "SVM",
    "LogisticRegression",
    "kNN",
]


def main():
    if not CONFIG_ROOT.exists():
        raise FileNotFoundError(f"Config directory not found: {CONFIG_ROOT}")

    generated = []
    for config_path in sorted(CONFIG_ROOT.glob("*.yaml")):
        cfg = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        if not isinstance(cfg, dict):
            continue

        models = cfg.get("models", {})
        deep = models.get("deep", [])
        classical = models.get("classical", [])

        # Only generate a variant if the original actually used deep models.
        if not deep:
            continue

        new_cfg = cfg.copy()
        base_name = cfg["experiment_name"]
        new_name = f"{base_name}_classical"
        new_cfg["experiment_name"] = new_name
        new_cfg["models"] = {
            "classical": CLASSICAL_MODELS,
            "deep": [],
        }

        new_path = CONFIG_ROOT / f"{new_name}.yaml"
        new_path.write_text(
            yaml.safe_dump(new_cfg, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
        generated.append(new_path.relative_to(Path("config").parent).as_posix())

    if not generated:
        print("No deep-learning extreme-percentile configs found; nothing generated.")
        return

    batch = {
        "batch_name": "biraffe2_extreme_percentile_classical",
        "n_jobs": -1,
        "configs": sorted(generated),
    }
    batch_rel = BATCH_PATH.relative_to(Path("config").parent).as_posix()
    BATCH_PATH.write_text(
        f"# Batch config for BIRAFFE2 extreme-percentile labeling with classical classifiers only.\n"
        f"# Run with: python scripts/run_batch_from_config.py --batch {batch_rel}\n\n"
        + yaml.safe_dump(batch, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )

    print(f"Generated {len(generated)} classical-only configs in {CONFIG_ROOT}")
    print(f"Wrote batch file: {BATCH_PATH}")
    print(f"Run them with: python scripts/run_batch_from_config.py --batch {BATCH_PATH}")


if __name__ == "__main__":
    main()
