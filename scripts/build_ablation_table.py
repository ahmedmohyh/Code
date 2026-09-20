"""Build a single ablation comparison table from all BIRAFFE2 experiment results.

Reads every `results/biraffe2/<experiment>/metrics.json`, extracts the best
subject-level AUC per experiment (and per model), then writes:

- `results/biraffe2/ablation_comparison.md` — human-readable Markdown table
- `results/biraffe2/ablation_comparison.csv` — machine-readable CSV

Usage:
    python scripts/build_ablation_table.py
"""
import argparse
import csv
import json
from pathlib import Path
from typing import Dict, List, Optional

RESULTS_DIR: Path = Path("results") / "biraffe2"
OUTPUT_MD: Path = RESULTS_DIR / "ablation_comparison.md"
OUTPUT_CSV: Path = RESULTS_DIR / "ablation_comparison.csv"
OUTPUT_PERM_MD: Path = RESULTS_DIR / "permutation_importance.md"
OUTPUT_PERM_CSV: Path = RESULTS_DIR / "permutation_importance.csv"
OUTPUT_PERM_GROUP_MD: Path = RESULTS_DIR / "permutation_importance_by_group.md"
OUTPUT_PERM_GROUP_CSV: Path = RESULTS_DIR / "permutation_importance_by_group.csv"


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
            "permutation_importance": model_data.get("permutation_importance"),
        })
    return rows


def extract_permutation_rows(metrics: dict, experiment: str) -> tuple:
    """Extract per-feature and per-group permutation-importance rows.

    Returns (feature_rows, group_rows). Both are empty if no permutation data.
    """
    feature_rows = []
    group_rows = []
    models = metrics.get("models", {})
    for model_name, model_data in models.items():
        if not isinstance(model_data, dict):
            continue
        perm = model_data.get("permutation_importance")
        if not perm:
            continue
        sub = model_data.get("subject_aggregate", {})
        auc = sub.get("auc")
        for name, stats in perm.get("per_feature", {}).items():
            feature_rows.append({
                "experiment": experiment,
                "model": model_name,
                "auc": auc,
                "feature": name,
                "group": stats.get("group", "unknown"),
                "importance_mean": stats["mean"],
                "importance_std": stats["std"],
                "n_folds": stats["n_folds"],
            })
        for group, stats in perm.get("per_group", {}).items():
            group_rows.append({
                "experiment": experiment,
                "model": model_name,
                "auc": auc,
                "group": group,
                "importance_mean": stats["mean"],
                "importance_std": stats["std"],
                "n_features": stats["n_features"],
                "top_feature": stats["top_feature"],
                "top_feature_score": stats["top_feature_score"],
            })
    return feature_rows, group_rows


def build_table(results_dir: Path) -> tuple:
    table = []
    perm_feature_rows = []
    perm_group_rows = []
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
        frows, grows = extract_permutation_rows(metrics, experiment)
        perm_feature_rows.extend(frows)
        perm_group_rows.extend(grows)
    return table, perm_feature_rows, perm_group_rows


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


def write_permutation_markdown(feature_rows: List[dict], group_rows: List[dict],
                               output_md: Path, output_group_md: Path) -> None:
    lines = [
        "# Permutation Feature Importance",
        "",
        "Mean accuracy drop when a feature is randomly shuffled within the left-out "
        "subject's windows. Values are averaged across LOSO folds. Only experiments "
        "run with `validation.permutation: true` are shown.",
        "",
        "| Experiment | Model | Feature | Group | Importance | Std | n_folds |",
        "|------------|-------|---------|-------|------------|-----|---------|",
    ]
    for row in sorted(feature_rows, key=lambda r: (-float(r.get("importance_mean") or 0), r["experiment"], r["feature"])):
        lines.append(
            f"| {row['experiment']} | {row['model']} | {row['feature']} | {row['group']} | "
            f"{format_value(row['importance_mean'])} | {format_value(row['importance_std'])} | {row['n_folds']} |"
        )
    lines.append("")
    lines.append(f"*Generated on {Path(__file__).parent.parent.name}*")
    output_md.write_text("\n".join(lines), encoding="utf-8")

    group_lines = [
        "# Permutation Importance by Feature Group",
        "",
        "Group averages of per-feature permutation importance.",
        "",
        "| Experiment | Model | Group | Mean Importance | Std | n_features | Top Feature | Top Score |",
        "|------------|-------|-------|-----------------|-----|------------|-------------|-----------|",
    ]
    for row in sorted(group_rows, key=lambda r: (-float(r.get("importance_mean") or 0), r["experiment"], r["group"])):
        group_lines.append(
            f"| {row['experiment']} | {row['model']} | {row['group']} | "
            f"{format_value(row['importance_mean'])} | {format_value(row['importance_std'])} | "
            f"{row['n_features']} | {row['top_feature']} | {format_value(row['top_feature_score'])} |"
        )
    group_lines.append("")
    group_lines.append(f"*Generated on {Path(__file__).parent.parent.name}*")
    output_group_md.write_text("\n".join(group_lines), encoding="utf-8")


def write_permutation_csv(feature_rows: List[dict], group_rows: List[dict],
                          output_csv: Path, output_group_csv: Path) -> None:
    f_fieldnames = [
        "experiment", "model", "auc", "feature", "group",
        "importance_mean", "importance_std", "n_folds",
    ]
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=f_fieldnames)
        writer.writeheader()
        for row in feature_rows:
            writer.writerow({k: (row[k] if row[k] is not None else "") for k in f_fieldnames})

    g_fieldnames = [
        "experiment", "model", "auc", "group", "importance_mean",
        "importance_std", "n_features", "top_feature", "top_feature_score",
    ]
    with open(output_group_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=g_fieldnames)
        writer.writeheader()
        for row in group_rows:
            writer.writerow({k: (row[k] if row[k] is not None else "") for k in g_fieldnames})


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
    output_perm_md = results_dir / "permutation_importance.md"
    output_perm_csv = results_dir / "permutation_importance.csv"
    output_perm_group_md = results_dir / "permutation_importance_by_group.md"
    output_perm_group_csv = results_dir / "permutation_importance_by_group.csv"

    table, perm_feature_rows, perm_group_rows = build_table(results_dir)
    if not table:
        print("No valid metrics.json files found.")
        return

    write_markdown(table, output_md)
    write_csv(table, output_csv)
    print(f"Wrote {output_md}")
    print(f"Wrote {output_csv}")

    if perm_feature_rows:
        write_permutation_markdown(
            perm_feature_rows, perm_group_rows,
            output_perm_md, output_perm_group_md,
        )
        write_permutation_csv(
            perm_feature_rows, perm_group_rows,
            output_perm_csv, output_perm_group_csv,
        )
        print(f"Wrote {output_perm_md}")
        print(f"Wrote {output_perm_csv}")
        print(f"Wrote {output_perm_group_md}")
        print(f"Wrote {output_perm_group_csv}")
    else:
        print("No permutation-importance data found. "
              "Rerun experiments with `validation.permutation: true`.")


if __name__ == "__main__":
    main()
