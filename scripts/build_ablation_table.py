"""Build a single ablation comparison table from all experiment results.

Reads every `results/<experiment>/metrics.json`, extracts the best
subject-level AUC per experiment (and per model), then writes:

- `results/ablation_comparison.md` — human-readable Markdown table
- `results/ablation_comparison.csv` — machine-readable CSV

Usage:
    python scripts/build_ablation_table.py
"""
import argparse
import csv
import json
from pathlib import Path
from typing import Dict, List, Optional

RESULTS_DIR: Path = Path("results")
OUTPUT_MD: Path = RESULTS_DIR / "ablation_comparison.md"
OUTPUT_CSV: Path = RESULTS_DIR / "ablation_comparison.csv"


def load_metrics(path: Path) -> Optional[dict]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def extract_subject_aggregates(metrics: dict) -> List[dict]:
    """Return one row per model with subject-level aggregate metrics."""
    rows = []
    models = metrics.get("models", {})
    for model_name, model_data in models.items():
        if not isinstance(model_data, dict):
            continue
        sub = model_data.get("subject_aggregate", {})
        if not sub:
            continue
        rows.append({
            "model": model_name,
            "accuracy": sub.get("accuracy"),
            "f1_macro": sub.get("f1_macro"),
            "auc": sub.get("auc"),
            "n": sub.get("n_subjects_used"),
        })
    return rows


def build_table(results_dir: Path) -> List[dict]:
    table = []
    for metrics_file in sorted(results_dir.rglob("metrics.json")):
        experiment = metrics_file.parent.name
        metrics = load_metrics(metrics_file)
        if metrics is None:
            continue
        model_rows = extract_subject_aggregates(metrics)
        if not model_rows:
            continue
        # Sort by AUC descending; handle NaN/None as worst
        def auc_key(row):
            auc = row.get("auc")
            if auc is None:
                return -1.0
            return float(auc)
        best = max(model_rows, key=auc_key)
        table.append({
            "experiment": experiment,
            "best_model": best["model"],
            "accuracy": best["accuracy"],
            "f1_macro": best["f1_macro"],
            "auc": best["auc"],
            "n": best["n"],
        })
    return table


def format_value(v, fmt=".3f"):
    if v is None:
        return "—"
    try:
        return f"{float(v):{fmt}}"
    except (TypeError, ValueError):
        return str(v)


def write_markdown(table: List[dict], output_md: Path) -> None:
    lines = [
        "# Ablation Comparison Table",
        "",
        "Subject-level metrics. Best model per experiment is selected by AUC.",
        "",
        "| Experiment | Best Model | Accuracy | F1 | AUC | n |",
        "|------------|------------|----------|----|-----|---|",
    ]
    for row in table:
        lines.append(
            f"| {row['experiment']} | {row['best_model']} | "
            f"{format_value(row['accuracy'])} | {format_value(row['f1_macro'])} | "
            f"{format_value(row['auc'])} | {row['n'] or '—'} |"
        )
    lines.append("")
    lines.append(f"*Generated on {Path(__file__).parent.parent.name}*")
    output_md.write_text("\n".join(lines), encoding="utf-8")


def write_csv(table: List[dict], output_csv: Path) -> None:
    fieldnames = ["experiment", "best_model", "accuracy", "f1_macro", "auc", "n"]
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in table:
            writer.writerow({k: (row[k] if row[k] is not None else "") for k in fieldnames})


def main():
    parser = argparse.ArgumentParser(
        description="Build a Markdown/CSV ablation comparison table from all results."
    )
    parser.add_argument(
        "--results-dir",
        default=str(RESULTS_DIR),
        help="Directory containing experiment result subdirectories",
    )
    args = parser.parse_args()

    results_dir = Path(args.results_dir)
    output_md = results_dir / "ablation_comparison.md"
    output_csv = results_dir / "ablation_comparison.csv"

    table = build_table(results_dir)
    if not table:
        print("No valid metrics.json files found.")
        return

    write_markdown(table, output_md)
    write_csv(table, output_csv)
    print(f"Wrote {output_md}")
    print(f"Wrote {output_csv}")


if __name__ == "__main__":
    main()
