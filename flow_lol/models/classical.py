"""Classical machine-learning classifiers."""
from typing import Any, Dict, List

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.neighbors import KNeighborsClassifier
from sklearn.svm import SVC
from sklearn.pipeline import Pipeline


def build_classifier(name: str, random_state: int = 42, **kwargs) -> Any:
    """Build a classical classifier by name."""
    if name == "RandomForest":
        return RandomForestClassifier(
            n_estimators=kwargs.get("n_estimators", 200),
            max_depth=kwargs.get("max_depth", None),
            random_state=random_state,
            n_jobs=-1,
            class_weight="balanced",
        )
    if name == "SVM":
        return SVC(
            C=kwargs.get("C", 1.0),
            kernel=kwargs.get("kernel", "rbf"),
            probability=True,
            class_weight="balanced",
            random_state=random_state,
        )
    if name == "kNN":
        return KNeighborsClassifier(
            n_neighbors=kwargs.get("n_neighbors", 5),
            n_jobs=-1,
        )
    try:
        import xgboost as xgb
        if name == "XGBoost":
            return xgb.XGBClassifier(
                n_estimators=kwargs.get("n_estimators", 200),
                max_depth=kwargs.get("max_depth", 4),
                learning_rate=kwargs.get("learning_rate", 0.05),
                use_label_encoder=False,
                eval_metric="logloss",
                random_state=random_state,
                n_jobs=-1,
            )
    except ImportError:
        pass
    raise ValueError(f"Unknown classifier: {name}")


def list_available_classifiers() -> List[str]:
    out = ["RandomForest", "SVM", "kNN"]
    try:
        import xgboost  # noqa: F401
        out.append("XGBoost")
    except ImportError:
        pass
    return out
