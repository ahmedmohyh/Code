# Biraffe2 Setups with Subject-Level Accuracy > 0.68

This document lists every Biraffe2 setup whose best model achieved a subject-level accuracy above 0.68 in LOSO cross-validation.

## Result

No Biraffe2 setup reached a subject-level accuracy above 0.68.

## Closest near-misses (subject-level accuracy ≥ 0.60)

| Setup | Category | Best Model | Accuracy | AUC | n | Pipeline highlights |
|---|---|---|---|---|---|---|
| setup_12_biraffe2_baseline_correction_grid_search | grid search | RandomForest | 0.647 | 0.681 | 207 | ECG, `train_only` outlier, baseline correction `change_score`, z-score, 60s/30s window |
| setup_12_biraffe2_baseline_correction_extreme_percentile | extreme percentile (equal split) | MLP | 0.640 | 0.730 | 111 | ECG, `train_only` outlier, baseline correction `change_score`, z-score, 60s/30s window |
| setup_12_biraffe2_baseline_correction | normal | MLP | 0.628 | 0.677 | 223 | ECG, `train_only` outlier, baseline correction `change_score`, z-score, 60s/30s window |
| setup_12_biraffe2_baseline_correction_real_level_times_extreme_percentile | extreme percentile (real level times) | MLP | 0.619 | 0.724 | 105 | ECG, `train_only` outlier, baseline correction `change_score`, real level timestamps, 60s/30s window |
| setup_06_full_multimodal_grid_search | grid search | RandomForest | 0.612 | 0.623 | 268 | ECG+EDA+FACE, `none` outlier, no baseline, z-score, 60s/30s window |
| setup_06_full_multimodal_extreme_percentile | extreme percentile (equal split) | LSTM | 0.560 | 0.605 | 134 | ECG+EDA+FACE, `none` outlier, no baseline, z-score, 60s/30s window |
| setup_03_without_time_distortion | normal | MLP | 0.577 | 0.587 | 260 | ECG, `train_only` outlier, no baseline, z-score, 60s/30s window, no time-distortion features |
| setup_11_raw_geq_without_time_distortion | normal | MLP | 0.577 | 0.587 | 260 | ECG, `train_only` outlier, no baseline, z-score, 60s/30s window, raw GEQ scores |
| setup_06_full_multimodal | normal | CNN1D | 0.564 | 0.561 | 273 | ECG+EDA+FACE, `none` outlier, no baseline, z-score, 60s/30s window |

## Note on AUC

If the supervisor's threshold is meant to apply to **AUC** rather than accuracy, the following setups exceed AUC 0.68:

- setup_12_biraffe2_baseline_correction_extreme_percentile — MLP — AUC 0.730
- setup_12_biraffe2_baseline_correction_real_level_times_extreme_percentile — MLP — AUC 0.724
- setup_12_biraffe2_baseline_correction_grid_search — RandomForest — AUC 0.681
- setup_12_biraffe2_baseline_correction — MLP — AUC 0.677