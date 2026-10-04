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
| setup_01_biraffe2_ecg_baseline_avg_levels_classical | — | — | — | — | — | — | — | — | RandomForest | 0.345 | 40 |
| setup_01_biraffe2_ecg_baseline_avg_levels_real_level_times | — | — | — | — | — | — | — | — | CNN1D | 0.290 | 40 |
| setup_01_biraffe2_ecg_baseline_avg_levels_real_level_times_classical | — | — | — | — | — | — | — | — | RandomForest | 0.345 | 40 |
| setup_01_biraffe2_ecg_baseline_classical | — | — | — | — | — | — | — | — | kNN | 0.495 | 47 |
| setup_01_biraffe2_ecg_baseline_real_level_times | — | — | — | — | — | — | — | — | LSTM | 0.527 | 47 |
| setup_01_biraffe2_ecg_baseline_real_level_times_classical | — | — | — | — | — | — | — | — | kNN | 0.495 | 47 |
| setup_01c_biraffe2_ecg_levels_as_subjects | CNN1D | 0.538 | 0.528 | 0.556 | 247 | — | — | — | MLP | 0.495 | 120 |
| setup_01c_biraffe2_ecg_levels_as_subjects_classical | — | — | — | — | — | — | — | — | kNN | 0.586 | 120 |
| setup_01c_biraffe2_ecg_levels_as_subjects_real_level_times | — | — | — | — | — | — | — | — | CNN1D | 0.431 | 113 |
| setup_01c_biraffe2_ecg_levels_as_subjects_real_level_times_classical | — | — | — | — | — | — | — | — | kNN | 0.491 | 113 |
| setup_01d_biraffe2_ecg_levels_as_subjects_real_level_times | — | — | — | — | — | — | — | — | CNN1D | 0.431 | 113 |
| setup_01d_biraffe2_ecg_levels_as_subjects_real_level_times_classical | — | — | — | — | — | — | — | — | kNN | 0.491 | 113 |
| setup_01d_drop_unreliable_60s_features | LSTM | 0.505 | 0.488 | 0.396 | 99 | — | — | — | LSTM | 0.305 | 43 |
| setup_01d_drop_unreliable_60s_features_classical | — | — | — | — | — | — | — | — | LogisticRegression | 0.435 | 43 |
| setup_01d_drop_unreliable_60s_features_real_level_times | — | — | — | — | — | — | — | — | LSTM | 0.305 | 43 |
| setup_01d_drop_unreliable_60s_features_real_level_times_classical | — | — | — | — | — | — | — | — | LogisticRegression | 0.435 | 43 |
| setup_01e_per_subject_normalization | CNN1D | 0.461 | 0.426 | 0.377 | 102 | — | — | — | CNN1D | 0.526 | 44 |
| setup_01e_per_subject_normalization_classical | — | — | — | — | — | — | — | — | LogisticRegression | 0.468 | 44 |
| setup_01e_per_subject_normalization_real_level_times | — | — | — | — | — | — | — | — | CNN1D | 0.526 | 44 |
| setup_01e_per_subject_normalization_real_level_times_classical | — | — | — | — | — | — | — | — | LogisticRegression | 0.468 | 44 |
| setup_01f_shorter_step | CNN1D | 0.495 | 0.486 | 0.401 | 99 | — | — | — | LSTM | 0.318 | 43 |
| setup_01f_shorter_step_classical | — | — | — | — | — | — | — | — | LogisticRegression | 0.357 | 43 |
| setup_01f_shorter_step_real_level_times | — | — | — | — | — | — | — | — | LSTM | 0.318 | 43 |
| setup_01f_shorter_step_real_level_times_classical | — | — | — | — | — | — | — | — | LogisticRegression | 0.357 | 43 |
| setup_01g_levels_as_subjects_per_subject_norm | MLP | 0.525 | 0.525 | 0.539 | 451 | — | — | — | MLP | 0.491 | 226 |
| setup_01g_levels_as_subjects_per_subject_norm_classical | — | — | — | — | — | — | — | — | SVM | 0.521 | 226 |
| setup_01g_levels_as_subjects_per_subject_norm_real_level_times | — | — | — | — | — | — | — | — | CNN1D | 0.431 | 113 |
| setup_01g_levels_as_subjects_per_subject_norm_real_level_times_classical | — | — | — | — | — | — | — | — | kNN | 0.491 | 113 |
| setup_02_label_margin_01 | CNN1D | 0.424 | 0.392 | 0.335 | 92 | — | — | — | LSTM | 0.527 | 47 |
| setup_02_label_margin_01_classical | — | — | — | — | — | — | — | — | kNN | 0.495 | 47 |
| setup_02_label_margin_01_real_level_times | — | — | — | — | — | — | — | — | LSTM | 0.527 | 47 |
| setup_02_label_margin_01_real_level_times_classical | — | — | — | — | — | — | — | — | kNN | 0.495 | 47 |
| setup_03_without_time_distortion | MLP | 0.577 | 0.568 | 0.587 | 260 | — | — | — | MLP | 0.430 | 102 |
| setup_03_without_time_distortion_classical | — | — | — | — | — | — | — | — | RandomForest | 0.537 | 102 |
| setup_03_without_time_distortion_real_level_times | — | — | — | — | — | — | — | — | MLP | 0.458 | 94 |
| setup_03_without_time_distortion_real_level_times_classical | — | — | — | — | — | — | — | — | LogisticRegression | 0.469 | 94 |
| setup_04_no_zscore | CNN1D | 0.394 | 0.383 | 0.290 | 99 | — | — | — | LSTM | 0.527 | 47 |
| setup_04_no_zscore_classical | — | — | — | — | — | — | — | — | RandomForest | 0.436 | 47 |
| setup_04_no_zscore_real_level_times | — | — | — | — | — | — | — | — | LSTM | 0.527 | 47 |
| setup_04_no_zscore_real_level_times_classical | — | — | — | — | — | — | — | — | RandomForest | 0.436 | 47 |
| setup_05_no_outlier | CNN1D | 0.382 | 0.379 | 0.310 | 102 | — | — | — | CNN1D | 0.416 | 48 |
| setup_05_no_outlier_classical | — | — | — | — | — | — | — | — | RandomForest | 0.381 | 48 |
| setup_05_no_outlier_real_level_times | — | — | — | — | — | — | — | — | CNN1D | 0.416 | 48 |
| setup_05_no_outlier_real_level_times_classical | — | — | — | — | — | — | — | — | RandomForest | 0.381 | 48 |
| setup_06_full_multimodal | CNN1D | 0.564 | 0.554 | 0.561 | 273 | RandomForest | 0.623 | 268 | LSTM | 0.605 | 134 |
| setup_06_full_multimodal_classical | — | — | — | — | — | — | — | — | kNN | 0.681 | 134 |
| setup_06_full_multimodal_real_level_times | — | — | — | — | — | — | — | — | LSTM | 0.534 | 131 |
| setup_06_full_multimodal_real_level_times_classical | — | — | — | — | — | — | — | — | kNN | 0.651 | 131 |
| setup_07_5min_window | CNN1D | 0.411 | 0.389 | 0.292 | 90 | — | — | — | MLP | 0.532 | 43 |
| setup_07_5min_window_classical | — | — | — | — | — | — | — | — | LogisticRegression | 0.641 | 43 |
| setup_07_5min_window_real_level_times | — | — | — | — | — | — | — | — | MLP | 0.532 | 43 |
| setup_07_5min_window_real_level_times_classical | — | — | — | — | — | — | — | — | LogisticRegression | 0.641 | 43 |
| setup_09_heartpy | MLP | 0.420 | 0.408 | 0.376 | 100 | — | — | — | MLP | 0.405 | 47 |
| setup_09_heartpy_classical | — | — | — | — | — | — | — | — | SVM | 0.438 | 47 |
| setup_09_heartpy_real_level_times | — | — | — | — | — | — | — | — | MLP | 0.405 | 47 |
| setup_09_heartpy_real_level_times_classical | — | — | — | — | — | — | — | — | SVM | 0.438 | 47 |
| setup_10_all_models | — | — | — | — | — | — | — | — | LSTM | 0.527 | 47 |
| setup_10_all_models_classical | — | — | — | — | — | — | — | — | kNN | 0.495 | 47 |
| setup_11_raw_geq_without_time_distortion | MLP | 0.577 | 0.568 | 0.587 | 260 | LogisticRegression | 0.582 | 232 | MLP | 0.430 | 102 |
| setup_11_raw_geq_without_time_distortion_classical | — | — | — | — | — | — | — | — | RandomForest | 0.537 | 102 |
| setup_11_raw_geq_without_time_distortion_real_level_times | — | — | — | — | — | — | — | — | MLP | 0.458 | 94 |
| setup_11_raw_geq_without_time_distortion_real_level_times_classical | — | — | — | — | — | — | — | — | LogisticRegression | 0.469 | 94 |
| setup_12_biraffe2_baseline_correction | MLP | 0.628 | 0.627 | 0.677 | 223 | RandomForest | 0.681 | 207 | MLP | 0.730 | 111 |
| setup_12_biraffe2_baseline_correction_classical | — | — | — | — | — | — | — | — | SVM | 0.790 | 111 |
| setup_12_biraffe2_baseline_correction_real_level_times | — | — | — | — | — | — | — | — | MLP | 0.724 | 105 |
| setup_12_biraffe2_baseline_correction_real_level_times_classical | — | — | — | — | — | — | — | — | RandomForest | 0.726 | 105 |

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
| setup_01_biraffe2_ecg_baseline_avg_levels_extreme_percentile_classical | equal split | RandomForest | 0.425 | 0.425 | 0.345 | 0.429 | 0.450 | 0.421 | 0.400 | 40 |
| setup_01_biraffe2_ecg_baseline_avg_levels_real_level_times_extreme_percentile | real level times | CNN1D | 0.325 | 0.314 | 0.290 | 0.360 | 0.450 | 0.267 | 0.200 | 40 |
| setup_01_biraffe2_ecg_baseline_avg_levels_real_level_times_extreme_percentile_classical | real level times | RandomForest | 0.425 | 0.425 | 0.345 | 0.429 | 0.450 | 0.421 | 0.400 | 40 |
| setup_01_biraffe2_ecg_baseline_extreme_percentile | equal split | LSTM | 0.511 | 0.507 | 0.527 | 0.538 | 0.560 | 0.476 | 0.455 | 47 |
| setup_01_biraffe2_ecg_baseline_extreme_percentile_classical | equal split | kNN | 0.489 | 0.470 | 0.495 | 0.516 | 0.640 | 0.438 | 0.318 | 47 |
| setup_01_biraffe2_ecg_baseline_real_level_times_extreme_percentile | real level times | LSTM | 0.511 | 0.507 | 0.527 | 0.538 | 0.560 | 0.476 | 0.455 | 47 |
| setup_01_biraffe2_ecg_baseline_real_level_times_extreme_percentile_classical | real level times | kNN | 0.489 | 0.470 | 0.495 | 0.516 | 0.640 | 0.438 | 0.318 | 47 |
| setup_01c_biraffe2_ecg_levels_as_subjects_extreme_percentile | equal split | MLP | 0.508 | 0.501 | 0.495 | 0.521 | 0.613 | 0.489 | 0.397 | 120 |
| setup_01c_biraffe2_ecg_levels_as_subjects_extreme_percentile_classical | equal split | kNN | 0.625 | 0.617 | 0.586 | 0.613 | 0.742 | 0.644 | 0.500 | 120 |
| setup_01c_biraffe2_ecg_levels_as_subjects_real_level_times_extreme_percentile | real level times | CNN1D | 0.522 | 0.432 | 0.431 | 0.538 | 0.127 | 0.520 | 0.897 | 113 |
| setup_01c_biraffe2_ecg_levels_as_subjects_real_level_times_extreme_percentile_classical | real level times | kNN | 0.593 | 0.550 | 0.491 | 0.696 | 0.291 | 0.567 | 0.879 | 113 |
| setup_01d_biraffe2_ecg_levels_as_subjects_real_level_times_extreme_percentile | real level times | CNN1D | 0.522 | 0.432 | 0.431 | 0.538 | 0.127 | 0.520 | 0.897 | 113 |
| setup_01d_biraffe2_ecg_levels_as_subjects_real_level_times_extreme_percentile_classical | real level times | kNN | 0.593 | 0.550 | 0.491 | 0.696 | 0.291 | 0.567 | 0.879 | 113 |
| setup_01d_drop_unreliable_60s_features_extreme_percentile | equal split | LSTM | 0.395 | 0.392 | 0.305 | 0.368 | 0.333 | 0.417 | 0.455 | 43 |
| setup_01d_drop_unreliable_60s_features_extreme_percentile_classical | equal split | LogisticRegression | 0.488 | 0.486 | 0.435 | 0.474 | 0.429 | 0.500 | 0.545 | 43 |
| setup_01d_drop_unreliable_60s_features_real_level_times_extreme_percentile | real level times | LSTM | 0.395 | 0.392 | 0.305 | 0.368 | 0.333 | 0.417 | 0.455 | 43 |
| setup_01d_drop_unreliable_60s_features_real_level_times_extreme_percentile_classical | real level times | LogisticRegression | 0.488 | 0.486 | 0.435 | 0.474 | 0.429 | 0.500 | 0.545 | 43 |
| setup_01e_per_subject_normalization_extreme_percentile | equal split | CNN1D | 0.523 | 0.477 | 0.526 | 0.500 | 0.238 | 0.529 | 0.783 | 44 |
| setup_01e_per_subject_normalization_extreme_percentile_classical | equal split | LogisticRegression | 0.568 | 0.549 | 0.468 | 0.531 | 0.810 | 0.667 | 0.348 | 44 |
| setup_01e_per_subject_normalization_real_level_times_extreme_percentile | real level times | CNN1D | 0.523 | 0.477 | 0.526 | 0.500 | 0.238 | 0.529 | 0.783 | 44 |
| setup_01e_per_subject_normalization_real_level_times_extreme_percentile_classical | real level times | LogisticRegression | 0.568 | 0.549 | 0.468 | 0.531 | 0.810 | 0.667 | 0.348 | 44 |
| setup_01f_shorter_step_extreme_percentile | equal split | LSTM | 0.302 | 0.299 | 0.318 | 0.320 | 0.381 | 0.278 | 0.227 | 43 |
| setup_01f_shorter_step_extreme_percentile_classical | equal split | LogisticRegression | 0.442 | 0.442 | 0.357 | 0.429 | 0.429 | 0.455 | 0.455 | 43 |
| setup_01f_shorter_step_real_level_times_extreme_percentile | real level times | LSTM | 0.302 | 0.299 | 0.318 | 0.320 | 0.381 | 0.278 | 0.227 | 43 |
| setup_01f_shorter_step_real_level_times_extreme_percentile_classical | real level times | LogisticRegression | 0.442 | 0.442 | 0.357 | 0.429 | 0.429 | 0.455 | 0.455 | 43 |
| setup_01g_levels_as_subjects_per_subject_norm_extreme_percentile | equal split | MLP | 0.469 | 0.450 | 0.491 | 0.487 | 0.638 | 0.432 | 0.291 | 226 |
| setup_01g_levels_as_subjects_per_subject_norm_extreme_percentile_classical | equal split | SVM | 0.513 | 0.511 | 0.521 | 0.524 | 0.569 | 0.500 | 0.455 | 226 |
| setup_01g_levels_as_subjects_per_subject_norm_real_level_times_extreme_percentile | real level times | CNN1D | 0.522 | 0.432 | 0.431 | 0.538 | 0.127 | 0.520 | 0.897 | 113 |
| setup_01g_levels_as_subjects_per_subject_norm_real_level_times_extreme_percentile_classical | real level times | kNN | 0.593 | 0.550 | 0.491 | 0.696 | 0.291 | 0.567 | 0.879 | 113 |
| setup_02_label_margin_01_extreme_percentile | equal split | LSTM | 0.511 | 0.507 | 0.527 | 0.538 | 0.560 | 0.476 | 0.455 | 47 |
| setup_02_label_margin_01_extreme_percentile_classical | equal split | kNN | 0.489 | 0.470 | 0.495 | 0.516 | 0.640 | 0.438 | 0.318 | 47 |
| setup_02_label_margin_01_real_level_times_extreme_percentile | real level times | LSTM | 0.511 | 0.507 | 0.527 | 0.538 | 0.560 | 0.476 | 0.455 | 47 |
| setup_02_label_margin_01_real_level_times_extreme_percentile_classical | real level times | kNN | 0.489 | 0.470 | 0.495 | 0.516 | 0.640 | 0.438 | 0.318 | 47 |
| setup_03_without_time_distortion_extreme_percentile | equal split | MLP | 0.451 | 0.437 | 0.430 | 0.375 | 0.326 | 0.500 | 0.554 | 102 |
| setup_03_without_time_distortion_extreme_percentile_classical | equal split | RandomForest | 0.529 | 0.529 | 0.537 | 0.481 | 0.565 | 0.583 | 0.500 | 102 |
| setup_03_without_time_distortion_real_level_times_extreme_percentile | real level times | MLP | 0.574 | 0.491 | 0.458 | 0.444 | 0.211 | 0.605 | 0.821 | 94 |
| setup_03_without_time_distortion_real_level_times_extreme_percentile_classical | real level times | LogisticRegression | 0.479 | 0.465 | 0.469 | 0.366 | 0.395 | 0.566 | 0.536 | 94 |
| setup_04_no_zscore_extreme_percentile | equal split | LSTM | 0.511 | 0.507 | 0.527 | 0.538 | 0.560 | 0.476 | 0.455 | 47 |
| setup_04_no_zscore_extreme_percentile_classical | equal split | RandomForest | 0.404 | 0.404 | 0.436 | 0.435 | 0.400 | 0.375 | 0.409 | 47 |
| setup_04_no_zscore_real_level_times_extreme_percentile | real level times | LSTM | 0.511 | 0.507 | 0.527 | 0.538 | 0.560 | 0.476 | 0.455 | 47 |
| setup_04_no_zscore_real_level_times_extreme_percentile_classical | real level times | RandomForest | 0.404 | 0.404 | 0.436 | 0.435 | 0.400 | 0.375 | 0.409 | 47 |
| setup_05_no_outlier_extreme_percentile | equal split | CNN1D | 0.500 | 0.499 | 0.416 | 0.520 | 0.520 | 0.478 | 0.478 | 48 |
| setup_05_no_outlier_extreme_percentile_classical | equal split | RandomForest | 0.458 | 0.457 | 0.381 | 0.480 | 0.480 | 0.435 | 0.435 | 48 |
| setup_05_no_outlier_real_level_times_extreme_percentile | real level times | CNN1D | 0.500 | 0.499 | 0.416 | 0.520 | 0.520 | 0.478 | 0.478 | 48 |
| setup_05_no_outlier_real_level_times_extreme_percentile_classical | real level times | RandomForest | 0.458 | 0.457 | 0.381 | 0.480 | 0.480 | 0.435 | 0.435 | 48 |
| setup_06_full_multimodal_extreme_percentile | equal split | LSTM | 0.560 | 0.559 | 0.605 | 0.541 | 0.615 | 0.583 | 0.507 | 134 |
| setup_06_full_multimodal_extreme_percentile_classical | equal split | kNN | 0.612 | 0.611 | 0.681 | 0.607 | 0.569 | 0.616 | 0.652 | 134 |
| setup_06_full_multimodal_real_level_times_extreme_percentile | real level times | LSTM | 0.519 | 0.484 | 0.534 | 0.486 | 0.274 | 0.531 | 0.739 | 131 |
| setup_06_full_multimodal_real_level_times_extreme_percentile_classical | real level times | kNN | 0.580 | 0.563 | 0.651 | 0.581 | 0.403 | 0.580 | 0.739 | 131 |
| setup_07_5min_window_extreme_percentile | equal split | MLP | 0.512 | 0.494 | 0.532 | 0.517 | 0.682 | 0.500 | 0.333 | 43 |
| setup_07_5min_window_extreme_percentile_classical | equal split | LogisticRegression | 0.628 | 0.628 | 0.641 | 0.636 | 0.636 | 0.619 | 0.619 | 43 |
| setup_07_5min_window_real_level_times_extreme_percentile | real level times | MLP | 0.512 | 0.494 | 0.532 | 0.517 | 0.682 | 0.500 | 0.333 | 43 |
| setup_07_5min_window_real_level_times_extreme_percentile_classical | real level times | LogisticRegression | 0.628 | 0.628 | 0.641 | 0.636 | 0.636 | 0.619 | 0.619 | 43 |
| setup_09_heartpy_extreme_percentile | equal split | MLP | 0.489 | 0.484 | 0.405 | 0.519 | 0.560 | 0.450 | 0.409 | 47 |
| setup_09_heartpy_extreme_percentile_classical | equal split | SVM | 0.468 | 0.467 | 0.438 | 0.500 | 0.400 | 0.444 | 0.545 | 47 |
| setup_09_heartpy_real_level_times_extreme_percentile | real level times | MLP | 0.489 | 0.484 | 0.405 | 0.519 | 0.560 | 0.450 | 0.409 | 47 |
| setup_09_heartpy_real_level_times_extreme_percentile_classical | real level times | SVM | 0.468 | 0.467 | 0.438 | 0.500 | 0.400 | 0.444 | 0.545 | 47 |
| setup_10_all_models_extreme_percentile | equal split | LSTM | 0.511 | 0.507 | 0.527 | 0.538 | 0.560 | 0.476 | 0.455 | 47 |
| setup_10_all_models_extreme_percentile_classical | equal split | kNN | 0.489 | 0.470 | 0.495 | 0.516 | 0.640 | 0.438 | 0.318 | 47 |
| setup_11_raw_geq_without_time_distortion_extreme_percentile | equal split | MLP | 0.451 | 0.437 | 0.430 | 0.375 | 0.326 | 0.500 | 0.554 | 102 |
| setup_11_raw_geq_without_time_distortion_extreme_percentile_classical | equal split | RandomForest | 0.529 | 0.529 | 0.537 | 0.481 | 0.565 | 0.583 | 0.500 | 102 |
| setup_11_raw_geq_without_time_distortion_real_level_times_extreme_percentile | real level times | MLP | 0.574 | 0.491 | 0.458 | 0.444 | 0.211 | 0.605 | 0.821 | 94 |
| setup_11_raw_geq_without_time_distortion_real_level_times_extreme_percentile_classical | real level times | LogisticRegression | 0.479 | 0.465 | 0.469 | 0.366 | 0.395 | 0.566 | 0.536 | 94 |
| setup_12_biraffe2_baseline_correction_extreme_percentile | equal split | MLP | 0.640 | 0.631 | 0.730 | 0.620 | 0.772 | 0.675 | 0.500 | 111 |
| setup_12_biraffe2_baseline_correction_extreme_percentile_classical | equal split | SVM | 0.730 | 0.727 | 0.790 | 0.708 | 0.807 | 0.761 | 0.648 | 111 |
| setup_12_biraffe2_baseline_correction_real_level_times_extreme_percentile | real level times | MLP | 0.619 | 0.615 | 0.724 | 0.628 | 0.529 | 0.613 | 0.704 | 105 |
| setup_12_biraffe2_baseline_correction_real_level_times_extreme_percentile_classical | real level times | RandomForest | 0.676 | 0.675 | 0.726 | 0.644 | 0.745 | 0.717 | 0.611 | 105 |

