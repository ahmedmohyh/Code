# Irshad/PhySF ablation comparison (subject-level AUC)

Models trained with LOSO cross-validation on the PhySF dataset.

**Note: results in this table are split by `preprocessing.outlier_strategy`. Default columns are `train_only`; `none` columns were added from the rerun with no outlier removal.**


## Best subject-level AUC per modality


| Model | ECG+EDA+EEG (train_only) | ECG+EDA+EEG (none) | ECG+EDA (train_only) | ECG only (train_only) | Best (train_only) | Grid-Search Best (train_only) |
|---|---|---|---|---|---|---|
| RandomForest | 0.889 | 0.404 | 0.296 | 0.712 | 0.889 | **0.889** |
| XGBoost | 0.778 | — | 0.259 | 0.615 | 0.778 | — |
| LSTM | 0.667 | — | 0.160 | 0.519 | 0.667 | — |
| SVM | 0.556 | — | 0.160 | 0.635 | 0.635 | — |
| LogisticRegression | 0.611 | — | 0.210 | 0.449 | 0.611 | — |
| MLP | 0.611 | — | 0.210 | 0.590 | 0.611 | — |
| kNN | 0.556 | — | 0.333 | 0.356 | 0.556 | — |
| CNN1D | 0.444 | — | 0.333 | 0.359 | 0.444 | — |

## Full results


| Experiment | Modality | Model | Accuracy (train_only) | F1-macro (train_only) | AUC (train_only) | n (train_only) | Grid-Search Model | Grid-Search AUC (train_only) | Accuracy (none) | F1-macro (none) | AUC (none) | n (none) | Grid-Search Model (none) | Grid-Search AUC (none) | Extreme-Percentile Model | Extreme-Percentile AUC | Extreme-Percentile n |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| setup_08b_irshad_physf_ecg_only | ECG only | RandomForest | 0.680 | 0.667 | 0.712 | 25 | — | — | — | — | — | — | — | — | — | — | — |
| setup_08b_irshad_physf_ecg_only | ECG only | SVM | 0.600 | 0.594 | 0.635 | 25 | — | — | — | — | — | — | — | — | — | — | — |
| setup_08b_irshad_physf_ecg_only | ECG only | XGBoost | 0.680 | 0.667 | 0.615 | 25 | — | — | — | — | — | — | — | — | — | — | — |
| setup_08b_irshad_physf_ecg_only | ECG only | MLP | 0.520 | 0.500 | 0.590 | 25 | — | — | — | — | — | — | — | — | — | — | — |
| setup_08b_irshad_physf_ecg_only | ECG only | LSTM | 0.520 | 0.479 | 0.519 | 25 | — | — | — | — | — | — | — | — | — | — | — |
| setup_08b_irshad_physf_ecg_only | ECG only | LogisticRegression | 0.480 | 0.477 | 0.449 | 25 | — | — | — | — | — | — | — | — | — | — | — |
| setup_08b_irshad_physf_ecg_only | ECG only | CNN1D | 0.440 | 0.432 | 0.359 | 25 | — | — | — | — | — | — | — | — | — | — | — |
| setup_08b_irshad_physf_ecg_only | ECG only | kNN | 0.400 | 0.384 | 0.356 | 25 | — | — | — | — | — | — | — | — | — | — | — |
| setup_08a_irshad_physf_ecg_eda | ECG+EDA | kNN | 0.278 | 0.276 | 0.333 | 18 | — | — | — | — | — | — | — | — | — | — | — |
| setup_08a_irshad_physf_ecg_eda | ECG+EDA | CNN1D | 0.444 | 0.444 | 0.333 | 18 | — | — | — | — | — | — | — | — | — | — | — |
| setup_08a_irshad_physf_ecg_eda | ECG+EDA | RandomForest | 0.333 | 0.325 | 0.296 | 18 | — | — | — | — | — | — | — | — | — | — | — |
| setup_08a_irshad_physf_ecg_eda | ECG+EDA | XGBoost | 0.333 | 0.325 | 0.259 | 18 | — | — | — | — | — | — | — | — | — | — | — |
| setup_08a_irshad_physf_ecg_eda | ECG+EDA | LogisticRegression | 0.278 | 0.276 | 0.210 | 18 | — | — | — | — | — | — | — | — | — | — | — |
| setup_08a_irshad_physf_ecg_eda | ECG+EDA | MLP | 0.444 | 0.444 | 0.210 | 18 | — | — | — | — | — | — | — | — | — | — | — |
| setup_08a_irshad_physf_ecg_eda | ECG+EDA | SVM | 0.278 | 0.276 | 0.160 | 18 | — | — | — | — | — | — | — | — | — | — | — |
| setup_08a_irshad_physf_ecg_eda | ECG+EDA | LSTM | 0.333 | 0.325 | 0.160 | 18 | — | — | — | — | — | — | — | — | — | — | — |
| setup_08_irshad_physf | ECG+EDA+EEG | RandomForest | 0.667 | 0.649 | 0.889 | 9 | RandomForest | 0.889 | 0.480 | 0.448 | 0.404 | 25 | RandomForest | 0.404 | — | — | — |
| setup_08_irshad_physf | ECG+EDA+EEG | XGBoost | 0.667 | 0.649 | 0.778 | 9 | — | — | — | — | — | — | — | — | — | — | — |
| setup_08_irshad_physf | ECG+EDA+EEG | LSTM | 0.667 | 0.585 | 0.667 | 9 | — | — | — | — | — | — | — | — | — | — | — |
| setup_08_irshad_physf | ECG+EDA+EEG | LogisticRegression | 0.556 | 0.500 | 0.611 | 9 | — | — | — | — | — | — | — | — | — | — | — |
| setup_08_irshad_physf | ECG+EDA+EEG | MLP | 0.556 | 0.500 | 0.611 | 9 | — | — | — | — | — | — | — | — | — | — | — |
| setup_08_irshad_physf | ECG+EDA+EEG | SVM | 0.444 | 0.308 | 0.556 | 9 | — | — | — | — | — | — | — | — | — | — | — |
| setup_08_irshad_physf | ECG+EDA+EEG | kNN | 0.667 | 0.585 | 0.556 | 9 | — | — | — | — | — | — | — | — | — | — | — |
| setup_08_irshad_physf | ECG+EDA+EEG | CNN1D | 0.444 | 0.416 | 0.444 | 9 | — | — | — | — | — | — | — | — | — | — | — |

*Grid-search results are for classical classifiers only. For `outlier_strategy: train_only`, grid search on `setup_08_irshad_physf` gave optimized RandomForest parameters `n_estimators=100, max_depth=null, min_samples_split=2, min_samples_leaf=1, class_weight=balanced`, yielding AUC = 0.889 (same as the non-grid-search result). For `outlier_strategy: none`, the best RandomForest parameters were `n_estimators=500, max_depth=10, min_samples_split=2, min_samples_leaf=1, class_weight=balanced`, yielding AUC = 0.404 on 25 pseudo-subjects. Extreme-percentile labeling has not yet been run on the Irshad/PhySF dataset.*
