# Biraffe2 Ablation Comparison

Results are organized into three sub-folders:
- `normal/` — standard median-split labels
- `gridsearch/` — hyperparameter-tuned classical classifiers
- `extreme_percentile/` — bottom 20 % / top 20 % labels (equal split and real level timestamp variants)

All metrics below are **subject-level aggregates** from LOSO cross-validation.

## Best model overview per experiment

| Experiment | Normal Model | Normal Acc | Normal F1 | Normal AUC | Normal n | Grid-Search Model | Grid-Search AUC | Grid-Search n | Extreme-Percentile Model | Extreme-Percentile AUC | Extreme-Percentile n |
|---|---|---|---|---|---|---|---|---|---|---|---|
| setup_01_biraffe2_ecg_baseline | CNN1D | 0.394 | 0.383 | 0.290 | 99 | — | — | — | LSTM | 0.527 | 47 |
| setup_01_biraffe2_ecg_baseline_avg_levels | LSTM | 0.495 | 0.489 | 0.389 | 99 | — | — | — | CNN1D | 0.290 | 40 |
| setup_01_biraffe2_ecg_baseline_avg_levels_real_level_times | — | — | — | — | — | — | — | — | CNN1D | 0.290 | 40 |
| setup_01_biraffe2_ecg_baseline_real_level_times | — | — | — | — | — | — | — | — | LSTM | 0.527 | 47 |
| setup_01c_biraffe2_ecg_levels_as_subjects | CNN1D | 0.538 | 0.528 | 0.556 | 247 | — | — | — | MLP | 0.495 | 120 |
| setup_01c_biraffe2_ecg_levels_as_subjects_real_level_times | — | — | — | — | — | — | — | — | CNN1D | 0.431 | 113 |
| setup_01d_biraffe2_ecg_levels_as_subjects_real_level_times | — | — | — | — | — | — | — | — | CNN1D | 0.431 | 113 |
| setup_01d_drop_unreliable_60s_features | LSTM | 0.505 | 0.488 | 0.396 | 99 | — | — | — | LSTM | 0.305 | 43 |
| setup_01d_drop_unreliable_60s_features_real_level_times | — | — | — | — | — | — | — | — | LSTM | 0.305 | 43 |
| setup_01e_per_subject_normalization | CNN1D | 0.461 | 0.426 | 0.377 | 102 | — | — | — | CNN1D | 0.526 | 44 |
| setup_01e_per_subject_normalization_real_level_times | — | — | — | — | — | — | — | — | CNN1D | 0.526 | 44 |
| setup_01f_shorter_step | CNN1D | 0.495 | 0.486 | 0.401 | 99 | — | — | — | LSTM | 0.318 | 43 |
| setup_01f_shorter_step_real_level_times | — | — | — | — | — | — | — | — | LSTM | 0.318 | 43 |
| setup_01g_levels_as_subjects_per_subject_norm | MLP | 0.525 | 0.525 | 0.539 | 451 | — | — | — | MLP | 0.491 | 226 |
| setup_01g_levels_as_subjects_per_subject_norm_real_level_times | — | — | — | — | — | — | — | — | CNN1D | 0.431 | 113 |
| setup_02_label_margin_01 | CNN1D | 0.424 | 0.392 | 0.335 | 92 | — | — | — | LSTM | 0.527 | 47 |
| setup_02_label_margin_01_real_level_times | — | — | — | — | — | — | — | — | LSTM | 0.527 | 47 |
| setup_03_without_time_distortion | MLP | 0.577 | 0.568 | 0.587 | 260 | — | — | — | MLP | 0.430 | 102 |
| setup_03_without_time_distortion_real_level_times | — | — | — | — | — | — | — | — | MLP | 0.458 | 94 |
| setup_04_no_zscore | CNN1D | 0.394 | 0.383 | 0.290 | 99 | — | — | — | LSTM | 0.527 | 47 |
| setup_04_no_zscore_real_level_times | — | — | — | — | — | — | — | — | LSTM | 0.527 | 47 |
| setup_05_no_outlier | CNN1D | 0.382 | 0.379 | 0.310 | 102 | — | — | — | CNN1D | 0.416 | 48 |
| setup_05_no_outlier_real_level_times | — | — | — | — | — | — | — | — | CNN1D | 0.416 | 48 |
| setup_06_full_multimodal | CNN1D | 0.564 | 0.554 | 0.561 | 273 | RandomForest | 0.623 | 268 | LSTM | 0.605 | 134 |
| setup_06_full_multimodal_real_level_times | — | — | — | — | — | — | — | — | LSTM | 0.534 | 131 |
| setup_07_5min_window | CNN1D | 0.411 | 0.389 | 0.292 | 90 | — | — | — | MLP | 0.532 | 43 |
| setup_07_5min_window_real_level_times | — | — | — | — | — | — | — | — | MLP | 0.532 | 43 |
| setup_09_heartpy | MLP | 0.420 | 0.408 | 0.376 | 100 | — | — | — | MLP | 0.405 | 47 |
| setup_09_heartpy_real_level_times | — | — | — | — | — | — | — | — | MLP | 0.405 | 47 |
| setup_10_all_models | — | — | — | — | — | — | — | — | LSTM | 0.527 | 47 |
| setup_11_raw_geq_without_time_distortion | MLP | 0.577 | 0.568 | 0.587 | 260 | LogisticRegression | 0.582 | 232 | MLP | 0.430 | 102 |
| setup_11_raw_geq_without_time_distortion_real_level_times | — | — | — | — | — | — | — | — | MLP | 0.458 | 94 |
| setup_12_biraffe2_baseline_correction | MLP | 0.628 | 0.627 | 0.677 | 223 | RandomForest | 0.681 | 207 | MLP | 0.730 | 111 |
| setup_12_biraffe2_baseline_correction_real_level_times | — | — | — | — | — | — | — | — | MLP | 0.724 | 105 |