## Supervisor summary: setups with subject-level accuracy > 0.68 or AUC > 0.68

### Accuracy > 0.68

#### setup_12_biraffe2_baseline_correction_extreme_percentile_classical (extreme percentile (equal split) — SVM, accuracy=0.730, AUC=0.790, n=111)

- **Data / modalities:** ECG
- **Levels as pseudo-subjects:** True
- **Classifier:** SVM
- **Outlier strategy:** train_only
- **Z-standardisation:** True
- **Baseline correction:** change_score (from procedure: True)
- **Window / step:** 60s / 30s
- **Label method:** extreme_percentile (margin=0.0)
- **Real level timestamps:** False
- **Models tested in config:** RandomForest, XGBoost, SVM, LogisticRegression, kNN

#### setup_08b_irshad_physf_ecg_only (Irshad/PhySF (no outlier removal) — RandomForest, accuracy=0.720, AUC=0.692, n=25)

- **Data / modalities:** ECG
- **Levels as pseudo-subjects:** False
- **Classifier:** RandomForest
- **Outlier strategy:** none
- **Z-standardisation:** True
- **Baseline correction:** none (from procedure: False)
- **Window / step:** 60s / 30s
- **Label method:** filename (margin=0.0)
- **Real level timestamps:** False
- **Models tested in config:** RandomForest, SVM, kNN, LogisticRegression, XGBoost, MLP, LSTM, CNN1D

