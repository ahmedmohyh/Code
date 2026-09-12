"""BIRAFFE2 biosignal and metadata loader."""
import os
import re
import zipfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from flow_lol.utils.config import DatasetConfig


class BIRAFFE2Loader:
    """Load BIRAFFE2 ECG/EDA signals and metadata.

    The biosignal files are stored inside a zip archive (e.g. BIRAFFE2-biosigs.zip).
    Each subject has one CSV: ``BIRAFFE2-biosigs/SUB<id>-BioSigs.csv`` with columns
    TIMESTAMP, ECG, EDA at 1 kHz.

    Labels are read from the main metadata CSV (semicolon-separated), which contains
    pre-computed GEQ Flow subscale scores such as ``GEQ-1-FLOW-2018``.

    Special modes
    -------------
    * ``treat_levels_as_subjects=False``, ``score_column`` is a single column or a list:
      a list is averaged into one label per subject.
    * ``treat_levels_as_subjects=True``, ``score_column`` must be a list of columns:
      each column is treated as an independent pseudo-subject level.  The GAME phase of
      the recording is split into ``N`` equal-duration segments, where ``N`` is the
      number of score columns, and each segment receives the label from the corresponding
      GEQ level.
    """

    def __init__(self, config: DatasetConfig, cache_dir: Optional[str] = None):
        self.config = config
        self.zip_path = Path(config.path)
        self.metadata_path = Path(config.metadata_path)
        self.sample_rate = 1000.0
        self.available_files: Dict[int, str] = {}
        self.metadata: Optional[pd.DataFrame] = None
        self.cache_dir = Path(cache_dir) if cache_dir else None
        # Maps real subject ID -> (game_start, game_end) when procedure files are available.
        self._game_times: Dict[int, Optional[Tuple[float, float]]] = {}
        # Maps real subject ID -> (baseline_start, baseline_end) when procedure files are available.
        self._baseline_times: Dict[int, Optional[Tuple[float, float]]] = {}
        self._raw_geq: Dict[int, pd.DataFrame] = {}
        self._recompute_flow = getattr(self.config, "recompute_flow_from_items", False)
        self._exclude_td = getattr(self.config, "exclude_time_distortion", False)
        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._scan_archive()
        self._load_metadata()
        if self._recompute_flow:
            self._load_raw_geq_items()
        # Load procedure times whenever a procedure archive is configured; this
        # makes both level-as-subjects mode and baseline correction work.
        proc_path = Path(getattr(self.config, "procedure_path", "") or "")
        if proc_path.exists():
            self._load_procedure_times()

    # ------------------------------------------------------------------
    # Archive / metadata scanning
    # ------------------------------------------------------------------
    def _scan_archive(self) -> None:
        if not self.zip_path.exists():
            raise FileNotFoundError(f"Biosig zip not found: {self.zip_path}")
        with zipfile.ZipFile(self.zip_path, "r") as zf:
            for name in zf.namelist():
                m = re.search(r"SUB(\d+)-BioSigs\.csv", name)
                if m:
                    self.available_files[int(m.group(1))] = name

    def _load_metadata(self) -> None:
        if not self.metadata_path.exists():
            raise FileNotFoundError(f"Metadata not found: {self.metadata_path}")
        self.metadata = pd.read_csv(self.metadata_path, sep=";")
        # Normalise ID column
        self.metadata["ID"] = pd.to_numeric(self.metadata["ID"], errors="coerce")

    def _load_raw_geq_items(self) -> None:
        """Load raw GEQ item CSVs and index them by level."""
        raw_dir = Path(getattr(self.config, "raw_geq_dir", "") or "")
        if not raw_dir.exists():
            raise FileNotFoundError(f"raw_geq_dir not found: {raw_dir}")
        pattern = re.compile(r"RAW-GEQ-Level(\d+)", re.IGNORECASE)
        for path in raw_dir.iterdir():
            if not path.is_file() or path.suffix.lower() != ".csv":
                continue
            m = pattern.search(path.name)
            if not m:
                continue
            level = int(m.group(1))
            df = pd.read_csv(path)
            if "ID" not in df.columns:
                raise ValueError(f"Raw GEQ file {path} has no ID column")
            df["ID"] = pd.to_numeric(df["ID"], errors="coerce")
            df = df.dropna(subset=["ID"]).set_index("ID")
            self._raw_geq[level] = df
        if not self._raw_geq:
            raise FileNotFoundError(f"No raw GEQ files found in {raw_dir}")

    @staticmethod
    def _level_from_score_column(col: str) -> int:
        """Infer GEQ level (1, 2, 3, ...) from a metadata column name."""
        m = re.search(r"GEQ-(\d+)-", col)
        if not m:
            raise ValueError(f"Cannot infer GEQ level from score column: {col}")
        return int(m.group(1))

    def _compute_raw_flow_score(self, real_id: int, level: int) -> float:
        """Recompute the Flow score from raw item responses for one level.

        BIRAFFE2 pre-computed Flow columns (GEQ-*-FLOW-2013/2018) store the
        mean item response shifted down by 1, i.e. ``mean(items) - 1``. This
        converts the 1-5 Likert scale to a 0-4 scale. The same shift is applied
        here so that recomputed scores are on the same scale as the metadata.
        """
        if level not in self._raw_geq:
            raise ValueError(f"No raw GEQ data for level {level}")
        if real_id not in self._raw_geq[level].index:
            raise ValueError(f"Subject {real_id} not found in raw GEQ level {level}")
        row = self._raw_geq[level].loc[real_id]
        flow_items = ["5", "13", "28", "31"]
        if not self._exclude_td:
            flow_items = ["5", "13", "25", "28", "31"]
        values = pd.to_numeric(row[flow_items], errors="coerce").to_numpy(dtype=float)
        return float(np.nanmean(values) - 1.0)

    # ------------------------------------------------------------------
    # Procedure-file handling (needed for level-as-subjects mode)
    # ------------------------------------------------------------------
    def _load_procedure_times(self) -> None:
        """Scan the BIRAFFE2 procedure archive and cache GAME/BASELINE times."""
        proc_path = Path(getattr(self.config, "procedure_path", "") or "")
        if not proc_path or not proc_path.exists():
            # Allow a directory containing loose procedure CSVs as a fallback.
            return

        is_zip = proc_path.suffix.lower() == ".zip"
        if is_zip:
            zf = zipfile.ZipFile(proc_path, "r")
            names = zf.namelist()
        else:
            zf = None
            names = [str(p.relative_to(proc_path)) for p in proc_path.rglob("*.csv")]

        for name in names:
            m = re.search(r"SUB(\d+)-Procedure\.csv", name, re.IGNORECASE)
            if not m:
                continue
            sid = int(m.group(1))
            try:
                if zf:
                    with zf.open(name) as f:
                        df = pd.read_csv(f, sep=";")
                else:
                    df = pd.read_csv(proc_path / name, sep=";")
            except Exception:
                continue

            start = self._find_event_time(df, ["GAME START", "GAME_START", "GAMESTART"])
            end = self._find_event_time(df, ["GAME END", "GAME_END", "GAMEEND"])
            self._game_times[sid] = (start, end) if start is not None and end is not None else None

            baseline_start = self._find_event_time(df, ["BASELINE START", "BASELINE_START", "BASELINESTART"])
            baseline_end = self._find_event_time(df, ["BASELINE END", "BASELINE_END", "BASELINEEND"])
            self._baseline_times[sid] = (baseline_start, baseline_end) if baseline_start is not None and baseline_end is not None else None

        if zf:
            zf.close()

    def get_baseline_times(self, real_id: int) -> Optional[Tuple[float, float]]:
        """Return (baseline_start, baseline_end) timestamps for a real subject, if known."""
        return self._baseline_times.get(real_id)

    @staticmethod
    def _find_event_time(df: pd.DataFrame, event_names: List[str]) -> Optional[float]:
        """Return the first timestamp matching one of the event names (case-insensitive)."""
        # Detect timestamp / event columns robustly (BIRAFFE2 uses TIMESTAMP + EVENT).
        time_col = None
        for c in df.columns:
            if c.upper() in ("TIMESTAMP", "TIME"):
                time_col = c
                break
        event_col = None
        for c in df.columns:
            if c.upper() == "EVENT":
                event_col = c
                break
        if df.empty or time_col is None or event_col is None:
            return None
        mask = df[event_col].astype(str).str.strip().str.lower().isin([e.lower() for e in event_names])
        if not mask.any():
            return None
        ts = pd.to_numeric(df.loc[mask, time_col], errors="coerce").dropna()
        if ts.empty:
            return None
        return float(ts.iloc[0])

    # ------------------------------------------------------------------
    # Label helpers
    # ------------------------------------------------------------------
    def _score_columns(self) -> List[str]:
        """Return score column(s) as a list."""
        if isinstance(self.config.score_column, list):
            return self.config.score_column
        return [self.config.score_column]

    def _level_count(self) -> int:
        """Return number of pseudo-subject levels.

        In level-as-subjects mode this equals the number of score columns,
        allowing any number of levels (e.g. 3 or 6). Otherwise it is 1.
        """
        if not getattr(self.config, "treat_levels_as_subjects", False):
            return 1
        return len(self._score_columns())

    def _pseudo_to_real(self, pseudo_id: int) -> Tuple[int, int]:
        """Decode pseudo subject ID into (real_subject_id, level_index).

        Uses a stable scheme: pseudo_id = real_id * 1000 + level_index.
        1000 is chosen to support up to 999 levels per subject.
        """
        real_id = pseudo_id // 1000
        level = pseudo_id % 1000
        return real_id, level

    def _real_to_pseudo(self, real_id: int, level: int) -> int:
        return real_id * 1000 + level

    def _get_label(self, row: pd.DataFrame, level: Optional[int] = None) -> float:
        """Read label for a subject/level.

        In level-as-subjects mode, ``level`` indexes into ``score_column``.
        Otherwise a list of columns is averaged.

        If ``recompute_flow_from_items`` is enabled, the score is computed from
        the raw GEQ item responses instead of the pre-aggregated metadata column.
        """
        cols = self._score_columns()
        real_id = int(row["ID"].values[0])

        if self._recompute_flow:
            if getattr(self.config, "treat_levels_as_subjects", False):
                if level is None:
                    raise ValueError("level required in treat_levels_as_subjects mode")
                target_level = level + 1
            elif len(cols) == 1:
                target_level = self._level_from_score_column(cols[0])
            else:
                # Average raw recomputed scores across the configured columns.
                scores = [
                    self._compute_raw_flow_score(real_id, self._level_from_score_column(c))
                    for c in cols
                ]
                return float(np.nanmean(scores))
            return self._compute_raw_flow_score(real_id, target_level)

        if getattr(self.config, "treat_levels_as_subjects", False):
            if level is None:
                raise ValueError("level required in treat_levels_as_subjects mode")
            return float(row[cols[level]].values[0])
        values = row[cols].values[0]
        if len(cols) == 1:
            return float(values)
        return float(np.nanmean(values))

    def get_label(self, subject_id: int) -> float:
        """Return the label for a real or pseudo subject without loading the signal."""
        if getattr(self.config, "treat_levels_as_subjects", False):
            real_id, level = self._pseudo_to_real(subject_id)
        else:
            real_id, level = subject_id, None

        row = self.metadata[self.metadata["ID"] == real_id]
        if row.empty:
            raise ValueError(f"Subject {real_id} not found in metadata")
        return self._get_label(row, level=level)

    # ------------------------------------------------------------------
    # Subject enumeration
    # ------------------------------------------------------------------
    def list_subjects(self) -> List[int]:
        """Return subject IDs (or pseudo-IDs) that have both biosignals and a valid label."""
        cols = self._score_columns()
        level_mode = getattr(self.config, "treat_levels_as_subjects", False)
        n_levels = self._level_count()
        valid_ids = []

        for sid in sorted(self.available_files.keys()):
            row = self.metadata[self.metadata["ID"] == sid]
            if row.empty:
                continue

            if level_mode:
                for level in range(n_levels):
                    if self._recompute_flow:
                        try:
                            score = self._compute_raw_flow_score(sid, level + 1)
                        except (ValueError, KeyError):
                            continue
                        if not pd.isna(score):
                            valid_ids.append(self._real_to_pseudo(sid, level))
                    else:
                        if not pd.isna(row[cols[level]].values[0]):
                            valid_ids.append(self._real_to_pseudo(sid, level))
            else:
                if self._recompute_flow:
                    if len(cols) == 1:
                        try:
                            score = self._compute_raw_flow_score(sid, self._level_from_score_column(cols[0]))
                        except (ValueError, KeyError):
                            continue
                        if pd.isna(score):
                            continue
                    else:
                        # Require at least one non-NaN raw score among the columns.
                        scores = []
                        for c in cols:
                            try:
                                scores.append(self._compute_raw_flow_score(sid, self._level_from_score_column(c)))
                            except (ValueError, KeyError):
                                scores.append(np.nan)
                        if pd.isna(scores).all():
                            continue
                elif pd.isna(row[cols].values[0]).all():
                    continue
                valid_ids.append(sid)

        return valid_ids

    def _load_full_signal(self, real_id: int) -> pd.DataFrame:
        """Load the full, uncropped biosignal DataFrame for a real subject.

        The signal is cached to disk if ``cache_dir`` was provided. The returned
        DataFrame contains all columns present in the raw CSV (including ECG, EDA,
        TIMESTAMP, etc.).
        """
        cache_file = None
        if self.cache_dir:
            cache_file = self.cache_dir / f"SUB{real_id}-BioSigs.csv"

        if cache_file and cache_file.exists():
            signal = pd.read_csv(cache_file)
        else:
            with zipfile.ZipFile(self.zip_path, "r") as zf:
                with zf.open(self.available_files[real_id]) as f:
                    signal = pd.read_csv(f)
            if cache_file:
                signal.to_csv(cache_file, index=False)

        # Ensure TIMESTAMP is float
        signal["TIMESTAMP"] = pd.to_numeric(signal["TIMESTAMP"], errors="coerce")
        signal = signal.dropna(subset=["TIMESTAMP"]).reset_index(drop=True)
        return signal

    # ------------------------------------------------------------------
    # Signal loading
    # ------------------------------------------------------------------
    def load_subject(self, subject_id: int) -> Dict:
        """Load one subject's (or pseudo-subject's) biosignals and label.

        Returns
        -------
        dict with keys:
            subject_id: int
            signal: pd.DataFrame with columns TIMESTAMP, ECG, (EDA)
            label: float  -- GEQ Flow score for the configured level
            sampling_rate: float
        """
        level_mode = getattr(self.config, "treat_levels_as_subjects", False)
        if level_mode:
            real_id, level = self._pseudo_to_real(subject_id)
        else:
            real_id, level = subject_id, None

        if real_id not in self.available_files:
            raise ValueError(f"Subject {real_id} not found in biosig archive")

        signal = self._load_full_signal(real_id)

        # In level-as-subjects mode, crop to the corresponding level segment.
        if level_mode:
            signal = self._crop_to_level(signal, real_id, level)

        # Select requested modalities
        cols = ["TIMESTAMP"] + [m for m in self.config.modalities if m in signal.columns]
        signal = signal[cols]

        row = self.metadata[self.metadata["ID"] == real_id]
        label = self._get_label(row, level=level)

        return {
            "subject_id": subject_id,
            "signal": signal,
            "label": label,
            "sampling_rate": self.sample_rate,
        }

    def load_baseline_signal(
        self,
        subject_id: int,
        max_length_s: Optional[float] = None,
    ) -> pd.DataFrame:
        """Return the resting/baseline segment for a subject.

        If procedure files are available and contain BASELINE START/END, the
        segment between those timestamps is returned (optionally clipped to the
        first ``max_length_s`` seconds). If no baseline times are known, the first
        ``max_length_s`` seconds of the full recording are used as a fallback.

        Parameters
        ----------
        subject_id: int
            Real or pseudo subject ID. Pseudo-IDs are decoded to the underlying
            real subject.
        max_length_s: Optional[float]
            Maximum duration in seconds. If None, the entire available baseline
            segment is returned.

        Returns
        -------
        pd.DataFrame with columns TIMESTAMP + requested modalities.
        """
        level_mode = getattr(self.config, "treat_levels_as_subjects", False)
        real_id, _ = self._pseudo_to_real(subject_id) if level_mode else (subject_id, None)

        if real_id not in self.available_files:
            raise ValueError(f"Subject {real_id} not found in biosig archive")

        signal = self._load_full_signal(real_id)
        ts = signal["TIMESTAMP"].to_numpy(dtype=float)
        t_min, t_max = float(ts.min()), float(ts.max())

        baseline_times = self._baseline_times.get(real_id)
        if baseline_times is not None:
            start, end = baseline_times
            start = max(start, t_min)
            end = min(end, t_max)
        else:
            start, end = t_min, t_max

        if max_length_s is not None and (end - start) > max_length_s:
            end = start + max_length_s

        if end <= start:
            return signal.iloc[0:0].copy()

        mask = (ts >= start) & (ts < end)
        if not mask.any():
            return signal.iloc[0:0].copy()

        signal = signal.loc[mask].copy()
        cols = ["TIMESTAMP"] + [m for m in self.config.modalities if m in signal.columns]
        return signal[cols]

    def _crop_to_level(self, signal: pd.DataFrame, real_id: int, level: int) -> pd.DataFrame:
        """Return the signal segment corresponding to GEQ level ``level``.

        Strategy
        --------
        1. Look up GAME START / GAME END from the procedure file.
        2. Split GAME START -> GAME END into N equal-duration chunks, where N is
           the number of score columns (levels).
        3. Return the chunk for ``level``.

        If no procedure times are available, fall back to splitting the whole
        available recording into N equal parts.
        """
        ts = signal["TIMESTAMP"].to_numpy(dtype=float)
        t_min, t_max = float(ts.min()), float(ts.max())

        game_times = self._game_times.get(real_id)
        if game_times is not None:
            start, end = game_times
            # Clip to actual recorded range
            start = max(start, t_min)
            end = min(end, t_max)
        else:
            start, end = t_min, t_max

        if end <= start:
            return signal.iloc[0:0].copy()

        n_levels = self._level_count()
        duration = end - start
        level_start = start + level * (duration / n_levels)
        level_end = start + (level + 1) * (duration / n_levels)

        mask = (ts >= level_start) & (ts < level_end)
        if not mask.any():
            return signal.iloc[0:0].copy()
        return signal.loc[mask].copy()
