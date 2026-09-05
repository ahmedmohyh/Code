# Implementation Summary

**Date:** 2026-08-21
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
| 10 | `setup_10_all_models.yaml` | RF/SVM/kNN/XGB + LSTM | Comments 0, 10 |

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

## What still needs to be done

### Immediate (next coding session)
1. ✅ Verify outputs in `results/setup_01_biraffe2_ecg_baseline/`.
2. ✅ Created averaged-levels config `setup_01_biraffe2_ecg_baseline_avg_levels.yaml`.
3. ✅ Updated README, GLOSSARY_AND_METHODOLOGY, and GEQ_ITEMS docs.
4. ✅ Ran `setup_01_biraffe2_ecg_baseline_avg_levels.yaml` and compared with single-level Setup 01.
5. ✅ Ran Setup 02–05 / 07 / 09 configs that require no new loaders. Subject-level AUCs: 02=0.358, 03=0.336, 04=0.336, 05=0.382, 07=0.237, 09=0.396. Best pure-ECG result is heartpy (Setup 09).
6. Implement proper Setup 03: recompute Flow score from raw GEQ items excluding item 25.

### Short-term (complete the 10 setups)
4. Implement BIRAFFE2 webcam loader (`flow_lol/data/loaders/biraffe2_face_loader.py`).
5. Implement Irshad/PhySF loader.
6. Integrate EDA features into `run_experiment.py` for Setup 06.
7. Integrate EEG features for Setup 08.
8. Implement baseline-segment extraction from BIRAFFE2 procedure files.
9. Add heartpy/biosppy feature extraction paths.
10. Wire up deep models in the runner.
11. Add permutation analysis to the runner.

### Medium-term (thesis-grade quality)
12. Add experiment tracking (MLflow or local CSV).
13. Generate ablation comparison table across all 10 setups.
14. Add visualisations (confusion matrices, feature importance, learning curves).
15. Write unit tests for each preprocessing component.
16. Document baseline-length limitations for HRV/EEG.

## How to proceed

Tell me which of the following you want next:
- **A.** Implement proper Setup 03 (recompute Flow score from raw GEQ items without item 25).
- **B.** Implement Setup 06 multimodal (ECG + EDA + webcam) by adding EDA and webcam loaders.
- **C.** Add experiment tracking and a script that runs all 10 configs sequentially and compares them.
- **D.** Write unit tests for preprocessing components.