### AUC > 0.68

#### setup_08_irshad_physf (Irshad/PhySF (IQR outlier removal (train_only)) — RandomForest, accuracy=0.667, AUC=0.889, n=9)

- **Data / modalities:** ECG, EDA, EEG
- **Levels as pseudo-subjects:** False
- **Classifier:** RandomForest
- **Outlier strategy:** train_only
- **Z-standardisation:** True
- **Baseline correction:** none (from procedure: False)
- **Window / step:** 60s / 30s
- **Label method:** filename (margin=0.0)
- **Real level timestamps:** False
- **Models tested in config:** RandomForest, SVM, kNN, LogisticRegression, XGBoost, MLP, LSTM, CNN1D

#### setup_12_biraffe2_baseline_correction_extreme_percentile_classical (extreme percentile (equal split) — SVM, accuracy=0.730, AUC=0.790, n=111)

- **Data / modalities:** ECG
- **Levels as pseudo-subjects:** True
- **Classifier:** SVM
- **Outlier strategy:** train_only
- **Z-standardisation:** True
- **Baseline correction:** change_score (from procedure: True)
- **Window / step:** 60s / 30s
- **Label method:** extreme_percentile (margin=0.0)
- **Real level timestamps:** False
- **Models tested in config:** RandomForest, XGBoost, SVM, LogisticRegression, kNN

