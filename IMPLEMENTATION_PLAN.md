# ML Pipeline Implementation Plan

**Project:** Flow Detection and Adaptive Support in League of Legends  
**Code folder:** `C:\Users\user\Downloads\Masterthesis\Code`  
**Date:** 2026-08-21  
**Goal:** Build a reproducible, config-driven pipeline that implements every ablation dimension requested by the supervisor.

---

## 1. Programming Language & Stack

| Layer | Choice | Why |
|-------|--------|-----|
| Main language | **Python 3.11/3.12** | Standard for ML, biosignal processing and deep learning |
| Environment | **conda** or **venv** + `requirements.txt` | Reproducibility and easy setup |
| Biosignals | **NeuroKit2** (primary), **heartpy**, **biosppy** | Supervisor asked to compare packages |
| EEG | **MNE-Python** | ICA, band-power, spectral entropy |
| ML / CV | **scikit-learn**, **xgboost** | Classical classifiers, LOSO, metrics |
| Deep learning | **PyTorch** (or TensorFlow/Keras if you prefer) | LSTM, 1D-CNN, MLP |
| Data handling | **pandas**, **numpy**, **scipy** | Tables, arrays, signal processing |
| Visualisation | **matplotlib**, **seaborn** | Ablation plots, confusion matrices |
| Configuration | **YAML** + `hydra` or plain `dataclasses` | Every ablation switch becomes one config value |
| Experiment tracking | **MLflow** or a local CSV results table | Compare hundreds of runs |
| Version control | **Git** + `.gitignore` for data/models | Required before coding starts |

---

## 2. Pipeline Architecture

Design the code as **modular stages**, where each stage reads a config object and writes intermediate artefacts. This lets you run ablations by changing only the config.

```text
config/                      <-- one YAML file per ablation run
├── base.yaml
├── ablation_label_margin.yaml
├── ablation_no_zscore.yaml
└── ...

flow_lol/                    <-- main package
├── __init__.py
├── data/
│   ├── loaders/
│   │   ├── biraffe2_loader.py        # ECG, EDA, webcam CSV
│   │   ├── biraffe2_face_loader.py   # emotion probabilities
│   │   └── irshad_loader.py          # PhySF multi-modal CSV
│   └── labelers/
│       └── flow_labeler.py           # median split, margin band, Time-Distortion variants
├── preprocessing/
│   ├── cleaners/
│   │   ├── ecg_cleaner.py            # NeuroKit2 / heartpy / biosppy
│   │   ├── eda_cleaner.py
│   │   └── eeg_cleaner.py
│   ├── outlier_handler.py            # none / train-only / full-data
│   ├── baseline_corrector.py         # raw / change / quotient
│   └── normaliser.py                 # z-standardisation on/off
├── segmentation/
│   └── window_segmenter.py           # 60 s sliding vs 5 min fixed
├── features/
│   ├── extractors/
│   │   ├── ecg_features.py           # HRV time/frequency/nonlinear
│   │   ├── eda_features.py
│   │   ├── eeg_features.py
│   │   └── webcam_features.py
│   └── feature_union.py              # merge feature vectors
├── models/
│   ├── classical.py                  # SVM, RF, XGBoost, k-NN
│   └── deep.py                       # LSTM, 1D-CNN, MLP
├── validation/
│   ├── loso_cv.py                    # leave-one-subject-out
│   ├── metrics.py                    # accuracy, F1, per-class P/R, AUC
│   └── permutation.py                # label + feature-group permutation
├── reporting/
│   ├── ablation_table.py             # build the result matrix
│   └── plots.py                      # heatmaps, confusion matrices
└── utils/
    └── config.py                     # dataclass / OmegaConf schema
```

### Stage flow

```text
Raw data
   ↓
[Loader] → per-subject DataFrame (ECG, EDA, EEG, webcam, labels)
   ↓
[Labeler] → y: High / Low / excluded (margin band)
   ↓
[Cleaner] → cleaned signals
   ↓
[Segmenter] → list of windows with labels
   ↓
[BaselineCorrector] + [Normaliser] + [OutlierHandler]
   ↓
[FeatureExtractor] → feature matrix X
   ↓
[LOSO CV] → trained models + predictions per fold
   ↓
[Metrics + Permutation] → results row
   ↓
[AblationTable] → final comparative report
```

---

## 3. Ablation Variables: What We Change in Each Setup

### 3.1 Dataset / modality track

| Setup | Data source | Modality | Why |
|-------|-------------|----------|-----|
| A | BIRAFFE2 | ECG + EDA + webcam | Full multimodal benchmark |
| B | BIRAFFE2 | ECG only | Raw video unavailable → reproducible baseline (Comment 12) |
| C | Irshad/PhySF | ECG + EDA + EEG | Full physiological benchmark |
| D | BIRAFFE2 + Irshad/PhySF | ECG only | Cross-dataset baseline |

**What changes:** `dataset.name` and `modalities` in config. Code branches in `data/loaders` and `features/extractors`.

