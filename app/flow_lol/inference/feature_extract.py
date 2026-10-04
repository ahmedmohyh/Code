"""Streaming ECG feature extraction for the app runtime.

Extracts the same classical HRV features used by the exported models:

  hr_mean, SDNN, RMSSD, pNN50, VLF, LF, HF, LF_HF, TP,
  sample_entropy, DFA_alpha1, DFA_alpha2

This module uses ``neurokit2`` directly so the deployed app does not need to
ship the research ``flow_lol`` package.
"""

from __future__ import annotations

import logging
import warnings
from typing import Dict, List, Optional

import neurokit2 as nk
import numpy as np

from flow_lol.sensors.buffer import ECGSample

logger = logging.getLogger(__name__)

# Suppress the DFA_alpha2 warning that floods output for short windows.
warnings.filterwarnings("ignore", message=".*DFA_alpha2.*")


# Feature names expected by the exported model bundles.
FEATURE_ORDER = [
    "hr_mean",
    "SDNN",
    "RMSSD",
    "pNN50",
    "VLF",
    "LF",
    "HF",
    "LF_HF",
    "TP",
    "sample_entropy",
    "DFA_alpha1",
    "DFA_alpha2",
]


def _series_value(series_or_scalar, key: str) -> float:
    """Safely extract a scalar from a pandas Series or a scalar value."""
    import pandas as pd

    if hasattr(series_or_scalar, "get"):
        val = series_or_scalar.get(key, np.nan)
    else:
        val = np.nan
    if isinstance(val, pd.Series):
        if len(val) == 0:
            return float(np.nan)
        val = val.iloc[0]
    return float(val)


def _ecg_process(ecg_signal: np.ndarray, sampling_rate: float) -> tuple[np.ndarray, np.ndarray]:
    """Run neurokit2 ECG processing and return (r_peaks_array, rri_ms)."""
    info, _ = nk.ecg_process(ecg_signal, sampling_rate=sampling_rate)
    peaks = np.where(info["ECG_R_Peaks"] == 1)[0]
    rri_ms = np.diff(peaks) / sampling_rate * 1000.0
    return peaks, rri_ms


def _time_features(peaks: np.ndarray, rri_ms: np.ndarray, sampling_rate: float) -> Dict[str, float]:
    """Compute time-domain HRV features."""
    feats: Dict[str, float] = {}
    if rri_ms.size > 1:
        hr = 60.0 / (np.diff(peaks) / sampling_rate)
        feats["hr_mean"] = float(np.nanmean(hr))
        feats["SDNN"] = float(np.nanstd(rri_ms, ddof=1))
        feats["RMSSD"] = float(np.sqrt(np.nanmean(np.diff(rri_ms) ** 2)))
        feats["pNN50"] = float(np.mean(np.abs(np.diff(rri_ms)) > 50.0) * 100.0)
    return feats


def _frequency_features(info: dict, sampling_rate: float) -> Dict[str, float]:
    """Compute frequency-domain HRV features."""
    feats: Dict[str, float] = {}
    try:
        hrv = nk.hrv_frequency(info, sampling_rate=sampling_rate, show=False)
        feats["VLF"] = _series_value(hrv, "HRV_VLF")
        feats["LF"] = _series_value(hrv, "HRV_LF")
        feats["HF"] = _series_value(hrv, "HRV_HF")
        feats["LF_HF"] = _series_value(hrv, "HRV_LFHF")
        feats["TP"] = _series_value(hrv, "HRV_TP")
    except Exception as exc:
        logger.debug("Frequency features failed: %s", exc)
    return feats


