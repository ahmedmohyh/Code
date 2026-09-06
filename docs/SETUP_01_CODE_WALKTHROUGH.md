# Setup 01 Code Walkthrough

This document explains exactly what happens, file by file and function by
function, when you run the baseline Setup 01.

## Command

```bash
python scripts/run_experiment_fast.py --config config/setup_01_biraffe2_ecg_baseline.yaml --n-jobs -1
```

## Overview

The execution follows this chain:

```text
run_experiment_fast.py  main()
        ↓
load_config()                    [flow_lol/utils/config.py]
        ↓
run()                            [scripts/run_experiment_fast.py]
        ↓
load_biraffe2_data_fast()        [scripts/run_experiment_fast.py]
        ↓
BIRAFFE2Loader                   [flow_lol/data/loaders/biraffe2_loader.py]
        ↓
FlowLabeler                      [flow_lol/data/labelers/flow_labeler.py]
        ↓
_process_one_subject()           [scripts/run_experiment_fast.py, parallel]
        ↓
clean_ecg()                      [flow_lol/preprocessing/cleaners/ecg_cleaner.py]
WindowSegmenter                  [flow_lol/segmentation/window_segmenter.py]
extract_ecg_features()           [flow_lol/features/extractors/ecg_features.py]
features_to_matrix()             [flow_lol/features/feature_union.py]
impute_missing()                 [flow_lol/features/feature_union.py]
        ↓
run_loso_cv()                    [flow_lol/validation/loso_cv.py]
        ↓
RandomForest                     [flow_lol/models/classical.py]
        ↓
save_results()                   [flow_lol/reporting/ablation_table.py]
```

---

## 1. Load the config

**File:** `scripts/run_experiment_fast.py`  
**Function:** `main()`

- Reads `config/setup_01_biraffe2_ecg_baseline.yaml`.
- Calls `load_config()` from `flow_lol/utils/config.py`.
- Builds a Python dataclass `Config` containing all settings: dataset, label,
  preprocessing, segmentation, features, models, validation.
- Calls `run(config, n_jobs=-1)`.

For Setup 01 the relevant config values are:

| Config key | Value |
|------------|-------|
| `experiment_name` | `setup_01_biraffe2_ecg_baseline` |
| `dataset.score_column` | `GEQ-1-FLOW-2018` |
| `label.method` | `median_split` |
| `label.margin` | `0.0` |
| `preprocessing.cleaning_package` | `neurokit2` |
| `preprocessing.z_standardise` | `true` |
| `preprocessing.outlier_strategy` | `train_only` |
| `segmentation.window_length_s` | `60` |
| `segmentation.step_s` | `30` |
| `features.package` | `neurokit2` |
| `features.ecg.time` | `hr_mean`, `SDNN`, `RMSSD`, `pNN50` |
| `features.ecg.frequency` | `VLF`, `LF`, `HF`, `LF_HF`, `TP` |
| `features.ecg.nonlinear` | `sample_entropy`, `DFA_alpha1`, `DFA_alpha2` |
| `models.classical` | `RandomForest` |
| `validation.strategy` | `LOSO` |

---

## 2. Load data and create labels

**File:** `scripts/run_experiment_fast.py`  
**Function:** `load_biraffe2_data_fast()`

1. Creates a `BIRAFFE2Loader` from `flow_lol/data/loaders/biraffe2_loader.py`.
2. `_scan_archive()` scans `BIRAFFE2-biosigs.zip` and finds every
   `SUB<id>-BioSigs.csv`.
3. `_load_metadata()` reads `BIRAFFE2-metadata.csv` (semicolon-separated).
4. `list_subjects()` returns the 102 subjects that have both biosignals and a
   valid `GEQ-1-FLOW-2018` score.
5. `_load_label_from_metadata()` reads the flow score for each subject from the
   metadata dataframe.
6. `FlowLabeler` from `flow_lol/data/labelers/flow_labeler.py` is instantiated
   and `fit_transform()` is called on the 102 scores.

### What FlowLabeler does

- `fit()` computes median and IQR of all scores.
- `transform()` assigns:
  - `0 = low flow` for scores ≤ median,
  - `1 = high flow` for scores ≥ median,
  - `-1 = excluded` for scores inside the margin band (only relevant when margin > 0).
- For Setup 01 the margin is `0.0`, so no subject is excluded.
- Prints label distribution, e.g. `low=49, high=53, excluded=0`.

---

## 3. Cache biosignals locally

**File:** `scripts/run_experiment_fast.py`  
**Function:** `_cache_subject()`