---

### 3.2 Labelling strategy

| Variable | Options | Comment |
|----------|---------|---------|
| `label.method` | `median_split` | Required baseline |
| `label.margin` | `0.0`, `0.1`, `0.2` | Fraction of inter-quartile range around median excluded as ambiguous (Comment 1) |
| `label.items` | `full_subscale`, `without_time_distortion` | Which GEQ Flow items are summed (Comment 3) |

**What changes:** `flow_labeler.py` computes the score, applies threshold, excludes margin band. Affects `y` and class sizes.

---

### 3.3 Preprocessing

| Variable | Options | Comment |
|----------|---------|---------|
| `preprocessing.cleaning_package` | `neurokit2`, `heartpy`, `biosppy` | Compare peak detection / EDA decomposition (Comments 6-7) |
| `preprocessing.z_standardise` | `true`, `false` | Applied per fold (Comment 2) |
| `preprocessing.outlier_strategy` | `none`, `train_only`, `full_data` | When and where thresholds are computed (Comment 8) |
| `preprocessing.baseline_correction` | `none`, `change_score`, `quotient` | Requires a pre-task baseline (Comment 5) |

**What changes:** cleaners, normaliser, outlier handler and baseline corrector are all independent classes selected by config.

---

### 3.4 Windowing / segmentation

| Variable | Options | Comment |
|----------|---------|---------|
| `segmentation.window_length_s` | `60`, `300` | 60 s sliding vs 5 min fixed (Comment 4) |
| `segmentation.step_s` | `30` (only for 60 s) | Overlap for sliding window |

**What changes:** `window_segmenter.py` returns windows and labels. Feature stability changes with window length.

---

### 3.5 Feature engineering

| Variable | Options | Comment |
|----------|---------|---------|
| `features.ecg.time` | `hr_mean`, `SDNN`, `RMSSD`, `pNN50` | Time-domain HRV (Comment 9) |
| `features.ecg.frequency` | `VLF`, `LF`, `HF`, `LF/HF`, `TP` | Frequency-domain HRV |
| `features.ecg.nonlinear` | `sample_entropy`, `DFA_α1`, `DFA_α2` | Nonlinear HRV |
| `features.eda` | `SCL_mean`, `phasic_peak`, `SCR_freq`, `SCR_area` | EDA features |
| `features.eeg` | `theta_power`, `alpha_power`, `beta_power`, `alpha/theta`, `spectral_entropy` | EEG bands |
| `features.webcam` | emotion means/variances, head movement, gaze fixation | Facial affect dynamics |
| `features.package` | `neurokit2`, `heartpy`, `mne` | Implementation comparison (Comment 7) |

**What changes:** each feature extractor is a function registered by name. You can swap packages or disable families.

---

### 3.6 Models

| Type | Models | Why |
|------|--------|-----|
| Classical | SVM, Random Forest, XGBoost, k-NN | Interpretable baselines |
| Deep | LSTM, 1D-CNN, MLP | Temporal / multimodal patterns |

**What changes:** `models/classical.py` and `models/deep.py`. Hyper-parameters live in config.

---

### 3.7 Validation

| Variable | Value | Comment |
|----------|-------|---------|
| `validation.strategy` | `LOSO` | Leave-one-subject-out prevents leakage |
| `validation.metrics` | accuracy, F1, per-class precision/recall, AUC, inference latency | Comment 11 |
| `validation.permutation` | `true` | Label + feature-group permutation (Comment 10) |

---

## 4. Suggested First Milestone

Build the simplest complete pipeline first, then add ablations.

1. **M0: Project skeleton**
   - Git init
   - `requirements.txt`
   - `config/base.yaml`
   - `flow_lol/` package with empty modules

2. **M1: BIRAFFE2 ECG-only baseline**
   - Load ECG CSV
   - Create binary labels with `median_split`, `margin=0.0`
   - Clean with NeuroKit2
   - Segment 60 s windows
   - Extract HRV time/frequency/nonlinear features
   - Train Random Forest with LOSO
   - Report accuracy + per-class metrics

3. **M2: Add first ablations**
   - margin band `0.0` vs `0.1` vs `0.2`
   - z-standardise on/off
   - train-only vs full-data outlier removal

4. **M3: Add modalities and packages**
   - EDA, webcam, EEG loaders
   - heartpy / biosppy cleaners
   - Feature package comparison

5. **M4: Deep models + permutation**
   - LSTM, 1D-CNN, MLP
   - Permutation importance

6. **M5: Final ablation report**
   - Generate the supervisor-ready table and plots
   - Export to Word / LaTeX

---

## 5. Config Example

