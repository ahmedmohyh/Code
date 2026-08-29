"""EDA feature extraction."""
import numpy as np


def extract_eda_features(tonic: np.ndarray, phasic: np.ndarray, sampling_rate: float) -> dict:
    """Compute basic EDA features from tonic and phasic components."""
    feats = {}
    feats["SCL_mean"] = float(np.nanmean(tonic))
    feats["SCL_std"] = float(np.nanstd(tonic))
    feats["phasic_max"] = float(np.nanmax(phasic))
    feats["phasic_sum"] = float(np.nansum(phasic))

    # Simple SCR detection: local maxima above a threshold
    from scipy.signal import find_peaks
    peaks, _ = find_peaks(phasic, height=0.01 * np.nanmax(phasic), distance=int(1.0 * sampling_rate))
    feats["SCR_count"] = float(len(peaks))
    feats["SCR_rate"] = float(len(peaks) / (len(phasic) / sampling_rate / 60.0))  # per minute

    return feats
