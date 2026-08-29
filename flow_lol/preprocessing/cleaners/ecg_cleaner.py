"""ECG cleaning adapters for multiple packages."""
from typing import Tuple

import numpy as np
import pandas as pd


def clean_ecg(signal: np.ndarray, sampling_rate: float, package: str = "neurokit2") -> np.ndarray:
    """Clean ECG and return a cleaned signal vector.

    Parameters
    ----------
    signal : 1-D numpy array
    sampling_rate : float
    package : {"neurokit2", "heartpy", "biosppy"}

    Returns
    -------
    cleaned : 1-D numpy array
    """
    if package == "neurokit2":
        return _clean_neurokit2(signal, sampling_rate)
    if package == "heartpy":
        return _clean_heartpy(signal, sampling_rate)
    if package == "biosppy":
        return _clean_biosppy(signal, sampling_rate)
    raise ValueError(f"Unknown ECG cleaning package: {package}")


def _clean_neurokit2(signal: np.ndarray, sampling_rate: float) -> np.ndarray:
    import neurokit2 as nk
    cleaned = nk.ecg_clean(signal, sampling_rate=sampling_rate, method="neurokit")
    return np.asarray(cleaned)


def _clean_heartpy(signal: np.ndarray, sampling_rate: float) -> np.ndarray:
    import heartpy as hp
    # heartpy works best on shorter segments; run its filter on the whole signal
    filtered = hp.filter_signal(signal, cutoff=[0.5, 45], sample_rate=sampling_rate,
                                   filtertype="bandpass", return_top=False)
    return np.asarray(filtered)


def _clean_biosppy(signal: np.ndarray, sampling_rate: float) -> np.ndarray:
    import biosppy.signals.ecg as ecg
    out = ecg.ecg(signal=signal, sampling_rate=sampling_rate, show=False)
    return np.asarray(out["filtered"])


def detect_r_peaks(signal: np.ndarray, sampling_rate: float, package: str = "neurokit2") -> np.ndarray:
    """Return R-peak sample indices."""
    if package == "neurokit2":
        import neurokit2 as nk
        info, _ = nk.ecg_peaks(signal, sampling_rate=sampling_rate, method="neurokit")
        return np.asarray(info["ECG_R_Peaks"])
    if package == "heartpy":
        import heartpy as hp
        wd, _ = hp.process(signal, sample_rate=sampling_rate)
        return np.asarray(wd["peaklist"])
    if package == "biosppy":
        import biosppy.signals.ecg as ecg
        out = ecg.ecg(signal=signal, sampling_rate=sampling_rate, show=False)
        return np.asarray(out["rpeaks"])
    raise ValueError(f"Unknown peak detection package: {package}")