```yaml
# config/base.yaml
experiment_name: "biraffe2_ecg_only_baseline"

seed: 42

dataset:
  name: "BIRAFFE2"          # BIRAFFE2, BIRAFFE2_ECG_ONLY, IRSHAD
  path: "../dataset/data/BIRAFFE2/Version 2/BIRAFFE2-biosigs.zip"
  modalities: ["ECG"]       # ECG, EDA, EEG, WEBCAM

label:
  method: "median_split"
  margin: 0.0               # 0.0 = no margin; try 0.1, 0.2
  items: "full_subscale"    # or "without_time_distortion"

preprocessing:
  cleaning_package: "neurokit2"   # neurokit2, heartpy, biosppy
  z_standardise: true
  outlier_strategy: "train_only"  # none, train_only, full_data
  baseline_correction: "none"     # none, change_score, quotient

segmentation:
  window_length_s: 60
  step_s: 30

features:
  ecg:
    time: ["hr_mean", "SDNN", "RMSSD", "pNN50"]
    frequency: ["VLF", "LF", "HF", "LF_HF", "TP"]
    nonlinear: ["sample_entropy", "DFA_alpha1", "DFA_alpha2"]
  package: "neurokit2"            # neurokit2, heartpy, mne

models:
  classical: ["RandomForest", "SVM", "XGBoost", "kNN"]
  # deep: ["LSTM", "CNN1D", "MLP"]

validation:
  strategy: "LOSO"
  permutation: false
  metrics: ["accuracy", "f1_macro", "precision_per_class", "recall_per_class", "auc", "inference_ms"]
```

---

## 6. Folder Structure After Init

```text
C:\Users\user\Downloads\Masterthesis\Code
├── .git/
├── .gitignore
├── README.md
├── requirements.txt
├── environment.yml
├── config/
│   ├── base.yaml
│   └── ablations/
├── flow_lol/
│   ├── __init__.py
│   ├── data/
│   ├── preprocessing/
│   ├── segmentation/
│   ├── features/
│   ├── models/
│   ├── validation/
│   ├── reporting/
│   └── utils/
├── notebooks/
│   └── 01_explore_biraffe2.ipynb
├── scripts/
│   └── run_experiment.py
├── results/
│   ├── ablation_table.csv
│   └── figures/
└── tests/
    └── test_loaders.py
```

---

## 7. Reproducibility Rules

1. Every run is fully determined by a config file.
2. Config name becomes the run ID.
3. Results are saved as `results/<run_id>/metrics.json` + `predictions.csv`.
4. Raw data are **never** committed; only paths are stored in configs.
5. Models are retrained from scratch each run; no saved checkpoints in git.
6. LOSO folds are deterministic by subject ID, not random.
7. Per-class sample sizes are logged before training.

---

## 8. Open Questions to Decide Before Coding

| Question | Recommended default |
|----------|---------------------|
| Deep-learning framework | **PyTorch** |
| Experiment tracker | Local CSV first, optional MLflow later |
| How to store intermediate windows | `.parquet` files in `cache/` |
| How many margin widths to test | `0.0, 0.1, 0.2` (3 levels) |
| Outlier detection method | IQR on feature matrix; also try isolation forest |
| Baseline length for Irshad/PhySF | Use first 60 s if available; document limitation |
| Webcam downsampling | 4 Hz already averaged; align by nearest timestamp |

---

## 9. Summary of What Each Setup Changes

| Setup | Dataset | Modalities | Label margin | Time Distortion | Z-score | Outlier | Baseline | Window | Cleaning pkg | Feature pkg | Models |
|-------|---------|------------|--------------|-----------------|---------|---------|----------|--------|--------------|-------------|--------|
| 1 | BIRAFFE2 | ECG | 0.0 | full | yes | train-only | none | 60 s | neurokit2 | neurokit2 | RF |
| 2 | BIRAFFE2 | ECG | 0.1 | full | yes | train-only | none | 60 s | neurokit2 | neurokit2 | RF |
| 3 | BIRAFFE2 | ECG | 0.0 | without_TD | yes | train-only | none | 60 s | neurokit2 | neurokit2 | RF |
| 4 | BIRAFFE2 | ECG | 0.0 | full | no | train-only | none | 60 s | neurokit2 | neurokit2 | RF |
| 5 | BIRAFFE2 | ECG | 0.0 | full | yes | none | none | 60 s | neurokit2 | neurokit2 | RF |
| 6 | BIRAFFE2 | ECG+EDA+webcam | 0.0 | full | yes | train-only | none | 60 s | neurokit2 | neurokit2 | RF |
| 7 | BIRAFFE2 | ECG | 0.0 | full | yes | train-only | none | 300 s | neurokit2 | neurokit2 | RF |
| 8 | Irshad/PhySF | ECG+EDA+EEG | 0.0 | full | yes | train-only | change_score | 60 s | neurokit2 | mne | RF |
| 9 | BIRAFFE2 | ECG | 0.0 | full | yes | train-only | none | 60 s | heartpy | heartpy | RF |
| 10 | BIRAFFE2 | ECG | 0.0 | full | yes | train-only | none | 60 s | neurokit2 | neurokit2 | all classical + LSTM |

This table can be copied into the final thesis as the ablation design matrix.
