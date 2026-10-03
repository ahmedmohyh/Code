# Biraffe2 Setups with Subject-Level Accuracy > 0.68

This document lists every Biraffe2 setup whose best model achieved a subject-level accuracy above 0.68 in LOSO cross-validation.

## setup_12_biraffe2_baseline_correction_extreme_percentile_classical

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
