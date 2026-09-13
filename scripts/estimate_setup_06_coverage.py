"""Estimate how many Setup 06 pseudo-subjects survive under different window strategies.

This script only scans metadata and procedure files; it does not extract features.
"""
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

DATA_DIR = Path("../dataset/data/BIRAFFE2/Version 2")
META_PATH = DATA_DIR / "BIRAFFE2-metadata.csv"
PROC_ZIP = DATA_DIR / "BIRAFFE2-procedure.zip"

score_cols = ["GEQ-1-FLOW-2018", "GEQ-2-FLOW-2018", "GEQ-3-FLOW-2018"]


def load_game_times():
    times = {}
    if not PROC_ZIP.exists():
        print(f"Procedure zip not found: {PROC_ZIP}")
        return times
    with zipfile.ZipFile(PROC_ZIP) as z:
        for name in z.namelist():
            if not name.endswith(".csv") or "procedure" not in name.lower():
                continue
            # Try to extract subject id from filename like SUB100-procedure.csv
            try:
                sub_str = Path(name).stem.split("-")[0].replace("SUB", "")
                sub_id = int(sub_str)
            except Exception:
                continue
            with z.open(name) as f:
                df = pd.read_csv(f, sep=None, engine="python")
            df.columns = [c.strip().upper() for c in df.columns]
            if "TIMESTAMP" not in df.columns or "EVENT" not in df.columns:
                continue
            starts = df.loc[df["EVENT"].str.upper() == "GAME START", "TIMESTAMP"].to_numpy(dtype=float)
            ends = df.loc[df["EVENT"].str.upper() == "GAME END", "TIMESTAMP"].to_numpy(dtype=float)
            if len(starts) > 0 and len(ends) > 0:
                times[sub_id] = (float(starts[0]), float(ends[0]))
    return times


def main():
    meta = pd.read_csv(META_PATH, sep=";")
    game_times = load_game_times()

    # Filter to subjects present in metadata with all 3 score columns non-NaN
    meta = meta.dropna(subset=score_cols)
    n_real = len(meta)
    print(f"Real subjects with all 3 GEQ scores: {n_real}")
    print(f"Expected pseudo-subjects (3 levels each): {n_real * 3}")

    # Estimate total recorded duration per subject from procedure GAME times
    durations = []
    level_durations = []
    for _, row in meta.iterrows():
        sub_id = int(row["ID"])
        if sub_id in game_times:
            start, end = game_times[sub_id]
            dur = end - start
        else:
            dur = np.nan
        durations.append(dur)

        # Per-level duration = total / 3
        if not np.isnan(dur) and dur > 0:
            level_durations.extend([dur / 3.0] * 3)

    durations = np.array(durations, dtype=float)
    level_durations = np.array(level_durations, dtype=float)

    print(f"\nGAME phase duration statistics (seconds):")
    print(f"  mean={np.nanmean(durations):.1f}, median={np.nanmedian(durations):.1f}")
    print(f"  min={np.nanmin(durations):.1f}, max={np.nanmax(durations):.1f}")

    print(f"\nPer-level segment duration statistics (seconds):")
    print(f"  mean={np.nanmean(level_durations):.1f}, median={np.nanmedian(level_durations):.1f}")
    print(f"  min={np.nanmin(level_durations):.1f}, max={np.nanmax(level_durations):.1f}")

    # Estimate pseudo-subjects kept for different strategies
    print("\nEstimated pseudo-subjects kept by strategy:")
    print("-" * 60)

    strategies = [
        ("60 s window, strict", 60, 60, False),
        ("30 s window, strict", 30, 30, False),
        ("20 s window, strict", 20, 20, False),
        ("60 s window + 30 s fallback", 60, 30, True),
        ("60 s window + 20 s fallback", 60, 20, True),
        ("60 s window + 10 s fallback", 60, 10, True),
    ]

    for label, win_len, min_win, fallback in strategies:
        if fallback:
            # Long segments get 60s windows; short segments get one window if >= min_win
            mask = level_durations >= win_len
            n_long = int(mask.sum())
            n_short = int((~mask & (level_durations >= min_win)).sum())
            kept = n_long + n_short
        else:
            kept = int((level_durations >= win_len).sum())
        print(f"  {label:30s}: {kept:3d} / {len(level_durations)} ({kept/len(level_durations)*100:.1f}%)")

    # Also show how many level segments are shorter than common thresholds
    print("\nDistribution of level segment durations:")
    thresholds = [10, 20, 30, 40, 50, 60, 90, 120]
    for t in thresholds:
        count = int((level_durations >= t).sum())
        print(f"  >= {t:3d} s: {count:3d} / {len(level_durations)} ({count/len(level_durations)*100:.1f}%)")


if __name__ == "__main__":
    main()