## Normal setups — full subject-level metrics

| Experiment | Best Model | Accuracy | F1 | AUC | Precision Low | Recall Low | Precision High | Recall High | n |
|---|---|---|---|---|---|---|---|---|---|
| setup_01_biraffe2_ecg_baseline | CNN1D | 0.394 | 0.383 | 0.290 | 0.419 | 0.520 | 0.351 | 0.265 | 99 |
| setup_01_biraffe2_ecg_baseline_avg_levels | LSTM | 0.495 | 0.489 | 0.389 | 0.487 | 0.388 | 0.500 | 0.600 | 99 |
| setup_01c_biraffe2_ecg_levels_as_subjects | CNN1D | 0.538 | 0.528 | 0.556 | 0.516 | 0.410 | 0.552 | 0.654 | 247 |
| setup_01d_drop_unreliable_60s_features | LSTM | 0.505 | 0.488 | 0.396 | 0.516 | 0.320 | 0.500 | 0.694 | 99 |
| setup_01e_per_subject_normalization | CNN1D | 0.461 | 0.426 | 0.377 | 0.407 | 0.220 | 0.480 | 0.692 | 102 |
| setup_01f_shorter_step | CNN1D | 0.495 | 0.486 | 0.401 | 0.500 | 0.360 | 0.492 | 0.633 | 99 |
| setup_01g_levels_as_subjects_per_subject_norm | MLP | 0.525 | 0.525 | 0.539 | 0.493 | 0.517 | 0.557 | 0.533 | 451 |
| setup_02_label_margin_01 | CNN1D | 0.424 | 0.392 | 0.335 | 0.476 | 0.600 | 0.310 | 0.214 | 92 |
| setup_03_without_time_distortion | MLP | 0.577 | 0.568 | 0.587 | 0.538 | 0.475 | 0.603 | 0.662 | 260 |
| setup_04_no_zscore | CNN1D | 0.394 | 0.383 | 0.290 | 0.419 | 0.520 | 0.351 | 0.265 | 99 |
| setup_05_no_outlier | CNN1D | 0.382 | 0.379 | 0.310 | 0.390 | 0.460 | 0.372 | 0.308 | 102 |
| setup_06_full_multimodal | CNN1D | 0.564 | 0.554 | 0.561 | 0.528 | 0.448 | 0.587 | 0.662 | 273 |
| setup_07_5min_window | CNN1D | 0.411 | 0.389 | 0.292 | 0.443 | 0.587 | 0.345 | 0.227 | 90 |
| setup_09_heartpy | MLP | 0.420 | 0.408 | 0.376 | 0.438 | 0.560 | 0.389 | 0.280 | 100 |
| setup_11_raw_geq_without_time_distortion | MLP | 0.577 | 0.568 | 0.587 | 0.538 | 0.475 | 0.603 | 0.662 | 260 |
| setup_12_biraffe2_baseline_correction | MLP | 0.628 | 0.627 | 0.677 | 0.607 | 0.613 | 0.647 | 0.641 | 223 |

## Grid-search setups — full subject-level metrics

