"""Build a per-label-column class-balance table.

The BIRAFFE2 metadata contains six separate Flow label columns:

    GEQ-1-FLOW-2013, GEQ-2-FLOW-2013, GEQ-3-FLOW-2013,
    GEQ-1-FLOW-2018, GEQ-2-FLOW-2018, GEQ-3-FLOW-2018

Each column is an independent binary classification target. This script reads
metadata.csv, applies median-split to each column, and reports the resulting
flow vs. no-flow class balance per column, which is the correct way to assess
balance rather than aggregating across columns or setups.

Outputs:
    results/class_balance.md
    results/class_balance.csv

Usage:
    python scripts/build_class_balance_table.py
"""
import csv
from pathlib import Path

import pandas as pd

RESULTS_DIR = Path("results")
OUTPUT_MD = RESULTS_DIR / "class_balance.md"
OUTPUT_CSV = RESULTS_DIR / "class_balance.csv"


def build_table(metadata_path: Path) -> list:
    df = pd.read_csv(metadata_path, sep=";")
    flow_cols = [c for c in df.columns if "FLOW" in c.upper()]
    rows = []
    for col in flow_cols:
        vals = pd.to_numeric(df[col], errors="coerce").dropna()
        if vals.empty:
            continue
        median = vals.median()
        low = int((vals < median).sum())
        high = int((vals >= median).sum())
        total = low + high
        rows.append({
            "label_column": col,
            "median": median,
            "low": low,
            "high": high,
            "total": total,
            "low_pct": (low / total * 100) if total else 0.0,
            "high_pct": (high / total * 100) if total else 0.0,
        })
    return rows


def balance_label(row: dict) -> str:
    pct_diff = abs(row["low_pct"] - row["high_pct"])
    if pct_diff <= 5:
        return "balanced"
    if pct_diff <= 15:
        return "slight imbalance"
    if row["low_pct"] > row["high_pct"]:
        return "low majority"
    return "high majority"


def format_value(v, decimals=3):
    if v is None:
        return "—"
    if isinstance(v, float):
        return f"{v:.{decimals}f}"
    return str(v)


def write_md(rows: list) -> None:
    lines = [
        "# Class Balance per Label Column",
        "",
        "BIRAFFE2 provides six independent Flow label columns: three game levels",
        "(GEQ-1, GEQ-2, GEQ-3) measured with two questionnaire versions each",
        "(GEQ-2013 and GEQ-2018). Balance must be checked separately for each",
        "column, because each one is a distinct binary classification target.",
        "",
        "| Label Column | Median | Low n | High n | Total | Low % | High % | Balance |",
        "|--------------|--------|-------|--------|-------|-------|--------|---------|",
    ]
    for row in rows:
        lines.append(
            f"| {row['label_column']} | {format_value(row['median'])} | "
            f"{row['low']} | {row['high']} | {row['total']} | "
            f"{format_value(row['low_pct'], 1)} | {format_value(row['high_pct'], 1)} | "
            f"{balance_label(row)} |"
        )
    lines.append("")
    lines.append("*Low = score < median; High = score >= median. Median computed over all available values in the column.*")
    OUTPUT_MD.write_text("\n".join(lines), encoding="utf-8")


def write_csv(rows: list) -> None:
    fieldnames = [
        "label_column", "median", "low", "high", "total",
        "low_pct", "high_pct", "balance",
    ]
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            out = {k: (row[k] if row[k] is not None else "") for k in fieldnames if k != "balance"}
            out["balance"] = balance_label(row)
            writer.writerow(out)


if __name__ == "__main__":
    import sys
    # Find metadata from a normal config
    metadata_path = Path("../dataset/data/BIRAFFE2/Version 2/BIRAFFE2-metadata.csv")
    if not metadata_path.exists():
        # Fallback: try from repo root
        metadata_path = Path("dataset/data/BIRAFFE2/Version 2/BIRAFFE2-metadata.csv")
    if not metadata_path.exists():
        print("Could not find BIRAFFE2-metadata.csv")
        sys.exit(1)

    rows = build_table(metadata_path)
    if not rows:
        print("No Flow label columns found.")
        sys.exit(1)

    write_md(rows)
    write_csv(rows)
    print(f"Wrote {OUTPUT_MD}")
    print(f"Wrote {OUTPUT_CSV}")
