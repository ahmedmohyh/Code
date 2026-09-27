# Equal Split vs. Real Level Timestamps

Side-by-side subject-level AUC comparison for setups that use the **pseudo-subject design** (i.e. real subject ID × 1000 + level index). Setups that average the three game levels into one record per subject (n ≈ 99 or 102) are excluded, because they do not compare the same subject representation.

The table also shows the effect of the **extreme percentile** label split (bottom 20 % vs. top 20 %). The higher AUC in each row is bolded.

| Setup | Equal Split Model | Equal Split AUC | Equal Split n | Real Timestamps Model | Real Timestamps AUC | Real Timestamps n | Equal Extreme Model | Equal Extreme AUC | Equal Extreme n | Real Extreme Model | Real Extreme AUC | Real Extreme n |
|-------|-------------------|-----------------|---------------|----------------------|---------------------|-------------------|---------------------|-------------------|-----------------|--------------------|------------------|----------------|
| setup_01c_biraffe2_ecg_levels_as_subjects | **RandomForest** | 0.628 | 247 | RandomForest | 0.558 | 226 | MLP | 0.495 | 120 | CNN1D | 0.431 | 113 |
| setup_01g_levels_as_subjects_per_subject_norm | **RandomForest** | 0.570 | 452 | RandomForest | 0.558 | 226 | MLP | 0.491 | 226 | CNN1D | 0.431 | 113 |
| setup_02_label_margin_01 | **RandomForest** | 0.384 | 92 | **RandomForest** | 0.384 | 92 | LSTM | 0.527 | 47 | LSTM | 0.527 | 47 |
| setup_03_without_time_distortion | **RandomForest** | 0.625 | 260 | RandomForest | 0.555 | 232 | MLP | 0.430 | 102 | MLP | 0.458 | 94 |
| setup_06_full_multimodal | RandomForest | 0.617 | 273 | **RandomForest** | 0.622 | 268 | LSTM | 0.605 | 134 | LSTM | 0.534 | 131 |
| setup_07_5min_window | **RandomForest** | 0.240 | 90 | **RandomForest** | 0.240 | 90 | MLP | 0.532 | 43 | MLP | 0.532 | 43 |
| setup_09_heartpy | **RandomForest** | 0.374 | 100 | **RandomForest** | 0.374 | 100 | MLP | 0.405 | 47 | MLP | 0.405 | 47 |
| setup_11_raw_geq_without_time_distortion | **RandomForest** | 0.625 | 260 | RandomForest | 0.576 | 232 | MLP | 0.430 | 102 | MLP | 0.458 | 94 |
| setup_12_biraffe2_baseline_correction | **SVM** | 0.676 | 223 | RandomForest | 0.664 | 207 | MLP | 0.730 | 111 | MLP | 0.724 | 105 |

*Generated from `ablation_comparison.csv` and `ablation_comparison_real_level_times.csv`, filtered to n ∉ {99, 102}, and extended with extreme-percentile results.*