#### setup_08_irshad_physf (Irshad/PhySF (IQR outlier removal (train_only)) — XGBoost, accuracy=0.667, AUC=0.778, n=9)

- **Data / modalities:** ECG, EDA, EEG
- **Levels as pseudo-subjects:** False
- **Classifier:** XGBoost
- **Outlier strategy:** train_only
- **Z-standardisation:** True
- **Baseline correction:** none (from procedure: False)
- **Window / step:** 60s / 30s
- **Label method:** filename (margin=0.0)
- **Real level timestamps:** False
- **Models tested in config:** RandomForest, SVM, kNN, LogisticRegression, XGBoost, MLP, LSTM, CNN1D

#### setup_12_biraffe2_baseline_correction_extreme_percentile (extreme percentile (equal split) — MLP, accuracy=0.640, AUC=0.730, n=111)

- **Data / modalities:** ECG
- **Levels as pseudo-subjects:** True
- **Classifier:** MLP
- **Outlier strategy:** train_only
- **Z-standardisation:** True
- **Baseline correction:** change_score (from procedure: True)
- **Window / step:** 60s / 30s
- **Label method:** extreme_percentile (margin=0.0)
- **Real level timestamps:** False
- **Models tested in config:** MLP, LSTM, CNN1D

#### setup_12_biraffe2_baseline_correction_real_level_times_extreme_percentile_classical (extreme percentile (real level times) — RandomForest, accuracy=0.676, AUC=0.726, n=105)

