"""Webcam-derived facial affect feature extraction."""
import numpy as np
import pandas as pd


def extract_webcam_features(face_df: pd.DataFrame, window_start_s: float, window_end_s: float,
                            timestamp_col: str = "GAME-TIMESTAMP") -> dict:
    """Compute features from a window of BIRAFFE2 Face CSV data."""
    if timestamp_col not in face_df.columns:
        return {}

    sub = face_df[(face_df[timestamp_col] >= window_start_s) & (face_df[timestamp_col] < window_end_s)]
    if sub.empty:
        return {}

    emotion_cols = [c for c in sub.columns if c in ["NEUTRAL", "HAPPINESS", "ANGER", "CONTEMPT", "DISGUST", "FEAR", "SADNESS", "SURPRISE"]]
    feats = {}
    for col in emotion_cols:
        feats[f"{col}_mean"] = float(sub[col].mean())
        feats[f"{col}_std"] = float(sub[col].std())
        feats[f"{col}_max"] = float(sub[col].max())

    # Head pose dynamics
    pose_cols = [c for c in sub.columns if "HEADPOSE" in c.upper()]
    for col in pose_cols:
        feats[f"{col}_mean"] = float(sub[col].mean())
        feats[f"{col}_range"] = float(sub[col].max() - sub[col].min())

    feats["face_observations"] = float(len(sub))
    return feats
