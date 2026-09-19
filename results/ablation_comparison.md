# Ablation Comparison Table

Subject-level metrics. Best model per experiment is selected by AUC.

| Experiment | Best Model | Accuracy | F1 | AUC | n |
|------------|------------|----------|----|-----|---|
| setup_01_biraffe2_ecg_baseline | RandomForest | 0.404 | 0.388 | 0.356 | 99 |
| setup_01_biraffe2_ecg_baseline_avg_levels | RandomForest | 0.455 | 0.453 | 0.380 | 99 |
| setup_01_biraffe2_ecg_baseline_avg_levels_real_level_times | RandomForest | 0.455 | 0.453 | 0.380 | 99 |
| setup_01_biraffe2_ecg_baseline_real_level_times | RandomForest | 0.404 | 0.388 | 0.356 | 99 |
| setup_01c_biraffe2_ecg_levels_as_subjects | RandomForest | 0.599 | 0.599 | 0.628 | 247 |
| setup_01c_biraffe2_ecg_levels_as_subjects_real_level_times | RandomForest | 0.540 | 0.525 | 0.558 | 226 |
| setup_01d_drop_unreliable_60s_features | RandomForest | 0.434 | 0.434 | 0.378 | 99 |
| setup_01d_drop_unreliable_60s_features_real_level_times | RandomForest | 0.434 | 0.434 | 0.378 | 99 |
| setup_01e_per_subject_normalization | RandomForest | 0.500 | 0.496 | 0.472 | 102 |
| setup_01e_per_subject_normalization_real_level_times | RandomForest | 0.500 | 0.496 | 0.472 | 102 |
| setup_01f_shorter_step | RandomForest | 0.455 | 0.454 | 0.411 | 99 |
| setup_01f_shorter_step_real_level_times | RandomForest | 0.455 | 0.454 | 0.411 | 99 |
| setup_01g_levels_as_subjects_per_subject_norm | RandomForest | 0.549 | 0.548 | 0.570 | 452 |
| setup_01g_levels_as_subjects_per_subject_norm_real_level_times | RandomForest | 0.540 | 0.525 | 0.558 | 226 |
| setup_02_label_margin_01 | RandomForest | 0.446 | 0.415 | 0.384 | 92 |
| setup_02_label_margin_01_real_level_times | RandomForest | 0.446 | 0.415 | 0.384 | 92 |
| setup_03_without_time_distortion | RandomForest | 0.600 | 0.598 | 0.625 | 260 |
| setup_03_without_time_distortion_real_level_times | RandomForest | 0.612 | 0.593 | 0.555 | 232 |
| setup_04_no_zscore | RandomForest | 0.394 | 0.383 | 0.357 | 99 |
| setup_04_no_zscore_real_level_times | RandomForest | 0.394 | 0.383 | 0.357 | 99 |
| setup_05_no_outlier | RandomForest | 0.451 | 0.446 | 0.399 | 102 |
| setup_05_no_outlier_real_level_times | RandomForest | 0.451 | 0.446 | 0.399 | 102 |
| setup_06_full_multimodal | RandomForest | 0.612 | 0.611 | 0.617 | 273 |
| setup_06_full_multimodal_real_level_times | RandomForest | 0.623 | 0.610 | 0.622 | 268 |
| setup_07_5min_window | RandomForest | 0.344 | 0.330 | 0.240 | 90 |
| setup_07_5min_window_real_level_times | RandomForest | 0.344 | 0.330 | 0.240 | 90 |
| setup_09_heartpy | RandomForest | 0.420 | 0.420 | 0.374 | 100 |
| setup_09_heartpy_real_level_times | RandomForest | 0.420 | 0.420 | 0.374 | 100 |
| setup_11_raw_geq_without_time_distortion | RandomForest | 0.600 | 0.598 | 0.625 | 260 |
| setup_11_raw_geq_without_time_distortion_real_level_times | LogisticRegression | 0.547 | 0.546 | 0.576 | 232 |
| setup_12_biraffe2_baseline_correction | SVM | 0.637 | 0.637 | 0.676 | 223 |
| setup_12_biraffe2_baseline_correction_real_level_times | RandomForest | 0.618 | 0.617 | 0.664 | 207 |

*Generated on Code*