- **Data / modalities:** ECG
- **Levels as pseudo-subjects:** True
- **Classifier:** RandomForest
- **Outlier strategy:** train_only
- **Z-standardisation:** True
- **Baseline correction:** change_score (from procedure: True)
- **Window / step:** 60s / 30s
- **Label method:** extreme_percentile (margin=0.0)
- **Real level timestamps:** True
- **Models tested in config:** RandomForest, XGBoost, SVM, LogisticRegression, kNN

#### setup_12_biraffe2_baseline_correction_real_level_times_extreme_percentile (extreme percentile (real level times) — MLP, accuracy=0.619, AUC=0.724, n=105)

- **Data / modalities:** ECG
- **Levels as pseudo-subjects:** True
- **Classifier:** MLP
- **Outlier strategy:** train_only
- **Z-standardisation:** True
- **Baseline correction:** change_score (from procedure: True)
- **Window / step:** 60s / 30s
- **Label method:** extreme_percentile (margin=0.0)
- **Real level timestamps:** True
- **Models tested in config:** MLP, LSTM, CNN1D

#### setup_08b_irshad_physf_ecg_only (Irshad/PhySF (IQR outlier removal (train_only)) — RandomForest, accuracy=0.680, AUC=0.712, n=25)

- **Data / modalities:** ECG
- **Levels as pseudo-subjects:** False
- **Classifier:** RandomForest
- **Outlier strategy:** train_only
- **Z-standardisation:** True
- **Baseline correction:** none (from procedure: False)
- **Window / step:** 60s / 30s
- **Label method:** filename (margin=0.0)
- **Real level timestamps:** False
- **Models tested in config:** RandomForest, SVM, kNN, LogisticRegression, XGBoost, MLP, LSTM, CNN1D

