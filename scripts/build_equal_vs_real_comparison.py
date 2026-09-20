"""Build a side-by-side comparison of equal-split vs. real-level-timestamp setups.

Reads `results/biraffe2/ablation_comparison.csv` (equal split) and
`results/biraffe2/ablation_comparison_real_level_times.csv`, matches experiments by
base name, and writes:

- results/biraffe2/equal_vs_real_level_times.md
- results/biraffe2/equal_vs_real_level_times.csv

The higher AUC in each row is bolded.

Usage:
    python scripts/build_equal_vs_real_comparison.py
"""
import csv
from pathlib import Path

RESULTS_DIR = Path("results") / "biraffe2"
OUTPUT_MD = RESULTS_DIR / "equal_vs_real_level_times.md"
OUTPUT_CSV = RESULTS_DIR / "equal_vs_real_level_times.csv"


def read_csv(path: Path) -> list:
    rows = []
    with open(path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def format_value(v, decimals=3):
    try:
        return f"{float(v):.{decimals}f}"
    except (TypeError, ValueError):
        return "—"


def main():
    equal_rows = {r["experiment"]: r for r in read_csv(RESULTS_DIR / "ablation_comparison.csv")}
    real_rows = {r["experiment"]: r for r in read_csv(RESULTS_DIR / "ablation_comparison_real_level_times.csv")}

    # Map real-level experiment names to base names
    base_to_real = {}
    for real_name in real_rows:
        base_name = real_name.replace("_real_level_times", "")
        base_to_real[base_name] = real_name

    matched = []
    for base_name in sorted(base_to_real):
        real_name = base_to_real[base_name]
        equal_row = equal_rows.get(base_name)
        real_row = real_rows.get(real_name)
        if equal_row is None or real_row is None:
            continue

        equal_auc = equal_row.get("auc")
        real_auc = real_row.get("auc")
        try:
            equal_auc_f = float(equal_auc) if equal_auc else None
        except ValueError:
            equal_auc_f = None
        try:
            real_auc_f = float(real_auc) if real_auc else None
        except ValueError:
            real_auc_f = None

        matched.append({
            "setup": base_name,
            "equal_model": equal_row.get("best_model"),
            "equal_auc": equal_auc_f,
            "equal_n": equal_row.get("n"),
            "real_model": real_row.get("best_model"),
            "real_auc": real_auc_f,
            "real_n": real_row.get("n"),
        })

    # Markdown
    lines = [
        "# Equal Split vs. Real Level Timestamps",
        "",
        "Side-by-side subject-level AUC comparison. The higher AUC in each row is bolded.",
        "",
        "| Setup | Equal Split Model | Equal Split AUC | Equal Split n | Real Timestamps Model | Real Timestamps AUC | Real Timestamps n |",
        "|-------|-------------------|-----------------|---------------|----------------------|---------------------|-------------------|",
    ]
    for row in matched:
        equal_auc_str = format_value(row["equal_auc"])
        real_auc_str = format_value(row["real_auc"])
        if row["equal_auc"] is not None and row["real_auc"] is not None:
            if row["equal_auc"] > row["real_auc"]:
                equal_auc_str = f"**{equal_auc_str}**"
            elif row["real_auc"] > row["equal_auc"]:
                real_auc_str = f"**{real_auc_str}**"
            else:
                equal_auc_str = f"**{equal_auc_str}**"
                real_auc_str = f"**{real_auc_str}**"

        lines.append(
            f"| {row['setup']} | {row['equal_model'] or '—'} | {equal_auc_str} | {row['equal_n'] or '—'} | "
            f"{row['real_model'] or '—'} | {real_auc_str} | {row['real_n'] or '—'} |"
        )
    lines.append("")
    lines.append("*Generated from `ablation_comparison.csv` and `ablation_comparison_real_level_times.csv`.*")
    OUTPUT_MD.write_text("\n".join(lines), encoding="utf-8")

    # CSV
    fieldnames = [
        "setup", "equal_model", "equal_auc", "equal_n",
        "real_model", "real_auc", "real_n",
    ]
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in matched:
            writer.writerow({k: (row[k] if row[k] is not None else "") for k in fieldnames})

    print(f"Wrote {OUTPUT_MD}")
    print(f"Wrote {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
