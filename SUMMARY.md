# Implementation Summary

**Date:** 2026-09-09
**Repo:** `C:\Users\user\Downloads\Masterthesis\Code`
**Branch:** `master`

## What was done

### 1. Repository setup
- Initialised Git repository in `C:\Users\user\Downloads\Masterthesis\Code`.
- Added `.gitignore` that ignores root-level `/data/` and `/models/` but **not** `flow_lol/data` or `flow_lol/models`.
- Created `requirements.txt`, `environment.yml` and `README.md`.

### 2. Package structure
Created the `flow_lol` package with the following modules:

```text
flow_lol/
├── data/
│   ├── loaders/biraffe2_loader.py       # reads BIRAFFE2-biosigs.zip + metadata.csv
│   └── labelers/flow_labeler.py         # median split, margin band, Time-Distortion variants
├── preprocessing/
│   ├── cleaners/ecg_cleaner.py          # NeuroKit2 / heartpy / biosppy adapters
│   ├── cleaners/eda_cleaner.py          # EDA tonic/phasic decomposition
│   ├── cleaners/eeg_cleaner.py          # MNE-Python filter stub
│   ├── normaliser.py                    # z-standardisation (train/test per fold)
│   ├── outlier_handler.py               # none / train-only / full-data strategies
│   └── baseline_corrector.py            # none / change_score / quotient
├── segmentation/window_segmenter.py     # 60 s sliding vs 5 min fixed
├── features/
│   ├── extractors/ecg_features.py       # time/frequency/nonlinear HRV features
│   ├── extractors/eda_features.py       # SCL / SCR features
│   ├── extractors/eeg_features.py       # band-power features
│   ├── extractors/webcam_features.py    # emotion probability features
│   └── feature_union.py                 # merge + impute feature matrices
├── models/
│   ├── classical.py                     # SVM, RF, XGBoost, k-NN
│   └── deep.py                          # PyTorch MLP / LSTM / 1D-CNN wrappers
├── validation/
│   ├── loso_cv.py                       # leave-one-subject-out cross-validation
│   ├── metrics.py                       # accuracy, F1, per-class P/R, AUC, inference time
│   └── permutation.py (inside metrics.py) # feature permutation importance
├── reporting/ablation_table.py        # save metrics + config per run
└── utils/config.py                      # dataclass-based config loader
```

### 3. Config-driven design
- Created `config/base.yaml` as a template.
- Generated 10 ablation setup configs:

| # | Config | What it changes | Supervisor comment addressed |
|---|--------|-----------------|------------------------------|
| 01 | `setup_01_biraffe2_ecg_baseline.yaml` | BIRAFFE2 ECG-only, RF, 60 s | Baseline |
| 02 | `setup_02_label_margin_01.yaml` | margin band = 0.1 | Comment 1 |
| 03 | `setup_03_without_time_distortion.yaml` | drops Time Distortion item | Comment 3 |
| 04 | `setup_04_no_zscore.yaml` | z-standardisation off | Comment 2 |
| 05 | `setup_05_no_outlier.yaml` | no outlier removal | Comment 8 |
| 06 | `setup_06_full_multimodal.yaml` | ECG + EDA + webcam | Comment 12 (contrast) |
| 07 | `setup_07_5min_window.yaml` | 5-minute fixed window | Comment 4 |
| 08 | `setup_08_irshad_physf.yaml` | Irshad/PhySF + baseline correction | Comments 5, 9 |
| 09 | `setup_09_heartpy.yaml` | heartpy cleaning/features | Comments 6, 7 |
| 10 | `setup_10_all_models.yaml` | RF/SVM/kNN/XGB + LSTM | Comments 0, 10 (deep models stub, perm. not wired) |
| 01c | `setup_01c_biraffe2_ecg_levels_as_subjects.yaml` | 3 pseudo-subjects per real subject | Tests time-varying labels |
| 01g | `setup_01g_levels_as_subjects_per_subject_norm.yaml` | 6 pseudo-subjects + per-subject norm | Diagnostic for 01c |

### 4. First working setup (Setup 01)
- `scripts/run_experiment.py` loads `setup_01_biraffe2_ecg_baseline.yaml`.
- Reads 102 BIRAFFE2 subjects from the biosig zip.
- Uses `GEQ-1-FLOW-2018` as the flow score.
- Cleans ECG with NeuroKit2.
- Segments into 60-second windows with 30-second step.
- Extracts time/frequency/nonlinear HRV features.
- Runs LOSO cross-validation with a Random Forest.
- Reports accuracy, F1, per-class precision/recall, AUC, inference time.

### 5. Tests
- `tests/test_loader.py` verifies the BIRAFFE2 loader and Flow labeler work without ML dependencies.

## What was completed since the last update

