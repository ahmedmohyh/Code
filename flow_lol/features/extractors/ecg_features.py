"""ECG / HRV feature extraction adapters."""
import warnings
from typing import Dict, List

import numpy as np

# Suppress NeuroKit2 DFA_alpha2 warning that floods output for short windows.
warnings.filterwarnings("ignore", message=".*DFA_alpha2.*")


def extract_ecg_features(signal: np.ndarray, sampling_rate: float, package: str = "neurokit2",
                         selected_time: List[str] = None,
                         selected_frequency: List[str] = None,
                         selected_nonlinear: List[str] = None) -> Dict[str, float]:
    """Extract HRV features from a cleaned ECG window.

    Parameters
    ----------
    signal : cleaned ECG window (1-D numpy array)
    sampling_rate : float
    package : {"neurokit2", "heartpy"}
    selected_* : feature names to compute (None = compute all available)

    Returns
    -------
    dict of feature_name -> value
    """
    if package == "neurokit2":
        return _extract_neurokit2(signal, sampling_rate, selected_time, selected_frequency, selected_nonlinear)
    if package == "heartpy":
        return _extract_heartpy(signal, sampling_rate, selected_time)
    raise ValueError(f"Unknown ECG feature package: {package}")


def _extract_neurokit2(signal, sampling_rate, selected_time, selected_frequency, selected_nonlinear):
    import neurokit2 as nk
    info, _ = nk.ecg_process(signal, sampling_rate=sampling_rate)
    peaks = np.where(info["ECG_R_Peaks"] == 1)[0]
    rri_ms = np.diff(peaks) / sampling_rate * 1000.0

    feats = {}

    # Time-domain features
    if rri_ms.size > 1:
        hr = 60.0 / (np.diff(peaks) / sampling_rate)
        feats["hr_mean"] = float(np.nanmean(hr))
        feats["SDNN"] = float(np.nanstd(rri_ms, ddof=1))
        feats["RMSSD"] = float(np.sqrt(np.nanmean(np.diff(rri_ms) ** 2)))
        feats["pNN50"] = float(np.mean(np.abs(np.diff(rri_ms)) > 50.0) * 100.0)

    # Frequency-domain features (use nk.hrv_frequency if enough R-peaks)
    if rri_ms.size >= 30:
        try:
            hrv = nk.hrv_frequency(info, sampling_rate=sampling_rate, show=False)
            feats["VLF"] = float(_series_value(hrv, "HRV_VLF"))
            feats["LF"] = float(_series_value(hrv, "HRV_LF"))
            feats["HF"] = float(_series_value(hrv, "HRV_HF"))
            feats["LF_HF"] = float(_series_value(hrv, "HRV_LFHF"))
            feats["TP"] = float(_series_value(hrv, "HRV_TP"))
        except Exception:
            pass

    # Nonlinear features
    if rri_ms.size > 3:
        try:
            hrv_non = nk.hrv_nonlinear(info, sampling_rate=sampling_rate, show=False)
            feats["sample_entropy"] = float(_series_value(hrv_non, "HRV_SampEn"))
            feats["DFA_alpha1"] = float(_series_value(hrv_non, "HRV_DFA_alpha1"))
            feats["DFA_alpha2"] = float(_series_value(hrv_non, "HRV_DFA_alpha2"))
        except Exception:
            pass

    return _filter_features(feats, selected_time, selected_frequency, selected_nonlinear)


def _extract_heartpy(signal, sampling_rate, selected_time):
    import heartpy as hp
    wd, m = hp.process(signal, sample_rate=sampling_rate)
    feats = {
        "hr_mean": float(m.get("bpm", np.nan)),
        "SDNN": float(m.get("sdnn", np.nan)),
        "RMSSD": float(m.get("rmssd", np.nan)),
        "pNN50": float(m.get("pnn50", np.nan)),
    }
    return _filter_features(feats, selected_time, None, None)


def _series_value(series_or_scalar, key):
    """Safely extract a scalar from a pandas Series or a scalar value."""
    import pandas as pd
    val = series_or_scalar.get(key, np.nan) if hasattr(series_or_scalar, "get") else np.nan
    if isinstance(val, pd.Series):
        if len(val) == 0:
            return np.nan
        val = val.iloc[0]
    return val


def _filter_features(feats: Dict, selected_time, selected_frequency, selected_nonlinear) -> Dict:
    selected = []
    if selected_time:
        selected.extend(selected_time)
    if selected_frequency:
        selected.extend(selected_frequency)
    if selected_nonlinear:
        selected.extend(selected_nonlinear)
    if not selected:
        return feats
    return {k: feats.get(k, np.nan) for k in selected if k in feats or True}
