# Ablation Comparison Table

Subject-level metrics. Best model per experiment is selected by AUC.

| Experiment | Best Model | Accuracy | F1 | AUC | n | Grid-Search Model | Grid-Search AUC | Extreme-Percentile Model | Extreme-Percentile AUC | Extreme-Percentile n |
|------------|------------|----------|----|-----|---|-------------------|-------------------|--------------------------|------------------------|----------------------|
| setup_01_biraffe2_ecg_baseline | CNN1D | 0.394 | 0.383 | 0.290 | 99 |  | — | LSTM | 0.527 | 47 |
| setup_01_biraffe2_ecg_baseline_avg_levels | LSTM | 0.495 | 0.489 | 0.389 | 99 |  | — | CNN1D | 0.290 | 40 |
| setup_01c_biraffe2_ecg_levels_as_subjects | CNN1D | 0.538 | 0.528 | 0.556 | 247 |  | — | MLP | 0.495 | 120 |
| setup_01d_drop_unreliable_60s_features | LSTM | 0.505 | 0.488 | 0.396 | 99 |  | — | LSTM | 0.305 | 43 |
| setup_01e_per_subject_normalization | CNN1D | 0.461 | 0.426 | 0.377 | 102 |  | — | CNN1D | 0.526 | 44 |
| setup_01f_shorter_step | CNN1D | 0.495 | 0.486 | 0.401 | 99 |  | — | LSTM | 0.318 | 43 |
| setup_01g_levels_as_subjects_per_subject_norm | MLP | 0.525 | 0.525 | 0.539 | 451 |  | — | MLP | 0.491 | 226 |
| setup_02_label_margin_01 | CNN1D | 0.424 | 0.392 | 0.335 | 92 |  | — | LSTM | 0.527 | 47 |
| setup_03_without_time_distortion | MLP | 0.577 | 0.568 | 0.587 | 260 |  | — | MLP | 0.430 | 102 |
| setup_04_no_zscore | CNN1D | 0.394 | 0.383 | 0.290 | 99 |  | — | LSTM | 0.527 | 47 |
| setup_05_no_outlier | CNN1D | 0.382 | 0.379 | 0.310 | 102 |  | — | CNN1D | 0.416 | 48 |
| setup_06_full_multimodal | CNN1D | 0.564 | 0.554 | 0.561 | 273 | RandomForest | 0.623 | LSTM | 0.605 | 134 |
| setup_07_5min_window | CNN1D | 0.411 | 0.389 | 0.292 | 90 |  | — | MLP | 0.532 | 43 |
| setup_09_heartpy | MLP | 0.420 | 0.408 | 0.376 | 100 |  | — | MLP | 0.405 | 47 |
| setup_11_raw_geq_without_time_distortion | MLP | 0.577 | 0.568 | 0.587 | 260 | LogisticRegression | 0.582 | MLP | 0.430 | 102 |
| setup_12_biraffe2_baseline_correction | MLP | 0.628 | 0.627 | 0.677 | 223 | RandomForest | 0.681 | MLP | 0.730 | 111 |

*Grid-search results are for classical classifiers only. Extreme-percentile uses bottom 20 % / top 20 % labels.*