def _nonlinear_features(rri_ms: np.ndarray) -> Dict[str, float]:
    """Compute nonlinear HRV features."""
    feats: Dict[str, float] = {}
    if rri_ms.size < 30:
        return feats

    try:
        sampen, _ = nk.entropy_sample(rri_ms)
        feats["sample_entropy"] = float(sampen)
    except Exception as exc:
        logger.debug("Sample entropy failed: %s", exc)

    try:
        dfa_alpha1, _ = nk.fractal_dfa(
            rri_ms, windows=list(range(4, min(17, rri_ms.size // 2)))
        )
        feats["DFA_alpha1"] = float(dfa_alpha1)
    except Exception as exc:
        logger.debug("DFA_alpha1 failed: %s", exc)

    if rri_ms.size >= 50:
        try:
            max_win = min(65, rri_ms.size // 2)
            windows2 = list(range(16, max_win))
            if len(windows2) >= 4:
                dfa_alpha2, _ = nk.fractal_dfa(rri_ms, windows=windows2)
                feats["DFA_alpha2"] = float(dfa_alpha2)
        except Exception as exc:
            logger.debug("DFA_alpha2 failed: %s", exc)

    return feats


def extract_features(
    ecg_signal: np.ndarray,
    sampling_rate: float,
    selected_features: Optional[List[str]] = None,
) -> Dict[str, float]:
    """Extract classical ECG/HRV features from a cleaned ECG signal window.

    Parameters
    ----------
    ecg_signal : np.ndarray
        Cleaned ECG samples for one window.
    sampling_rate : float
        ECG sampling rate in Hz (e.g. 130 for Polar H10).
    selected_features : list[str] | None
        If provided, only these features are returned (missing ones are NaN).

    Returns
    -------
    dict[str, float]
        Feature name -> value. Values may be NaN if the window is too short or
        a specific feature cannot be computed.
    """
    features: Dict[str, float] = {}
    try:
        peaks, rri_ms = _ecg_process(ecg_signal, sampling_rate)
    except Exception as exc:
        logger.warning("ECG processing failed: %s", exc)
        return {name: float(np.nan) for name in (selected_features or FEATURE_ORDER)}

    features.update(_time_features(peaks, rri_ms, sampling_rate))
    # neurokit2 ecg_process returns the info dict that hrv_frequency expects.
    info = {"ECG_R_Peaks": np.zeros(len(ecg_signal), dtype=int)}
    info["ECG_R_Peaks"][peaks] = 1
    features.update(_frequency_features(info, sampling_rate))
    features.update(_nonlinear_features(rri_ms))

    if selected_features:
        return {name: float(features.get(name, np.nan)) for name in selected_features}
    return {name: float(features.get(name, np.nan)) for name in FEATURE_ORDER}


def samples_to_signal(samples: List[ECGSample]) -> np.ndarray:
    """Convert a list of ECGSample objects to a numpy array of amplitudes."""
    return np.array([s.value for s in samples], dtype=float)


def apply_baseline_correction(
    window_features: Dict[str, float],
    baseline_features: Dict[str, float],
    selected_features: Optional[List[str]] = None,
) -> Dict[str, float]:
    """Apply change-score baseline correction: X - baseline.

    This mirrors the BIRAFFE2 training setup so that the BIRAFFE2 models receive
    baseline-corrected features at runtime. The Irshad models do not use baseline
    correction.
    """
    names = selected_features or FEATURE_ORDER
    corrected: Dict[str, float] = {}
    for name in names:
        value = window_features.get(name, np.nan)
        base = baseline_features.get(name, np.nan)
        if np.isnan(value) or np.isnan(base):
            corrected[name] = float(np.nan)
        else:
            corrected[name] = float(value - base)
    return corrected


def align_features(
    features: Dict[str, float],
    feature_names: List[str],
) -> List[float]:
    """Return a list of feature values in the order requested by a model bundle."""
    return [float(features.get(name, np.nan)) for name in feature_names]


class FeaturePipeline:
    """High-level helper: turn ECG windows into feature dicts."""

    def __init__(
        self,
        sampling_rate: float,
        baseline_samples: Optional[List[ECGSample]] = None,
        selected_features: Optional[List[str]] = None,
    ) -> None:
        self.sampling_rate = sampling_rate
        self.baseline_features: Optional[Dict[str, float]] = None
        if baseline_samples:
            baseline_signal = samples_to_signal(baseline_samples)
            self.baseline_features = extract_features(
                baseline_signal, sampling_rate, selected_features=selected_features
            )
        self.selected_features = selected_features or FEATURE_ORDER

    def process_window(self, samples: List[ECGSample]) -> Dict[str, float]:
        """Extract features from one window; optionally apply baseline correction."""
        signal = samples_to_signal(samples)
        features = extract_features(signal, self.sampling_rate, self.selected_features)
        if self.baseline_features is not None:
            features = apply_baseline_correction(
                features, self.baseline_features, self.selected_features
            )
        return features

    def process_window_for_bundle(
        self, samples: List[ECGSample], feature_names: List[str]
    ) -> List[float]:
        """Extract features and align them to a specific model bundle."""
        features = self.process_window(samples)
        return align_features(features, feature_names)