- ✅ Installed all Python dependencies.
- ✅ Added `scripts/run_experiment_fast.py` with parallel subject processing and parallel LOSO folds.
- ✅ Added progress bars for caching, feature extraction, and LOSO folds.
- ✅ Fixed NaN imputation in `flow_lol/features/feature_union.py` (all-NaN columns now filled with 0.0).
- ✅ Fixed config JSON serialization by converting dataclass config to plain dict.
- ✅ Ran Setup 01 end-to-end on all 102 BIRAFFE2 subjects.
- ✅ Fixed single-class test-fold issue: LOSO CV now also reports **subject-level** accuracy/F1/AUC by aggregating window predictions to one prediction per subject.
- ✅ Added loader support for averaged score columns (e.g. mean of `GEQ-1-FLOW-2018`, `GEQ-2-FLOW-2018`, `GEQ-3-FLOW-2018`).
- ✅ Created `setup_01_biraffe2_ecg_baseline_avg_levels.yaml`.
- ✅ Documented GEQ 2013 vs 2018 scoring, feature calculation, and baseline performance interpretation.
- ✅ Ran the averaged-levels baseline on all 102 subjects. Results:
  - Window-level: Accuracy=0.458, F1=0.312, AUC=nan
  - Subject-level: Accuracy=0.434, F1=0.434, AUC=0.362, n=99
  - Slightly better than single-level Setup 01 (AUC 0.336), but still near chance.
- ✅ Ran batch ablations Setups 02-05, 07, 09. Subject-level AUCs: 02=0.358, 03=0.336, 04=0.336, 05=0.382, 07=0.237, 09=0.396. Setup 09 (heartpy) achieved the best pure-ECG AUC so far.
- ✅ Created Setup 01c config: `config/setup_01c_biraffe2_ecg_levels_as_subjects.yaml`.
  - `BIRAFFE2Loader` now supports `treat_levels_as_subjects=True` for any number of score columns.
  - Reads GAME START/END timestamps from `BIRAFFE2-procedure.zip`.
  - Splits the GAME phase into N equal segments (N = number of score columns) and labels each with the matching score column.
  - Produces up to 306 pseudo-subjects for three columns or up to 612 for six columns.
  - **Ran and achieved subject-level AUC = 0.630 with RandomForest (n=248 pseudo-subjects).**
  - Other models: XGBoost 0.605, kNN 0.576, LogisticRegression 0.558, SVM 0.537.
- ✅ Added diagnostic configs 01d, 01e, 01f, 01g, 11, 12 to test weak-AUC assumptions.
- ✅ Fixed `BIRAFFE2Loader` so `treat_levels_as_subjects` works with six score columns (Setup 01g).
- ✅ Ran Setup 01g original (level-as-subjects + per-subject normalization, six score columns):
  - Window-level: Accuracy=0.543, F1=0.512, AUC=nan
  - Subject-level: Accuracy=0.552, F1=0.528, **AUC=0.501** (XGBoost), n=540 pseudo-subjects.
  - RandomForest subject-level AUC was 0.499 and LogisticRegression 0.077.
  - Per-subject normalization removes the Setup 01c improvement, suggesting the 01c AUC gain was partly driven by subject-specific baseline physiology rather than true within-person Flow variation.
- ✅ Re-ran Setup 01g with `per_subject_normalize=false` and `z_standardise=true`:
  - Window-level: Accuracy=0.532, F1=0.473, AUC=nan
  - Subject-level: Accuracy=0.546, F1=0.545, **AUC=0.551**, n=460 pseudo-subjects.
  - Confirms that removing per-subject normalization recovers much of the AUC, but adding 2013 columns does not beat the 3-column 01c result (AUC 0.630).
- ✅ Created `scripts/build_ablation_table.py` and regenerated `results/ablation_comparison.md` / `.csv` with all runnable setups.
- ✅ Redesigned and reran Setups 03 / 11 with `treat_levels_as_subjects: true` and `raw_geq_levels: [1, 2, 3]`, creating up to 306 pseudo-subjects with Time-Distortion-free labels.
  - RandomForest subject-level AUC = **0.618**, accuracy = 0.573, F1 = 0.571, n = 260 pseudo-subjects.
  - Setup 11 per-model AUCs: RandomForest 0.618, LogisticRegression 0.579, XGBoost 0.543.
  - This is slightly below Setup 01c (0.630), suggesting removing item 25 (Time Distortion) makes prediction marginally harder.

## Unified To-Do List — Cover All Supervisor Comments + Missing Setups

Status key: ✅ done / 🔄 partially done / ❌ not done.

### High priority — most likely to improve AUC or directly required by supervisor

