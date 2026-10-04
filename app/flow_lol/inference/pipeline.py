"""End-to-end inference pipeline: ECG window → features → ensemble vote."""

from __future__ import annotations

import logging
from typing import Callable, Dict, List, Optional

from flow_lol.config.settings import AppSettings
from flow_lol.inference.ensemble import ClassifierEnsemble
from flow_lol.inference.feature_extract import FeaturePipeline
from flow_lol.sensors.buffer import ECGBuffer, ECGSample

logger = logging.getLogger(__name__)


class Prediction:
    """One ensemble prediction for one sensor window."""

    def __init__(
        self,
        sensor_name: str,
        start_timestamp: float,
        end_timestamp: float,
        n_samples: int,
        votes: Dict[str, int],
        probabilities: Dict[str, Optional[float]],
        ensemble_label: int,
        n_votes: int,
        n_for_majority: int,
        features: Dict[str, float],
    ) -> None:
        self.sensor_name = sensor_name
        self.start_timestamp = start_timestamp
        self.end_timestamp = end_timestamp
        self.n_samples = n_samples
        self.votes = votes
        self.probabilities = probabilities
        self.ensemble_label = ensemble_label
        self.n_votes = n_votes
        self.n_for_majority = n_for_majority
        self.features = features

    def to_dict(self) -> Dict[str, object]:
        return {
            "sensor_name": self.sensor_name,
            "start_timestamp": self.start_timestamp,
            "end_timestamp": self.end_timestamp,
            "n_samples": self.n_samples,
            "votes": self.votes,
            "probabilities": self.probabilities,
            "ensemble_label": self.ensemble_label,
            "n_votes": self.n_votes,
            "n_for_majority": self.n_for_majority,
            "features": self.features,
        }


class InferencePipeline:
    """Combine feature extraction and ensemble voting for live sensor streams."""

    def __init__(
        self,
        settings: AppSettings,
        on_prediction: Optional[Callable[[Prediction], None]] = None,
    ) -> None:
        self.settings = settings
        self.on_prediction = on_prediction
        self.ensemble = ClassifierEnsemble(enabled_names=self._enabled_model_names())
        self.feature_pipelines: Dict[str, FeaturePipeline] = {}

    def _enabled_model_names(self) -> tuple[str, ...]:
        names = []
        if self.settings.use_biraffe2_svm:
            names.append("biraffe2_svm")
        if self.settings.use_biraffe2_knn:
            names.append("biraffe2_knn")
        if self.settings.use_biraffe2_rf:
            names.append("biraffe2_rf")
        if self.settings.use_irshad_rf:
            names.append("irshad_rf")
        if self.settings.use_biraffe2_mlp:
            names.append("biraffe2_mlp")
        return tuple(names)

    def load_models(self) -> None:
        self.ensemble.load()
        if not self.ensemble.is_ready():
            logger.warning("Inference pipeline not ready: some model bundles are missing")

    def register_sensor(self, sensor_name: str, baseline_samples: Optional[List[ECGSample]] = None) -> None:
        """Create a FeaturePipeline for a sensor stream.

        If ``baseline_samples`` is provided, BIRAFFE2 baseline-corrected models
        receive change-score-corrected features; Irshad models receive raw
        features because they were trained without baseline correction.
        """
        self.feature_pipelines[sensor_name] = FeaturePipeline(
            sampling_rate=self.settings.sampling_rate,
            baseline_samples=baseline_samples,
        )

    def process_window(
        self,
        sensor_name: str,
        start_timestamp: float,
        samples: List[ECGSample],
    ) -> Optional[Prediction]:
        """Extract features and run ensemble on one completed window."""
        if sensor_name not in self.feature_pipelines:
            self.register_sensor(sensor_name)

        pipeline = self.feature_pipelines[sensor_name]
        features = pipeline.process_window(samples)

        # The ensemble expects a dict; it aligns per-bundle internally.
        result = self.ensemble.predict(features)
        if "error" in result:
            logger.warning("Ensemble prediction failed: %s", result["error"])
            return None

        end_timestamp = samples[-1].timestamp if samples else start_timestamp
        prediction = Prediction(
            sensor_name=sensor_name,
            start_timestamp=start_timestamp,
            end_timestamp=end_timestamp,
            n_samples=len(samples),
            votes=result["votes"],
            probabilities=result["probabilities"],
            ensemble_label=result["ensemble_label"],
            n_votes=result["n_votes"],
            n_for_majority=result["n_for_majority"],
            features=features,
        )

        if self.on_prediction:
            self.on_prediction(prediction)
        return prediction

    def is_ready(self) -> bool:
        return self.ensemble.is_ready()
