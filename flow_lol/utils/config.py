"""Configuration schema and loader."""
from dataclasses import dataclass, field
from typing import List, Optional, Union
from pathlib import Path
import yaml


@dataclass
class DatasetConfig:
    name: str = "BIRAFFE2"
    path: str = ""
    metadata_path: str = ""
    modalities: List[str] = field(default_factory=lambda: ["ECG"])
    score_column: Union[str, List[str]] = "GEQ-1-FLOW-2018"
    # If True, each level in the list score_column becomes a separate pseudo-subject.
    # Requires BIRAFFE2 procedure files (procedure_path) to locate level segments.
    treat_levels_as_subjects: bool = False
    procedure_path: str = ""
    # Raw GEQ item recomputation (Setup 03 / Setup 11).
    # If recompute_flow_from_items is True, the loader reads raw item CSVs from
    # raw_geq_dir and recomputes the Flow score per level instead of using the
    # pre-aggregated metadata column. exclude_time_distortion drops item 25.
    raw_geq_dir: str = ""
    recompute_flow_from_items: bool = False
    exclude_time_distortion: bool = False
    # When recompute_flow_from_items is true, this list selects which GEQ levels
    # (1, 2, 3, ...) are used. In normal mode the levels are averaged into one
    # label per subject. In treat_levels_as_subjects mode each level becomes a
    # separate pseudo-subject.
    raw_geq_levels: List[int] = field(default_factory=list)


@dataclass
class LabelConfig:
    method: str = "median_split"
    margin: float = 0.0
    items: str = "full_subscale"
    classes: List[str] = field(default_factory=lambda: ["low", "high"])


@dataclass
class PreprocessingConfig:
    cleaning_package: str = "neurokit2"
    z_standardise: bool = True
    per_subject_normalize: bool = False
    outlier_strategy: str = "train_only"
    baseline_correction: str = "none"
    baseline_length_s: int = 60
    baseline_from_procedure: bool = False


@dataclass
class SegmentationConfig:
    window_length_s: int = 60
    step_s: int = 30


@dataclass
class ECGFeatureConfig:
    time: List[str] = field(default_factory=lambda: ["hr_mean", "SDNN", "RMSSD", "pNN50"])
    frequency: List[str] = field(default_factory=lambda: ["VLF", "LF", "HF", "LF_HF", "TP"])
    nonlinear: List[str] = field(default_factory=lambda: ["sample_entropy", "DFA_alpha1", "DFA_alpha2"])


@dataclass
class FeaturesConfig:
    ecg: ECGFeatureConfig = field(default_factory=ECGFeatureConfig)
    package: str = "neurokit2"


@dataclass
class ModelsConfig:
    classical: List[str] = field(default_factory=lambda: ["RandomForest"])
    deep: List[str] = field(default_factory=list)


@dataclass
class ValidationConfig:
    strategy: str = "LOSO"
    permutation: bool = False
    metrics: List[str] = field(default_factory=lambda: [
        "accuracy", "f1_macro", "precision_low", "recall_low",
        "precision_high", "recall_high", "auc", "inference_ms"
    ])


@dataclass
class Config:
    experiment_name: str = "default"
    seed: int = 42
    dataset: DatasetConfig = field(default_factory=DatasetConfig)
    label: LabelConfig = field(default_factory=LabelConfig)
    preprocessing: PreprocessingConfig = field(default_factory=PreprocessingConfig)
    segmentation: SegmentationConfig = field(default_factory=SegmentationConfig)
    features: FeaturesConfig = field(default_factory=FeaturesConfig)
    models: ModelsConfig = field(default_factory=ModelsConfig)
    validation: ValidationConfig = field(default_factory=ValidationConfig)


def load_config(path: str) -> Config:
    """Load YAML config into dataclass."""
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    def _build(cfg_class, data):
        if data is None:
            return cfg_class()
        # Only pass keys that exist in dataclass fields
        fields = {f.name for f in cfg_class.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in fields}
        # Recursively build nested dataclasses
        for f_name, f_def in cfg_class.__dataclass_fields__.items():
            if f_name in filtered and hasattr(f_def.type, "__dataclass_fields__"):
                filtered[f_name] = _build(f_def.type, filtered[f_name])
        return cfg_class(**filtered)

    return _build(Config, raw)


def save_config(config: Config, path: str) -> None:
    """Save dataclass config to YAML."""
    def to_dict(obj):
        if hasattr(obj, "__dataclass_fields__"):
            return {k: to_dict(v) for k, v in obj.__dict__.items()}
        return obj

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(to_dict(config), f, default_flow_style=False, sort_keys=False)
