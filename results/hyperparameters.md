# Hyperparameters Used in the Flow-LoL Pipeline

This document lists the machine-learning hyperparameters used for each classical
classifier. Hyperparameters are settings chosen **before** training; they are not
learned from the data.

All models are built by `flow_lol/models/classical.py` and trained inside
`flow_lol/validation/loso_cv.py`. The same hyperparameters are used for every
setup unless the config overrides them (currently none do).

## Model-specific hyperparameters

| Classifier | Hyperparameter | Value | Meaning |
|------------|----------------|-------|---------|
| **RandomForest** | `n_estimators` | 200 | Number of decision trees in the forest |
| | `max_depth` | None | Trees can grow until leaves are pure (no depth limit) |
| | `class_weight` | "balanced" | Weights classes inversely to their frequency |
| | `random_state` | 42 | Reproducible random seed |
| | `n_jobs` | -1 | Use all CPU cores |
| **SVM** | `C` | 1.0 | Regularisation strength (smaller = stronger regularisation) |
| | `kernel` | "rbf" | Radial basis function kernel |
| | `probability` | True | Enables probability estimates for AUC |
| | `class_weight` | "balanced" | Weights classes inversely to their frequency |
| | `random_state` | 42 | Reproducible random seed |
| **kNN** | `n_neighbors` | 5 | Number of nearest neighbours used for voting |
| | `n_jobs` | -1 | Use all CPU cores |
| **LogisticRegression** | `C` | 1.0 | Inverse regularisation strength |
| | `max_iter` | 1000 | Maximum optimisation iterations |
| | `class_weight` | "balanced" | Weights classes inversely to their frequency |
| | `random_state` | 42 | Reproducible random seed |
| | `n_jobs` | -1 | Use all CPU cores |
| **XGBoost** | `n_estimators` | 200 | Number of boosting rounds |
| | `max_depth` | 4 | Maximum depth of each tree |
| | `learning_rate` | 0.05 | Step size for each boosting update |
| | `eval_metric` | "logloss" | Loss used during training |
| | `use_label_encoder` | False | Disabled to avoid XGBoost warning |
| | `random_state` | 42 | Reproducible random seed |
| | `n_jobs` | -1 | Use all CPU cores |

## Notes

- We use **fixed hyperparameters**, not a search grid. This keeps the comparison
  fair across setups, but it means we do not tune per setup.
- `class_weight="balanced"` is used for all models that support it to mitigate
  the slight class imbalance in the label columns.
- No deep-learning model is currently used in the main ablation runs. Setup 10
  includes an LSTM, but the classical results reported to the supervisor use the
  table above.

## What could be improved

For the final thesis, the supervisor may ask for a **hyperparameter search**
(e.g. grid search or randomized search). This would try combinations such as:

- RandomForest: `n_estimators` ∈ {100, 200, 500}, `max_depth` ∈ {None, 10, 20}
- SVM: `C` ∈ {0.1, 1, 10}, `kernel` ∈ {"linear", "rbf"}
- kNN: `n_neighbors` ∈ {3, 5, 7, 11}
- LogisticRegression: `C` ∈ {0.1, 1, 10}
- XGBoost: `n_estimators` ∈ {100, 200}, `max_depth` ∈ {3, 4, 6}, `learning_rate` ∈ {0.01, 0.05, 0.1}

A search would be done **inside each LOSO fold on the training data only**,
using e.g. inner cross-validation, so that hyperparameter choice does not leak
information from the test subject.
