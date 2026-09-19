# Permutation Importance by Feature Group

Group averages of per-feature permutation importance.

| Experiment | Model | Group | Mean Importance | Std | n_features | Top Feature | Top Score |
|------------|-------|-------|-----------------|-----|------------|-------------|-----------|
| setup_01c_biraffe2_ecg_levels_as_subjects | RandomForest | ECG | 0.007 | 0.004 | 12 | RMSSD | 0.015 |
| setup_12_biraffe2_baseline_correction | LogisticRegression | ECG | 0.007 | 0.007 | 12 | LF | 0.023 |
| setup_12_biraffe2_baseline_correction_real_level_times | LogisticRegression | ECG | 0.005 | 0.006 | 12 | LF | 0.018 |
| setup_12_biraffe2_baseline_correction | kNN | ECG | 0.004 | 0.004 | 12 | SDNN | 0.011 |
| setup_06_full_multimodal | RandomForest | EDA | 0.004 | 0.003 | 6 | SCL_std | 0.008 |
| setup_01c_biraffe2_ecg_levels_as_subjects | XGBoost | ECG | 0.004 | 0.004 | 12 | pNN50 | 0.013 |
| setup_01_biraffe2_ecg_baseline_avg_levels | RandomForest | ECG | 0.004 | 0.004 | 12 | SDNN | 0.012 |
| setup_01_biraffe2_ecg_baseline_avg_levels_real_level_times | RandomForest | ECG | 0.004 | 0.004 | 12 | SDNN | 0.012 |
| setup_06_full_multimodal | RandomForest | ECG | 0.004 | 0.003 | 12 | DFA_alpha1 | 0.007 |
| setup_03_without_time_distortion_real_level_times | RandomForest | ECG | 0.003 | 0.004 | 12 | pNN50 | 0.009 |
| setup_11_raw_geq_without_time_distortion_real_level_times | RandomForest | ECG | 0.003 | 0.004 | 12 | pNN50 | 0.009 |
| setup_07_5min_window | RandomForest | ECG | 0.003 | 0.006 | 12 | HF | 0.013 |
| setup_07_5min_window_real_level_times | RandomForest | ECG | 0.003 | 0.006 | 12 | HF | 0.013 |
| setup_01c_biraffe2_ecg_levels_as_subjects_real_level_times | LogisticRegression | ECG | 0.003 | 0.007 | 12 | LF | 0.020 |
| setup_01g_levels_as_subjects_per_subject_norm_real_level_times | LogisticRegression | ECG | 0.003 | 0.007 | 12 | LF | 0.020 |
| setup_12_biraffe2_baseline_correction | SVM | ECG | 0.002 | 0.005 | 12 | LF | 0.013 |
| setup_01c_biraffe2_ecg_levels_as_subjects | LogisticRegression | ECG | 0.002 | 0.008 | 12 | TP | 0.023 |
| setup_01e_per_subject_normalization | RandomForest | ECG | 0.002 | 0.005 | 12 | RMSSD | 0.010 |
| setup_01e_per_subject_normalization_real_level_times | RandomForest | ECG | 0.002 | 0.005 | 12 | RMSSD | 0.010 |
| setup_11_raw_geq_without_time_distortion_real_level_times | LogisticRegression | ECG | 0.002 | 0.008 | 12 | TP | 0.019 |
| setup_06_full_multimodal_real_level_times | RandomForest | EDA | 0.002 | 0.002 | 6 | SCL_std | 0.005 |
| setup_06_full_multimodal | RandomForest | FACE | 0.002 | 0.002 | 25 | CONTEMPT_mean | 0.007 |
| setup_01g_levels_as_subjects_per_subject_norm | LogisticRegression | ECG | 0.002 | 0.004 | 12 | TP | 0.013 |
| setup_06_full_multimodal_real_level_times | RandomForest | FACE | 0.002 | 0.002 | 25 | SADNESS_max | 0.005 |
| setup_06_full_multimodal_real_level_times | RandomForest | ECG | 0.001 | 0.002 | 12 | LF_HF | 0.004 |
| setup_04_no_zscore | RandomForest | ECG | 0.001 | 0.004 | 12 | hr_mean | 0.007 |
| setup_04_no_zscore_real_level_times | RandomForest | ECG | 0.001 | 0.004 | 12 | hr_mean | 0.007 |
| setup_01c_biraffe2_ecg_levels_as_subjects | kNN | ECG | 0.001 | 0.003 | 12 | DFA_alpha1 | 0.006 |
| setup_11_raw_geq_without_time_distortion | XGBoost | ECG | 0.001 | 0.004 | 12 | LF_HF | 0.008 |
| setup_01f_shorter_step | RandomForest | ECG | 0.001 | 0.003 | 12 | HF | 0.003 |
| setup_01f_shorter_step_real_level_times | RandomForest | ECG | 0.001 | 0.003 | 12 | HF | 0.003 |
| setup_05_no_outlier | RandomForest | ECG | 0.001 | 0.002 | 12 | hr_mean | 0.006 |
| setup_05_no_outlier_real_level_times | RandomForest | ECG | 0.001 | 0.002 | 12 | hr_mean | 0.006 |
| setup_01g_levels_as_subjects_per_subject_norm | XGBoost | ECG | 0.000 | 0.004 | 12 | HF | 0.010 |
| setup_12_biraffe2_baseline_correction_real_level_times | XGBoost | ECG | 0.000 | 0.002 | 12 | TP | 0.004 |
| setup_01c_biraffe2_ecg_levels_as_subjects | SVM | ECG | 0.000 | 0.003 | 12 | DFA_alpha1 | 0.007 |
| setup_01_biraffe2_ecg_baseline | RandomForest | ECG | 0.000 | 0.004 | 12 | hr_mean | 0.005 |
| setup_01_biraffe2_ecg_baseline_real_level_times | RandomForest | ECG | 0.000 | 0.004 | 12 | hr_mean | 0.005 |
| setup_01c_biraffe2_ecg_levels_as_subjects_real_level_times | XGBoost | ECG | 0.000 | 0.004 | 12 | HF | 0.007 |
| setup_01g_levels_as_subjects_per_subject_norm_real_level_times | XGBoost | ECG | 0.000 | 0.004 | 12 | HF | 0.007 |
| setup_03_without_time_distortion | RandomForest | ECG | 0.000 | 0.004 | 12 | pNN50 | 0.007 |
| setup_11_raw_geq_without_time_distortion | RandomForest | ECG | 0.000 | 0.004 | 12 | pNN50 | 0.007 |
| setup_01g_levels_as_subjects_per_subject_norm | RandomForest | ECG | -0.001 | 0.004 | 12 | LF_HF | 0.006 |
| setup_01f_shorter_step | XGBoost | ECG | -0.001 | 0.003 | 12 | sample_entropy | 0.001 |
| setup_01f_shorter_step_real_level_times | XGBoost | ECG | -0.001 | 0.003 | 12 | sample_entropy | 0.001 |
| setup_01c_biraffe2_ecg_levels_as_subjects_real_level_times | RandomForest | ECG | -0.001 | 0.004 | 12 | RMSSD | 0.004 |
| setup_01g_levels_as_subjects_per_subject_norm_real_level_times | RandomForest | ECG | -0.001 | 0.004 | 12 | RMSSD | 0.004 |
| setup_12_biraffe2_baseline_correction_real_level_times | kNN | ECG | -0.002 | 0.006 | 12 | TP | 0.011 |
| setup_01c_biraffe2_ecg_levels_as_subjects_real_level_times | SVM | ECG | -0.002 | 0.004 | 12 | HF | 0.006 |
| setup_02_label_margin_01 | RandomForest | ECG | -0.002 | 0.003 | 12 | TP | 0.001 |
| setup_02_label_margin_01_real_level_times | RandomForest | ECG | -0.002 | 0.003 | 12 | TP | 0.001 |
| setup_01d_drop_unreliable_60s_features | XGBoost | ECG | -0.003 | 0.005 | 5 | sample_entropy | 0.003 |
| setup_01d_drop_unreliable_60s_features_real_level_times | XGBoost | ECG | -0.003 | 0.005 | 5 | sample_entropy | 0.003 |
| setup_12_biraffe2_baseline_correction_real_level_times | RandomForest | ECG | -0.003 | 0.003 | 12 | HF | 0.001 |
| setup_01e_per_subject_normalization | LogisticRegression | ECG | -0.003 | 0.003 | 12 | hr_mean | 0.001 |
| setup_01e_per_subject_normalization_real_level_times | LogisticRegression | ECG | -0.003 | 0.003 | 12 | hr_mean | 0.001 |
| setup_01c_biraffe2_ecg_levels_as_subjects_real_level_times | kNN | ECG | -0.003 | 0.004 | 12 | HF | 0.003 |
| setup_12_biraffe2_baseline_correction | RandomForest | ECG | -0.003 | 0.003 | 12 | LF_HF | 0.000 |
| setup_12_biraffe2_baseline_correction | XGBoost | ECG | -0.003 | 0.003 | 12 | DFA_alpha1 | 0.001 |
| setup_01e_per_subject_normalization | XGBoost | ECG | -0.004 | 0.004 | 12 | hr_mean | 0.002 |
| setup_01e_per_subject_normalization_real_level_times | XGBoost | ECG | -0.004 | 0.004 | 12 | hr_mean | 0.002 |
| setup_11_raw_geq_without_time_distortion_real_level_times | XGBoost | ECG | -0.004 | 0.004 | 12 | DFA_alpha2 | 0.000 |
| setup_12_biraffe2_baseline_correction_real_level_times | SVM | ECG | -0.005 | 0.004 | 12 | hr_mean | 0.001 |
| setup_01d_drop_unreliable_60s_features | RandomForest | ECG | -0.005 | 0.005 | 5 | sample_entropy | 0.000 |
| setup_01d_drop_unreliable_60s_features_real_level_times | RandomForest | ECG | -0.005 | 0.005 | 5 | sample_entropy | 0.000 |
| setup_09_heartpy | RandomForest | ECG | -0.009 | 0.004 | 4 | SDNN | -0.004 |
| setup_09_heartpy_real_level_times | RandomForest | ECG | -0.009 | 0.004 | 4 | SDNN | -0.004 |
| setup_11_raw_geq_without_time_distortion | LogisticRegression | ECG | -0.009 | 0.006 | 12 | VLF | 0.000 |
| setup_01f_shorter_step | LogisticRegression | ECG | -0.012 | 0.016 | 12 | hr_mean | 0.002 |
| setup_01f_shorter_step_real_level_times | LogisticRegression | ECG | -0.012 | 0.016 | 12 | hr_mean | 0.002 |
| setup_01d_drop_unreliable_60s_features | LogisticRegression | ECG | -0.013 | 0.014 | 5 | hr_mean | -0.000 |
| setup_01d_drop_unreliable_60s_features_real_level_times | LogisticRegression | ECG | -0.013 | 0.014 | 5 | hr_mean | -0.000 |

*Generated on Code*