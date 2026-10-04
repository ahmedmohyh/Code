"""Write raw ECG samples to compressed CSV files per session."""

from __future__ import annotations

import csv
import gzip
import logging
import time
from pathlib import Path
from typing import Dict, List, Optional

from flow_lol.sensors.buffer import ECGSample

logger = logging.getLogger(__name__)


class RawECGWriter:
    """Buffer raw ECG samples per sensor and flush them to gzipped CSV on close.

    The writer keeps samples in memory during the session. For typical lab
    sessions (1–2 h at 130 Hz) this is a few 10 MB of floats; for very long
    sessions the storage strategy can be switched to periodic disk flushing.
    """

    def __init__(self, output_dir: Path, enabled: bool = True) -> None:
        self.output_dir = Path(output_dir)
        self.enabled = enabled
        self._samples: Dict[str, List[ECGSample]] = {}

    def add_samples(self, sensor_name: str, samples: List[ECGSample]) -> None:
        if not self.enabled or not samples:
            return
        self._samples.setdefault(sensor_name, []).extend(samples)

    def save(self, session_id: int) -> List[Path]:
        """Save all buffered samples and return the written file paths."""
        if not self.enabled:
            return []
        self.output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        written: List[Path] = []
        for sensor_name, samples in self._samples.items():
            if not samples:
                continue
            safe_name = sensor_name.replace("/", "_").replace("\\", "_")
            path = self.output_dir / f"session_{session_id}_{timestamp}_{safe_name}.csv.gz"
            try:
                with gzip.open(path, "wt", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow(["timestamp", "value"])
                    for s in samples:
                        writer.writerow([s.timestamp, s.value])
                written.append(path)
                logger.info("Saved %s raw ECG samples for %s to %s", len(samples), sensor_name, path)
            except Exception as exc:
                logger.error("Failed to write ECG CSV %s: %s", path, exc)
        self._samples.clear()
        return written

    def close(self, session_id: int) -> List[Path]:
        return self.save(session_id)
