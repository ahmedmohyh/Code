# Biraffe2 Setups with Subject-Level Accuracy or AUC > 0.68

This document lists every Biraffe2 setup whose best model achieved a subject-level accuracy or AUC above 0.68 in LOSO cross-validation.

## Accuracy > 0.68

### setup_12_biraffe2_baseline_correction_extreme_percentile_classical

- **Category:** extreme percentile (equal split)
- **Best classifier:** SVM
- **Subject-level accuracy:** 0.730
- **Subject-level AUC:** 0.790
- **Number of pseudo-subjects (n):** 111
- **Data / modalities:** ECG
- **Levels treated as subjects:** True
- **Labeling:** extreme_percentile with margin=0.0
- **Outlier strategy:** train_only
- **Z-standardisation:** True
- **Baseline correction:** change_score (from procedure events: True)
- **Window length / step:** 60s / 30s
- **Real level timestamps (games_zip):** False
- **All models tested in config:** RandomForest, XGBoost, SVM, LogisticRegression, kNN

## AUC > 0.68

### setup_12_biraffe2_baseline_correction_extreme_percentile_classical

- **Category:** extreme percentile (equal split)
- **Best classifier:** SVM
- **Subject-level accuracy:** 0.730
- **Subject-level AUC:** 0.790
- **Number of pseudo-subjects (n):** 111
- **Data / modalities:** ECG
- **Levels treated as subjects:** True
- **Labeling:** extreme_percentile with margin=0.0
- **Outlier strategy:** train_only
- **Z-standardisation:** True
- **Baseline correction:** change_score (from procedure events: True)
- **Window length / step:** 60s / 30s
- **Real level timestamps (games_zip):** False
- **All models tested in config:** RandomForest, XGBoost, SVM, LogisticRegression, kNN

### setup_12_biraffe2_baseline_correction_extreme_percentile

- **Category:** extreme percentile (equal split)
- **Best classifier:** MLP
- **Subject-level accuracy:** 0.640
- **Subject-level AUC:** 0.730
- **Number of pseudo-subjects (n):** 111
- **Data / modalities:** ECG
- **Levels treated as subjects:** True
- **Labeling:** extreme_percentile with margin=0.0
- **Outlier strategy:** train_only
- **Z-standardisation:** True
- **Baseline correction:** change_score (from procedure events: True)
- **Window length / step:** 60s / 30s
- **Real level timestamps (games_zip):** False
- **All models tested in config:** MLP, LSTM, CNN1D

### setup_12_biraffe2_baseline_correction_real_level_times_extreme_percentile_classical

- **Category:** extreme percentile (real level times)
- **Best classifier:** RandomForest
- **Subject-level accuracy:** 0.676
- **Subject-level AUC:** 0.726
- **Number of pseudo-subjects (n):** 105
- **Data / modalities:** ECG
- **Levels treated as subjects:** True
- **Labeling:** extreme_percentile with margin=0.0
- **Outlier strategy:** train_only
- **Z-standardisation:** True
- **Baseline correction:** change_score (from procedure events: True)
- **Window length / step:** 60s / 30s
- **Real level timestamps (games_zip):** True
- **All models tested in config:** RandomForest, XGBoost, SVM, LogisticRegression, kNN

### setup_12_biraffe2_baseline_correction_real_level_times_extreme_percentile

- **Category:** extreme percentile (real level times)
- **Best classifier:** MLP
- **Subject-level accuracy:** 0.619
- **Subject-level AUC:** 0.724
- **Number of pseudo-subjects (n):** 105
- **Data / modalities:** ECG
- **Levels treated as subjects:** True
- **Labeling:** extreme_percentile with margin=0.0
- **Outlier strategy:** train_only
- **Z-standardisation:** True
- **Baseline correction:** change_score (from procedure events: True)
- **Window length / step:** 60s / 30s
- **Real level timestamps (games_zip):** True
- **All models tested in config:** MLP, LSTM, CNN1D

### setup_12_biraffe2_baseline_correction_grid_search

- **Category:** grid search
- **Best classifier:** RandomForest
- **Subject-level accuracy:** 0.647
- **Subject-level AUC:** 0.681
- **Number of pseudo-subjects (n):** 207
- **Data / modalities:** ECG
- **Levels treated as subjects:** True
- **Labeling:** median_split with margin=0.0
- **Outlier strategy:** train_only
- **Z-standardisation:** True
- **Baseline correction:** change_score (from procedure events: True)
- **Window length / step:** 60s / 30s
- **Real level timestamps (games_zip):** True
- **All models tested in config:** RandomForest

### setup_06_full_multimodal_extreme_percentile_classical

- **Category:** extreme percentile (equal split)
- **Best classifier:** kNN
- **Subject-level accuracy:** 0.612
- **Subject-level AUC:** 0.681
- **Number of pseudo-subjects (n):** 134
- **Data / modalities:** ECG, EDA, FACE
- **Levels treated as subjects:** True
- **Labeling:** extreme_percentile with margin=0.0
- **Outlier strategy:** none
- **Z-standardisation:** True
- **Baseline correction:** none (from procedure events: False)
- **Window length / step:** 60s / 30s
- **Real level timestamps (games_zip):** False
- **All models tested in config:** RandomForest, XGBoost, SVM, LogisticRegression, kNN
