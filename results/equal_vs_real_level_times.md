# Equal Split vs. Real Level Timestamps

Side-by-side subject-level AUC comparison. The higher AUC in each row is bolded.

| Setup | Equal Split Model | Equal Split AUC | Equal Split n | Real Timestamps Model | Real Timestamps AUC | Real Timestamps n |
|-------|-------------------|-----------------|---------------|----------------------|---------------------|-------------------|
| setup_01_biraffe2_ecg_baseline | RandomForest | **0.356** | 99 | RandomForest | **0.356** | 99 |
| setup_01_biraffe2_ecg_baseline_avg_levels | RandomForest | **0.380** | 99 | RandomForest | **0.380** | 99 |
| setup_01c_biraffe2_ecg_levels_as_subjects | RandomForest | **0.628** | 247 | RandomForest | 0.558 | 226 |
| setup_01d_drop_unreliable_60s_features | RandomForest | **0.378** | 99 | RandomForest | **0.378** | 99 |
| setup_01e_per_subject_normalization | RandomForest | **0.472** | 102 | RandomForest | **0.472** | 102 |
| setup_01f_shorter_step | RandomForest | **0.411** | 99 | RandomForest | **0.411** | 99 |
| setup_01g_levels_as_subjects_per_subject_norm | RandomForest | **0.570** | 452 | RandomForest | 0.558 | 226 |
| setup_02_label_margin_01 | RandomForest | **0.384** | 92 | RandomForest | **0.384** | 92 |
| setup_03_without_time_distortion | RandomForest | **0.625** | 260 | RandomForest | 0.555 | 232 |
| setup_04_no_zscore | RandomForest | **0.357** | 99 | RandomForest | **0.357** | 99 |
| setup_05_no_outlier | RandomForest | **0.399** | 102 | RandomForest | **0.399** | 102 |
| setup_06_full_multimodal | RandomForest | 0.617 | 273 | RandomForest | **0.622** | 268 |
| setup_07_5min_window | RandomForest | **0.240** | 90 | RandomForest | **0.240** | 90 |
| setup_09_heartpy | RandomForest | **0.374** | 100 | RandomForest | **0.374** | 100 |
| setup_11_raw_geq_without_time_distortion | RandomForest | **0.625** | 260 | LogisticRegression | 0.576 | 232 |
| setup_12_biraffe2_baseline_correction | SVM | **0.676** | 223 | RandomForest | 0.664 | 207 |

*Generated from `ablation_comparison.csv` and `ablation_comparison_real_level_times.csv`.*