| # | Task | Supervisor comment | Status | What exactly needs to be done |
|---|------|--------------------|--------|------------------------------|
| 1 | Proper Setup 03 / Setup 11 — recompute Flow from raw GEQ items excluding item 25 (Time Distortion) | 3 | ✅ Done | Reran with `raw_geq_levels: [1,2,3]`: RF AUC=0.618, n=260; LR=0.579, XGB=0.543 |
| 2 | Setup 12 — BIRAFFE2 baseline correction from procedure-file resting segment | 5 | ✅ Done | Ran with 3 levels as pseudo-subjects + 5 classifiers; RandomForest AUC=0.691, n=223 |
| 3 | Setup 06 — multimodal ECG + EDA + webcam | 12 | 🔄 Config only | Implement EDA loader + cleaning/features, implement webcam/affect loader, combine all features in runner, run `setup_06_full_multimodal.yaml` |
| 4 | Setup 08 — Irshad/PhySF loader with EEG | 9 | 🔄 Config only | Confirm dataset format/path, implement loader with ECG + EDA + EEG + baseline correction, run it |

### Medium priority — methodological completeness

| # | Task | Supervisor comment | Status | What exactly needs to be done |
|---|------|--------------------|--------|------------------------------|
| 5 | Wire permutation analysis into runner | 10 | ❌ Not done | Call `compute_permutation_importance()` inside LOSO CV, store per-feature and per-feature-group importance in results JSON |
| 6 | Biosppy ECG cleaning/features config | 7 | ❌ Not done | Wire biosppy path in `ecg_cleaner.py` and feature extractor, create and run a biosppy config |
| 7 | Finish Setup 10 — wire deep learning models (MLP/LSTM/CNN1D) into runner | 0 | 🔄 Config only | Integrate models from `flow_lol/models/deep.py` into `run_experiment_fast.py`, handle sequences vs flat features |

### Lower priority / support infrastructure

| # | Task | Why | Status | What exactly needs to be done |
|---|------|-----|--------|------------------------------|
| 8 | Ablation comparison table script | Thesis overview | ✅ Done | `scripts/build_ablation_table.py` writes `results/ablation_comparison.md` and `.csv` |
| 9 | Visualisations | Thesis quality | ❌ Not done | Confusion matrices, feature importance plots, learning curves |
| 10 | Document baseline-length limitations | Methodology clarity | ❌ Not done | Add section in GLOSSARY/SETUP docs explaining 60s HRV and EEG baseline limits |

## What still needs to be done (legacy grouped view)

### Immediate (next coding session)
1. ✅ Verify outputs in `results/setup_01_biraffe2_ecg_baseline/`.
2. ✅ Created averaged-levels config `setup_01_biraffe2_ecg_baseline_avg_levels.yaml`.
3. ✅ Updated README, GLOSSARY_AND_METHODOLOGY, and GEQ_ITEMS docs.
4. ✅ Ran `setup_01_biraffe2_ecg_baseline_avg_levels.yaml` and compared with single-level Setup 01.
5. ✅ Ran Setup 02 / 04 / 05 / 07 / 09 configs that require no new loaders. Subject-level AUCs: 02=0.358, 04=0.336, 05=0.382, 07=0.237, 09=0.396. Best pure-ECG result is heartpy (Setup 09).
6. ✅ Implemented and ran corrected Setups 03 / 11 (level-1-only): recompute Flow score from raw GEQ items excluding item 25, with fixed `mean(items) - 1` scoring. Setup 03 RF AUC=0.298; Setup 11 best LR AUC=0.299, RF=0.298, XGB=0.268 (n=99).
7. ✅ Redesigned and reran Setups 03 / 11 with `treat_levels_as_subjects: true` and `raw_geq_levels: [1, 2, 3]` (up to 306 pseudo-subjects). Final subject-level AUC=0.618 with RandomForest (n=260), LR=0.579, XGB=0.543.

### Short-term (complete the 10 setups)
4. ❌ Implement BIRAFFE2 webcam loader (`flow_lol/data/loaders/biraffe2_face_loader.py`).
5. ❌ Implement Irshad/PhySF loader.
6. ❌ Integrate EDA features into `run_experiment.py` for Setup 06.
7. ❌ Integrate EEG features for Setup 08.
8. ❌ Implement baseline-segment extraction from BIRAFFE2 procedure files.
9. 🔄 Add biosppy feature extraction path (heartpy done).
10. ❌ Wire up deep models in the runner.
11. ❌ Add permutation analysis to the runner.

### Medium-term (thesis-grade quality)
12. ❌ Add experiment tracking (MLflow or local CSV).
13. ✅ Generate ablation comparison table across all runnable setups.
14. ❌ Add visualisations (confusion matrices, feature importance, learning curves).
15. ❌ Write unit tests for each preprocessing component.
16. ❌ Document baseline-length limitations for HRV/EEG.

## How to proceed

Setup 12 is complete and produced the best result so far (AUC = 0.691). The next
recommended steps are now:

1. **Setup 06 / multimodal:** add EDA + webcam features to see whether they push AUC higher.
2. **Permutation analysis:** wire feature importance into LOSO CV (comment #10).
3. **Biosppy path:** add the missing cross-package comparison (comment #7).
4. **Deep models / Setup 10:** integrate MLP/LSTM/CNN and compare with classical models.
5. **Visualisations:** confusion matrices, feature-importance plots, learning curves.
