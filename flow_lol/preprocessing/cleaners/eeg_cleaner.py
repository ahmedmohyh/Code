"""EEG preprocessing adapter (MNE-Python)."""
import numpy as np


def clean_eeg(data: np.ndarray, sampling_rate: float, channels: list) -> np.ndarray:
    """Run minimal EEG preprocessing.

    Parameters
    ----------
    data : np.ndarray, shape (n_channels, n_samples)
    sampling_rate : float
    channels : list of channel names

    Returns
    -------
    cleaned : np.ndarray, same shape as input
    """
    import mne
    info = mne.create_info(ch_names=channels, sfreq=sampling_rate, ch_types="eeg")
    raw = mne.io.RawArray(data, info)
    raw.filter(l_freq=1.0, h_freq=45.0, verbose=False)
    # ICA-based artifact removal can be added here once data quality is verified.
    return raw.get_data()
