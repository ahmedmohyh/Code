"""Build and save ablation result tables."""
import json
from pathlib import Path
from typing import Dict, List

import pandas as pd


def save_results(results: Dict, config_dict: Dict, output_dir: str) -> None:
    """Save metrics and config to disk."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    with open(out / "metrics.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    with open(out / "config.json", "w", encoding="utf-8") as f:
        json.dump(config_dict, f, indent=2, ensure_ascii=False)

    # Save aggregate metrics as a small CSV row
    if "aggregate" in results:
        agg = {k: v for k, v in results["aggregate"].items() if not isinstance(v, list)}
        agg["n_subjects"] = results.get("n_subjects", 0)
        df = pd.DataFrame([agg])
        df.to_csv(out / "aggregate_metrics.csv", index=False)


def build_ablation_table(rows: List[Dict], save_path: str) -> pd.DataFrame:
    """Build a table comparing multiple experimental runs."""
    df = pd.DataFrame(rows)
    df.to_csv(save_path, index=False)
    return df