| Experiment | Best Model | Accuracy | F1 | AUC | Precision Low | Recall Low | Precision High | Recall High | n |
|---|---|---|---|---|---|---|---|---|---|
| setup_06_full_multimodal_grid_search | RandomForest | 0.612 | 0.598 | 0.623 | 0.582 | 0.475 | 0.629 | 0.723 | 268 |
| setup_11_raw_geq_without_time_distortion_grid_search | LogisticRegression | 0.539 | 0.537 | 0.582 | 0.458 | 0.567 | 0.625 | 0.519 | 232 |
| setup_12_biraffe2_baseline_correction_grid_search | RandomForest | 0.647 | 0.647 | 0.681 | 0.604 | 0.674 | 0.693 | 0.625 | 207 |

## Extreme-percentile setups — full subject-level metrics

| Experiment | Variant | Best Model | Accuracy | F1 | AUC | Precision Low | Recall Low | Precision High | Recall High | n |
|---|---|---|---|---|---|---|---|---|---|---|
| setup_01_biraffe2_ecg_baseline_avg_levels_extreme_percentile | equal split | CNN1D | 0.325 | 0.314 | 0.290 | 0.360 | 0.450 | 0.267 | 0.200 | 40 |
| setup_01_biraffe2_ecg_baseline_avg_levels_real_level_times_extreme_percentile | real level times | CNN1D | 0.325 | 0.314 | 0.290 | 0.360 | 0.450 | 0.267 | 0.200 | 40 |
| setup_01_biraffe2_ecg_baseline_extreme_percentile | equal split | LSTM | 0.511 | 0.507 | 0.527 | 0.538 | 0.560 | 0.476 | 0.455 | 47 |
| setup_01_biraffe2_ecg_baseline_real_level_times_extreme_percentile | real level times | LSTM | 0.511 | 0.507 | 0.527 | 0.538 | 0.560 | 0.476 | 0.455 | 47 |
| setup_01c_biraffe2_ecg_levels_as_subjects_extreme_percentile | equal split | MLP | 0.508 | 0.501 | 0.495 | 0.521 | 0.613 | 0.489 | 0.397 | 120 |
| setup_01c_biraffe2_ecg_levels_as_subjects_real_level_times_extreme_percentile | real level times | CNN1D | 0.522 | 0.432 | 0.431 | 0.538 | 0.127 | 0.520 | 0.897 | 113 |
| setup_01d_biraffe2_ecg_levels_as_subjects_real_level_times_extreme_percentile | real level times | CNN1D | 0.522 | 0.432 | 0.431 | 0.538 | 0.127 | 0.520 | 0.897 | 113 |
| setup_01d_drop_unreliable_60s_features_extreme_percentile | equal split | LSTM | 0.395 | 0.392 | 0.305 | 0.368 | 0.333 | 0.417 | 0.455 | 43 |
| setup_01d_drop_unreliable_60s_features_real_level_times_extreme_percentile | real level times | LSTM | 0.395 | 0.392 | 0.305 | 0.368 | 0.333 | 0.417 | 0.455 | 43 |
| setup_01e_per_subject_normalization_extreme_percentile | equal split | CNN1D | 0.523 | 0.477 | 0.526 | 0.500 | 0.238 | 0.529 | 0.783 | 44 |
| setup_01e_per_subject_normalization_real_level_times_extreme_percentile | real level times | CNN1D | 0.523 | 0.477 | 0.526 | 0.500 | 0.238 | 0.529 | 0.783 | 44 |
| setup_01f_shorter_step_extreme_percentile | equal split | LSTM | 0.302 | 0.299 | 0.318 | 0.320 | 0.381 | 0.278 | 0.227 | 43 |
| setup_01f_shorter_step_real_level_times_extreme_percentile | real level times | LSTM | 0.302 | 0.299 | 0.318 | 0.320 | 0.381 | 0.278 | 0.227 | 43 |
| setup_01g_levels_as_subjects_per_subject_norm_extreme_percentile | equal split | MLP | 0.469 | 0.450 | 0.491 | 0.487 | 0.638 | 0.432 | 0.291 | 226 |
| setup_01g_levels_as_subjects_per_subject_norm_real_level_times_extreme_percentile | real level times | CNN1D | 0.522 | 0.432 | 0.431 | 0.538 | 0.127 | 0.520 | 0.897 | 113 |
| setup_02_label_margin_01_extreme_percentile | equal split | LSTM | 0.511 | 0.507 | 0.527 | 0.538 | 0.560 | 0.476 | 0.455 | 47 |
| setup_02_label_margin_01_real_level_times_extreme_percentile | real level times | LSTM | 0.511 | 0.507 | 0.527 | 0.538 | 0.560 | 0.476 | 0.455 | 47 |
| setup_03_without_time_distortion_extreme_percentile | equal split | MLP | 0.451 | 0.437 | 0.430 | 0.375 | 0.326 | 0.500 | 0.554 | 102 |
| setup_03_without_time_distortion_real_level_times_extreme_percentile | real level times | MLP | 0.574 | 0.491 | 0.458 | 0.444 | 0.211 | 0.605 | 0.821 | 94 |
| setup_04_no_zscore_extreme_percentile | equal split | LSTM | 0.511 | 0.507 | 0.527 | 0.538 | 0.560 | 0.476 | 0.455 | 47 |
| setup_04_no_zscore_real_level_times_extreme_percentile | real level times | LSTM | 0.511 | 0.507 | 0.527 | 0.538 | 0.560 | 0.476 | 0.455 | 47 |
| setup_05_no_outlier_extreme_percentile | equal split | CNN1D | 0.500 | 0.499 | 0.416 | 0.520 | 0.520 | 0.478 | 0.478 | 48 |
| setup_05_no_outlier_real_level_times_extreme_percentile | real level times | CNN1D | 0.500 | 0.499 | 0.416 | 0.520 | 0.520 | 0.478 | 0.478 | 48 |
| setup_06_full_multimodal_extreme_percentile | equal split | LSTM | 0.560 | 0.559 | 0.605 | 0.541 | 0.615 | 0.583 | 0.507 | 134 |
| setup_06_full_multimodal_real_level_times_extreme_percentile | real level times | LSTM | 0.519 | 0.484 | 0.534 | 0.486 | 0.274 | 0.531 | 0.739 | 131 |
| setup_07_5min_window_extreme_percentile | equal split | MLP | 0.512 | 0.494 | 0.532 | 0.517 | 0.682 | 0.500 | 0.333 | 43 |
| setup_07_5min_window_real_level_times_extreme_percentile | real level times | MLP | 0.512 | 0.494 | 0.532 | 0.517 | 0.682 | 0.500 | 0.333 | 43 |
| setup_09_heartpy_extreme_percentile | equal split | MLP | 0.489 | 0.484 | 0.405 | 0.519 | 0.560 | 0.450 | 0.409 | 47 |
| setup_09_heartpy_real_level_times_extreme_percentile | real level times | MLP | 0.489 | 0.484 | 0.405 | 0.519 | 0.560 | 0.450 | 0.409 | 47 |
| setup_10_all_models_extreme_percentile | equal split | LSTM | 0.511 | 0.507 | 0.527 | 0.538 | 0.560 | 0.476 | 0.455 | 47 |
| setup_11_raw_geq_without_time_distortion_extreme_percentile | equal split | MLP | 0.451 | 0.437 | 0.430 | 0.375 | 0.326 | 0.500 | 0.554 | 102 |
| setup_11_raw_geq_without_time_distortion_real_level_times_extreme_percentile | real level times | MLP | 0.574 | 0.491 | 0.458 | 0.444 | 0.211 | 0.605 | 0.821 | 94 |
| setup_12_biraffe2_baseline_correction_extreme_percentile | equal split | MLP | 0.640 | 0.631 | 0.730 | 0.620 | 0.772 | 0.675 | 0.500 | 111 |
| setup_12_biraffe2_baseline_correction_real_level_times_extreme_percentile | real level times | MLP | 0.619 | 0.615 | 0.724 | 0.628 | 0.529 | 0.613 | 0.704 | 105 |

## Supervisor summary: setups with subject-level accuracy > 0.68

No Biraffe2 setup reached a subject-level accuracy above 0.68.

The closest near-misses are:

| Setup | Category | Best Model | Accuracy | AUC | n |
|---|---|---|---|---|---|
| setup_12_biraffe2_baseline_correction_grid_search | grid search | RandomForest | 0.647 | 0.681 | 207 |
| setup_12_biraffe2_baseline_correction_extreme_percentile | extreme percentile (equal split) | MLP | 0.640 | 0.730 | 111 |
| setup_12_biraffe2_baseline_correction | normal | MLP | 0.628 | 0.677 | 223 |
| setup_12_biraffe2_baseline_correction_real_level_times_extreme_percentile | extreme percentile (real level times) | MLP | 0.619 | 0.724 | 105 |
| setup_06_full_multimodal_grid_search | grid search | RandomForest | 0.612 | 0.623 | 268 |

If the supervisor's threshold applies to **AUC** instead of accuracy, four setups exceed AUC 0.68 (all variants of setup_12_biraffe2_baseline_correction; see the separate `supervisor_accuracy_over_068.md` for full pipeline details).