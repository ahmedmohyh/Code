"""Build an ablation table only for real-level-timestamp experiments.

This is the companion to `build_ablation_table.py`. It scans
`results/<experiment>_real_level_times/metrics.json` and writes:

- results/ablation_comparison_real_level_times.md
- results/ablation_comparison_real_level_times.csv

Usage:
    python scripts/build_ablation_table_real_level_times.py
"""
import csv
import json
from pathlib import Path

RESULTS_DIR = Path("results")
OUTPUT_MD = RESULTS_DIR / "ablation_comparison_real_level_times.md"
OUTPUT_CSV = RESULTS_DIR / "ablation_comparison_real_level_times.csv"

SUFFIX = "_real_level_times"


def load_metrics(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def extract_best_model(metrics):
    models = metrics.get("models", {})
    best = None
    best_auc = -1.0
    for model_name, model_data in models.items():
        if not isinstance(model_data, dict):
            continue
        sub = model_data.get("subject_aggregate", {})
        auc = sub.get("auc")
        if auc is None:
            continue
        auc = float(auc)
        if auc > best_auc:
            best_auc = auc
            best = {
                "experiment": metrics.get("experiment", "unknown"),
                "best_model": model_name,
                "accuracy": sub.get("accuracy"),
                "f1_macro": sub.get("f1_macro"),
                "auc": auc,
                "n": sub.get("n_subjects_used"),
            }
    return best


def build_table():
    rows = []
    for metrics_file in sorted(RESULTS_DIR.rglob("metrics.json")):
        experiment = metrics_file.parent.name
        if not experiment.endswith(SUFFIX):
            continue
        metrics = load_metrics(metrics_file)
        if metrics is None:
            continue
        row = extract_best_model(metrics)
        if row:
            rows.append(row)
    return rows


def format_value(v):
    if v is None:
        return "—"
    try:
        return f"{float(v):.3f}"
    except Exception:
        return str(v)


def write_md(rows):
    lines = [
        "# Ablation Comparison: Real Level Timestamps",
        "",
        "Subject-level metrics from setups run with `games_zip_path` enabled.",
        "",
        "| Experiment | Best Model | Accuracy | F1 | AUC | n |",
        "|------------|------------|----------|----|-----|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['experiment']} | {row['best_model']} | "
            f"{format_value(row['accuracy'])} | {format_value(row['f1_macro'])} | "
            f"{format_value(row['auc'])} | {row['n'] or '—'} |"
        )
    lines.append("")
    lines.append("*Generated for real level timestamp experiments.*")
    OUTPUT_MD.write_text("\n".join(lines), encoding="utf-8")


def write_csv(rows):
    fieldnames = ["experiment", "best_model", "accuracy", "f1_macro", "auc", "n"]
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: (row[k] if row[k] is not None else "") for k in fieldnames})


if __name__ == "__main__":
    rows = build_table()
    if not rows:
        print(f"No metrics found for experiments ending with {SUFFIX}.")
    else:
        write_md(rows)
        write_csv(rows)
        print(f"Wrote {OUTPUT_MD}")
        print(f"Wrote {OUTPUT_CSV}")
