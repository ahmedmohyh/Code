"""EEG band-power feature extraction."""
import numpy as np
from scipy.signal import welch


BANDS = {
    "theta": (4, 8),
    "alpha": (8, 13),
    "beta": (13, 30),
}


def extract_eeg_features(data: np.ndarray, sampling_rate: float, channels: list) -> dict:
    """Compute per-channel and aggregate EEG features.

    Parameters
    ----------
    data : np.ndarray, shape (n_channels, n_samples)
    sampling_rate : float
    channels : list of channel names
    """
    feats = {}
    band_power = {band: [] for band in BANDS}

    for ch_idx, ch_name in enumerate(channels):
        freqs, psd = welch(data[ch_idx], fs=sampling_rate, nperseg=int(sampling_rate * 2))
        total = np.trapezoid(psd, freqs)
        for band, (lo, hi) in BANDS.items():
            idx = (freqs >= lo) & (freqs <= hi)
            power = np.trapezoid(psd[idx], freqs[idx])
            band_power[band].append(power)
            feats[f"{ch_name}_{band}_power"] = float(power)
            if total > 0:
                feats[f"{ch_name}_{band}_relative"] = float(power / total)

    # Aggregate across channels
    for band in BANDS:
        vals = np.array(band_power[band])
        feats[f"{band}_mean"] = float(np.nanmean(vals))
        feats[f"{band}_std"] = float(np.nanstd(vals))

    # Alpha/theta ratio
    theta = np.array(band_power["theta"])
    alpha = np.array(band_power["alpha"])
    beta = np.array(band_power["beta"])
    with np.errstate(divide="ignore", invalid="ignore"):
        feats["alpha_theta_ratio"] = float(np.nanmean(alpha / theta))
        feats["beta_alpha_ratio"] = float(np.nanmean(beta / alpha))

    return feats
