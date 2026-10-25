"""Persistent user settings."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from flow_lol.utils.paths import config_file


@dataclass
class AppSettings:
    """All user-editable settings for the Flow-LoL app."""

    # Sensor
    use_h10: bool = True
    h10_address: str = ""  # optional paired MAC address; empty = scan

    # Paths
    ecg_save_path: str = ""
    webcam_save_path: str = ""
    snapshot_save_path: str = ""
    logs_save_path: str = ""
    db_path: str = ""
    replay_save_path: str = ""

    # Webcam
    webcam_enabled: bool = True

    # Riot / game detection
    riot_api_enabled: bool = False
    riot_api_key: str = ""
    auto_detect_game: bool = True

    # Classifiers
    use_biraffe2_svm: bool = True
    use_biraffe2_knn: bool = True
    use_biraffe2_rf: bool = True
    use_irshad_rf: bool = True
    use_biraffe2_mlp: bool = True
    use_biraffe2_lr: bool = True
    use_biraffe2_xgb: bool = True
    use_biraffe2_lstm: bool = True
    use_biraffe2_cnn: bool = True
    use_irshad_lr: bool = True
    use_irshad_mlp: bool = True

    # Signal processing
    window_seconds: int = 60  # matches the model training setup
    overlap_percent: int = 50  # 30 s step for 60 s windows
    sampling_rate: int = 130  # Polar H10 ECG default

    # Interventions
    notification_muting_enabled: bool = False
    adaptive_cues_enabled: bool = False
    screen_edge_status_enabled: bool = False
    screen_edge_status_monitor: int = -1  # -1 = primary monitor

    def __post_init__(self) -> None:
        from flow_lol.utils.paths import default_data_dir

        data = default_data_dir()
        if not self.ecg_save_path:
            self.ecg_save_path = str(data / "ecg")
        if not self.webcam_save_path:
            self.webcam_save_path = str(data / "webcam")
        if not self.snapshot_save_path:
            self.snapshot_save_path = str(Path(self.webcam_save_path) / "snapshots")
        if not self.logs_save_path:
            self.logs_save_path = str(data / "logs")
        if not self.db_path:
            self.db_path = str(data / "flow_lol.db")
        if not self.replay_save_path:
            user_docs = Path.home() / "Documents" / "League of Legends" / "Replays"
            self.replay_save_path = str(user_docs)

    @classmethod
    def load(cls) -> "AppSettings":
        path = config_file()
        if not path.exists():
            return cls()
        try:
            with path.open("r", encoding="utf-8") as f:
                data: dict[str, Any] = json.load(f)
            # Only accept known fields
            known = {k for k in cls.__dataclass_fields__}
            filtered = {k: v for k, v in data.items() if k in known}
            return cls(**filtered)
        except Exception:
            return cls()

    def save(self) -> None:
        path = config_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(asdict(self), f, indent=2, ensure_ascii=False)

    def update(self, **kwargs: Any) -> None:
        for key, value in kwargs.items():
            if key in self.__dataclass_fields__:
                setattr(self, key, value)