- Extracts each needed `SUB<id>-BioSigs.csv` from the zip into `cache/biosigs/`.
- After this step the parallel workers read plain CSVs instead of contending for
  the same zip file.

---

## 4. Prepare windowing

**File:** `flow_lol/segmentation/window_segmenter.py`  
**Class:** `WindowSegmenter`

Created in `load_biraffe2_data_fast()` with:

- `window_length_s = 60`
- `step_s = 30`
- `sampling_rate = 1000` (1 kHz for BIRAFFE2)

`segment(signal)` cuts the continuous cleaned signal into overlapping windows:

```text
[s0 ... s59999], [s30000 ... s89999], [s60000 ... s119999], ...
```

---

## 5. Process each subject in parallel

**File:** `scripts/run_experiment_fast.py`  
**Function:** `_process_one_subject()`

Executed in parallel via `joblib.Parallel` across all CPU cores.

For each subject the following happens:

1. `loader.load_subject(sid)` loads the cached CSV into a pandas DataFrame.
2. `record["signal"]["ECG"].to_numpy(dtype=float)` extracts the raw ECG voltage
   as a 1-D numpy array.
3. `clean_ecg()` from `flow_lol/preprocessing/cleaners/ecg_cleaner.py` is
   called with `package="neurokit2"`.
   - `_clean_neurokit2()` runs `neurokit2.ecg_clean()` to remove noise and
     baseline drift.
4. `segmenter.segment(ecg_clean)` produces 60-second windows.
5. For every window `extract_ecg_features()` from
   `flow_lol/features/extractors/ecg_features.py` is called.

### What extract_ecg_features does (neurokit2 path)

**File:** `flow_lol/features/extractors/ecg_features.py`  
**Function:** `_extract_neurokit2()`

1. `nk.ecg_process(signal, sampling_rate=1000)` detects R-peaks.
2. `rri_ms = np.diff(peaks) / sampling_rate * 1000.0` converts peak indices to
   R-R intervals in milliseconds.
3. Computes time-domain features from the R-R intervals:
   - `hr_mean`: mean heart rate in bpm
   - `SDNN`: standard deviation of R-R intervals
   - `RMSSD`: root mean square of successive differences
   - `pNN50`: percentage of successive R-R differences > 50 ms
4. If enough R-peaks (≥ 30), computes frequency-domain features via
   `nk.hrv_frequency()`:
   - `VLF`, `LF`, `HF`, `LF_HF`, `TP`
5. If enough R-peaks, computes nonlinear features via `nk.hrv_nonlinear()`:
   - `sample_entropy`, `DFA_alpha1`, `DFA_alpha2`
6. Returns only the features requested in the config.

If a feature cannot be computed it becomes `NaN`.

### Back in _process_one_subject

6. `features_to_matrix()` from `flow_lol/features/feature_union.py` converts the
   list of per-window feature dictionaries into a 2-D numpy array of shape
   `(n_windows, 12)`.
7. `impute_missing()` replaces `NaN` values column-wise with the median.
   - Columns that are entirely `NaN` are filled with `0.0`.
8. `y = np.full(len(X), label)` creates one label vector where every window of
   this subject receives the same binary flow label.

The function returns `(sid, X, y, label, n_windows)`.

---

## 6. Collect per-subject matrices

**File:** `scripts/run_experiment_fast.py`  
**Function:** `load_biraffe2_data_fast()` (after parallel call)

- Collects all `(sid, X, y, ...)` tuples.
- Builds two dictionaries:
  - `X_by_subject[sid] = X`
  - `y_by_subject[sid] = y`
- Prints total number of windows and NaN statistics.

At this point the data structure is:

```python
X_by_subject = {
    103: array shape (121, 12),
    104: array shape (118, 12),
    ...
}
y_by_subject = {
    103: array of 121 zeros or ones,
    ...
}
```

---

## 7. LOSO cross-validation

**File:** `flow_lol/validation/loso_cv.py`  
**Function:** `run_loso_cv()`

For every subject as test fold:

1. All other subjects become the training set.
2. `_run_single_fold()` is called.

### Inside _run_single_fold

**File:** `flow_lol/validation/loso_cv.py`  
**Function:** `_run_single_fold()`

1. **Outlier handling** with `OutlierHandler(strategy="train_only")`.
   - Outlier thresholds are computed only on the training windows.
   - The same thresholds are applied to the test windows.
   - This prevents leakage from test to train.
2. **Z-standardisation** with `ZStandardiser`.
   - Mean and standard deviation are computed on training windows.
   - The same scaler is applied to the test windows.
