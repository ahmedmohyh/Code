"""Merge feature vectors from multiple modalities into a single matrix."""
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd


def features_to_matrix(feature_dicts: List[Dict[str, float]]) -> Tuple[np.ndarray, List[str]]:
    """Convert list of feature dictionaries into a 2-D numpy array.

    Returns
    -------
    X : np.ndarray, shape (n_windows, n_features)
    feature_names : list of str
    """
    if not feature_dicts:
        return np.empty((0, 0)), []

    df = pd.DataFrame(feature_dicts)
    df = df.replace([np.inf, -np.inf], np.nan)
    feature_names = list(df.columns)
    return df.to_numpy(dtype=float), feature_names


def impute_missing(X: np.ndarray, strategy: str = "median") -> np.ndarray:
    """Simple column-wise imputation."""
    if strategy == "median":
        col_medians = np.nanmedian(X, axis=0)
        inds = np.where(np.isnan(X))
        X[inds] = np.take(col_medians, inds[1])
    elif strategy == "mean":
        col_means = np.nanmean(X, axis=0)
        inds = np.where(np.isnan(X))
        X[inds] = np.take(col_means, inds[1])
    return X
