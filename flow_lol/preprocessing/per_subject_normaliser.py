"""Per-subject normalisation (within-subject z-score)."""
import numpy as np
from typing import Dict


class PerSubjectNormaliser:
    """Normalise each subject's windows to zero mean and unit variance.

    This removes subject-specific baseline mean/variance before LOSO, so the
    model learns within-subject deviations rather than absolute between-subject
    differences.
    """

    def __init__(self, active: bool = True, eps: float = 1e-8):
        self.active = active
        self.eps = eps

    def transform_dict(self, X_by_subject: Dict[int, np.ndarray]) -> Dict[int, np.ndarray]:
        """Normalise each subject independently."""
        if not self.active:
            return X_by_subject

        out = {}
        for sid, X in X_by_subject.items():
            if len(X) == 0:
                out[sid] = X
                continue
            mean = np.nanmean(X, axis=0, keepdims=True)
            std = np.nanstd(X, axis=0, keepdims=True)
            std = np.where(std == 0, 1.0, std)
            out[sid] = (X - mean) / std
        return out