3. **Imputation** with `impute_missing()` again.
4. **Drop all-NaN columns** so scikit-learn does not crash.
5. **Model training**:
   - `model_builder()` creates a `RandomForestClassifier`.
   - `model.fit(X_train, y_train)`.
6. **Prediction**:
   - `model.predict(X_test)` → class labels per window.
   - `model.predict_proba(X_test)` → probabilities per window (if available).
7. **Metrics** computed per window:
   - accuracy, F1 macro, precision/recall per class, AUC, inference time.

### Why subject-level aggregation is needed

In BIRAFFE2 each subject has exactly one global label. If AUC were computed on
window-level test folds, every test fold would contain only one class, making
AUC undefined.

Therefore `_run_single_fold()` also computes:

- `subject_true`: the subject's real label
- `subject_pred`: majority vote of window predictions
- `subject_score`: mean predicted probability for class 1

After all folds, `_subject_level_aggregate()` builds one prediction per subject
and computes the final subject-level accuracy, F1 and AUC.

---

## 8. Print and save results

**File:** `scripts/run_experiment_fast.py`  
**Function:** `run()`

After LOSO CV the runner prints two result blocks:

```text
Window-level: Accuracy=0.447 F1=0.302 AUC=nan
Subject-level: Accuracy=0.394 F1=0.376 AUC=0.336 n=99
```

- `Window-level`: average over all windows of all folds.
- `Subject-level`: one prediction per subject, the valid AUC.

Then `save_results()` from `flow_lol/reporting/ablation_table.py` writes:

```text
results/setup_01_biraffe2_ecg_baseline/
├── results.json
└── config.yaml
```

`results.json` contains fold results, window-level aggregate and subject-level
aggregate. `config.yaml` stores the exact configuration used.

---

## Summary table

| Step | File | Function / Class | What it does |
|------|------|------------------|--------------|
| Parse CLI + load config | `scripts/run_experiment_fast.py` | `main()` | Reads YAML, builds `Config` |
| Orchestrate run | `scripts/run_experiment_fast.py` | `run()` | Calls loader, LOSO CV, saves results |
| Load subjects + labels | `scripts/run_experiment_fast.py` | `load_biraffe2_data_fast()` | Builds `X_by_subject`, `y_by_subject` |
| Find biosignals in zip | `flow_lol/data/loaders/biraffe2_loader.py` | `BIRAFFE2Loader._scan_archive()` | Lists `SUB<id>-BioSigs.csv` |
| Read metadata CSV | `flow_lol/data/loaders/biraffe2_loader.py` | `BIRAFFE2Loader._load_metadata()` | Loads GEQ scores |
| Return valid subjects | `flow_lol/data/loaders/biraffe2_loader.py` | `BIRAFFE2Loader.list_subjects()` | Filters 102 valid subjects |
| Load one subject | `flow_lol/data/loaders/biraffe2_loader.py` | `BIRAFFE2Loader.load_subject()` | Reads CSV, returns signal + label |
| Create binary labels | `flow_lol/data/labelers/flow_labeler.py` | `FlowLabeler.fit_transform()` | Median split → 0/1 labels |
| Cache zip contents | `scripts/run_experiment_fast.py` | `_cache_subject()` | Extracts CSVs to `cache/biosigs/` |
| Cut signal into windows | `flow_lol/segmentation/window_segmenter.py` | `WindowSegmenter.segment()` | 60 s windows, 30 s step |
| Per-subject processing | `scripts/run_experiment_fast.py` | `_process_one_subject()` | Clean, segment, extract, impute |
| Clean ECG | `flow_lol/preprocessing/cleaners/ecg_cleaner.py` | `clean_ecg()` | Calls `neurokit2.ecg_clean()` |
| Extract HRV features | `flow_lol/features/extractors/ecg_features.py` | `extract_ecg_features()` | R-peaks → R-R → HRV features |
| Build feature matrix | `flow_lol/features/feature_union.py` | `features_to_matrix()` | Dicts → numpy matrix |
| Impute NaN | `flow_lol/features/feature_union.py` | `impute_missing()` | Median imputation, all-NaN → 0 |
| LOSO CV | `flow_lol/validation/loso_cv.py` | `run_loso_cv()` | One fold per subject |
| One fold | `flow_lol/validation/loso_cv.py` | `_run_single_fold()` | Outliers, z-score, train, predict |
| Subject aggregation | `flow_lol/validation/loso_cv.py` | `_subject_level_aggregate()` | One label/prediction per subject |
| Build classifier | `flow_lol/models/classical.py` | `build_classifier()` | Returns `RandomForestClassifier` |
| Save results | `flow_lol/reporting/ablation_table.py` | `save_results()` | Writes JSON + config YAML |
