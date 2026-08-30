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
    """

    def __init__(self, config: DatasetConfig):
        self.config = config
        self.zip_path = Path(config.path)
        self.metadata_path = Path(config.metadata_path)
        self.sample_rate = 1000.0
        self.available_files: Dict[int, str] = {}
        self.metadata: Optional[pd.DataFrame] = None
        self._scan_archive()
        self._load_metadata()

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

    def list_subjects(self) -> List[int]:
        """Return subject IDs that have both biosignals and a valid label."""
        valid_ids = []
        for sid in sorted(self.available_files.keys()):
            row = self.metadata[self.metadata["ID"] == sid]
            if row.empty:
                continue
            if pd.isna(row[self.config.score_column].values[0]):
                continue
            valid_ids.append(sid)
        return valid_ids

    def load_subject(self, subject_id: int) -> Dict:
        """Load one subject's biosignals and label.

        Returns
        -------
        dict with keys:
            subject_id: int
            signal: pd.DataFrame with columns TIMESTAMP, ECG, (EDA)
            label: float  -- GEQ Flow score for the configured level
            sampling_rate: float
        """
        if subject_id not in self.available_files:
            raise ValueError(f"Subject {subject_id} not found in biosig archive")

        with zipfile.ZipFile(self.zip_path, "r") as zf:
            with zf.open(self.available_files[subject_id]) as f:
                signal = pd.read_csv(f)

        # Ensure TIMESTAMP is float
        signal["TIMESTAMP"] = pd.to_numeric(signal["TIMESTAMP"], errors="coerce")
        signal = signal.dropna(subset=["TIMESTAMP"]).reset_index(drop=True)

        # Select requested modalities
        cols = ["TIMESTAMP"] + [m for m in self.config.modalities if m in signal.columns]
        signal = signal[cols]

        row = self.metadata[self.metadata["ID"] == subject_id]
        label = float(row[self.config.score_column].values[0])

        return {
            "subject_id": subject_id,
            "signal": signal,
            "label": label,
            "sampling_rate": self.sample_rate,
        }
