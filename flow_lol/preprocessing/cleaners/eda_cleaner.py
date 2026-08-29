"""EDA cleaning adapters for multiple packages."""
import numpy as np


def clean_eda(signal: np.ndarray, sampling_rate: float, package: str = "neurokit2") -> dict:
    """Clean EDA and return tonic/phasic decomposition.

    Returns
    -------
    dict with keys "cleaned", "tonic", "phasic".
    """
    if package == "neurokit2":
        import neurokit2 as nk
        signals, info = nk.eda_process(signal, sampling_rate=sampling_rate)
        return {
            "cleaned": np.asarray(signals["EDA_Clean"]),
            "tonic": np.asarray(signals["EDA_Tonic"]),
            "phasic": np.asarray(signals["EDA_Phasic"]),
        }
    if package == "biosppy":
        import biosppy.signals.eda as eda
        out = eda.eda(signal=signal, sampling_rate=sampling_rate, show=False)
        return {
            "cleaned": np.asarray(out["filtered"]),
            "tonic": np.asarray(out["tonic"]),
            "phasic": np.asarray(out["phasic"]),
        }
    raise ValueError(f"Unknown EDA cleaning package: {package}")
