"""Loader for the Irshad/PhySF physiological flow dataset.

The dataset is shipped as a zip archive (e.g. PhySF.zip) containing one CSV per
subject-session, named ``s<id>_<label>.csv`` where ``label`` is either ``flow`` or
``no_flow``. Each CSV contains 23 sensor channels sampled at 128 Hz:

- Empatica E4: BVP, EDA, Tmp, IBI, HR
- RespiBan: Resp, EOG, ECG, EMG
- Emotiv Epoc X EEG: EEG.AF3, EEG.F7, EEG.F3, EEG.FC5, EEG.T7, EEG.P7,
  EEG.O1, EEG.O2, EEG.P8, EEG.T8, EEG.FC6, EEG.F4, EEG.F8, EEG.AF4

Labels are binary and derived from the filename: ``flow`` = 1, ``no_flow`` = 0.
"""
import re
import zipfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


class IrshadLoader:
    """Load Irshad/PhySF data from a zip archive of per-session CSVs."""

    SAMPLE_RATE = 128.0

    MODALITY_COLUMNS = {
        "ECG": ["ECG"],
        "EDA": ["EDA"],
        "RESP": ["Resp"],
        "BVP": ["BVP"],
        "EMG": ["EMG"],
        "EOG": ["EOG"],
        "EEG": [
            "EEG.AF3", "EEG.F7", "EEG.F3", "EEG.FC5", "EEG.T7", "EEG.P7",
            "EEG.O1", "EEG.O2", "EEG.P8", "EEG.T8", "EEG.FC6", "EEG.F4",
            "EEG.F8", "EEG.AF4",
        ],
    }

    def __init__(self, zip_path: str, modalities: Optional[List[str]] = None):
        self.zip_path = Path(zip_path)
        self.modalities = [m.upper() for m in (modalities or ["ECG", "EDA", "EEG"])]
        self.sample_rate = self.SAMPLE_RATE
        self.available_files: Dict[int, Tuple[str, int]] = {}  # sid -> (filename, binary label)
        if not self.zip_path.exists():
            raise FileNotFoundError(f"PhySF zip not found: {self.zip_path}")
        self._scan_archive()

    def _scan_archive(self) -> None:
        pattern = re.compile(r"[Ss](\d+)_(flow|no_flow)\.csv", re.IGNORECASE)
        with zipfile.ZipFile(self.zip_path, "r") as zf:
            for name in zf.namelist():
                m = pattern.search(name)
                if not m:
                    continue
                sid = int(m.group(1))
                label = 1 if m.group(2).lower() == "flow" else 0
                # If a subject has multiple files, keep the first encountered.
                # Future extension: aggregate or select by configuration.
                if sid not in self.available_files:
                    self.available_files[sid] = (name, label)

    def list_subjects(self) -> List[int]:
        return sorted(self.available_files.keys())

    def get_label(self, subject_id: int) -> int:
        if subject_id not in self.available_files:
            raise ValueError(f"Subject {subject_id} not found")
        return self.available_files[subject_id][1]

    def _read_csv(self, filename: str) -> pd.DataFrame:
        with zipfile.ZipFile(self.zip_path, "r") as zf:
            with zf.open(filename) as f:
                df = pd.read_csv(f)
        # Drop unnamed index column if present
        if "Unnamed: 0" in df.columns:
            df = df.drop(columns=["Unnamed: 0"])
        return df

    def load_subject(self, subject_id: int) -> Dict:
        """Load one subject's biosignals and binary label.

        Returns
        -------
        dict with keys:
            subject_id: int
            signal: pd.DataFrame with columns TIMESTAMP + requested modality columns
            label: int (1 = flow, 0 = no_flow)
            sampling_rate: float
        """
        if subject_id not in self.available_files:
            raise ValueError(f"Subject {subject_id} not found")

        filename, label = self.available_files[subject_id]
        df = self._read_csv(filename)

        # Build synthetic TIMESTAMP column in seconds
        n_rows = len(df)
        df = df.copy()
        df.insert(0, "TIMESTAMP", np.arange(n_rows) / self.SAMPLE_RATE)

        # Select requested modality columns that exist in the file
        selected = ["TIMESTAMP"]
        for mod in self.modalities:
            cols = self.MODALITY_COLUMNS.get(mod, [])
            for c in cols:
                if c in df.columns:
                    selected.append(c)

        signal = df[selected].copy()
        return {
            "subject_id": subject_id,
            "signal": signal,
            "label": float(label),
            "sampling_rate": self.SAMPLE_RATE,
        }