#### setup_08b_irshad_physf_ecg_only (Irshad/PhySF (no outlier removal) — RandomForest, accuracy=0.720, AUC=0.692, n=25)

- **Data / modalities:** ECG
- **Levels as pseudo-subjects:** False
- **Classifier:** RandomForest
- **Outlier strategy:** none
- **Z-standardisation:** True
- **Baseline correction:** none (from procedure: False)
- **Window / step:** 60s / 30s
- **Label method:** filename (margin=0.0)
- **Real level timestamps:** False
- **Models tested in config:** RandomForest, SVM, kNN, LogisticRegression, XGBoost, MLP, LSTM, CNN1D

#### setup_12_biraffe2_baseline_correction_grid_search (grid search — RandomForest, accuracy=0.647, AUC=0.681, n=207)

- **Data / modalities:** ECG
- **Levels as pseudo-subjects:** True
- **Classifier:** RandomForest
- **Outlier strategy:** train_only
- **Z-standardisation:** True
- **Baseline correction:** change_score (from procedure: True)
- **Window / step:** 60s / 30s
- **Label method:** median_split (margin=0.0)
- **Real level timestamps:** True
- **Models tested in config:** RandomForest

#### setup_06_full_multimodal_extreme_percentile_classical (extreme percentile (equal split) — kNN, accuracy=0.612, AUC=0.681, n=134)

- **Data / modalities:** ECG, EDA, FACE
- **Levels as pseudo-subjects:** True
- **Classifier:** kNN
- **Outlier strategy:** none
- **Z-standardisation:** True
- **Baseline correction:** none (from procedure: False)
- **Window / step:** 60s / 30s
- **Label method:** extreme_percentile (margin=0.0)
- **Real level timestamps:** False
- **Models tested in config:** RandomForest, XGBoost, SVM, LogisticRegression, kNN
