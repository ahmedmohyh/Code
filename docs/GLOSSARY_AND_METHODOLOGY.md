# Flow-LoL: Glossary and Methodology Notes

This document explains the key machine-learning and signal-processing concepts used in the Flow-LoL pipeline. It is meant as a quick reference while reading the code, editing YAML configs, or writing the thesis.

---

## 1. Dataset terminology

### Subject
One participant / player in the dataset. In BIRAFFE2 there are 102 subjects.

### Biosignal
A continuously recorded physiological signal. In this project we use:
- **ECG** (electrocardiography) — heart electrical activity, sampled at 1 kHz in BIRAFFE2.
- **EDA** (electrodermal activity) — skin conductance, also at 1 kHz. Cleaned with `neurokit2` into tonic (SCL) and phasic (SCR) components.
- **EEG** (electroencephalography) — brain electrical activity, when available.
- **Webcam / face video** — pre-computed emotion probabilities per frame from BIRAFFE2 Face CSVs (`ANGER`, `CONTEMPT`, `DISGUST`, `FEAR`, `HAPPINESS`, `NEUTRAL`, `SADNESS`, `SURPRISE`), aggregated per window as mean/std/max.

### Window
A short, fixed-length segment of a biosignal that is treated as one analysis sample. Example: a 60-second ECG window with a 30-second step gives many windows per subject.

### Label
The flow-state class assigned to a subject. In BIRAFFE2 there is **one global flow score per subject** (`GEQ-1-FLOW-2018`), so every window of that subject shares the same label.

- `0` = low flow
- `1` = high flow


### Pseudo-subject (Setups 01c, 01g, 03, 11)
In **level-as-subjects** mode, each real BIRAFFE2 subject is expanded into up to
N pseudo-subjects — one per configured level. The GAME phase (from `GAME START`
to `GAME END` in the procedure file) is split into **N equal-duration segments**,
and each segment receives the Flow score from the matching level:

- Segment 1 = first 1/N of GAME phase → label from level 1
- Segment 2 = second 1/N of GAME phase → label from level 2
- Segment N = last 1/N of GAME phase → label from level N

For Setup 01c this means N=3 (`GEQ-1-FLOW-2018`, `GEQ-2-FLOW-2018`,
`GEQ-3-FLOW-2018`). Setup 01g uses N=6 by adding the three GEQ 2013 Flow scores.
Setups 03 and 11 also use N=3, but the scores are recomputed from raw items
excluding item 25. Setup 12 uses N=3 with baseline correction from the resting
segment and achieved the best result so far (see Section 4).

Pseudo-subject IDs are encoded as `real_id * 1000 + level_index`, e.g. subject 103
level 1 becomes `103001`. The factor 1000 supports up to 999 levels per subject.

Caveats:

- **Exact level boundaries are not recorded.** The procedure file only has
  `GAME START` and `GAME END`, not `LEVEL 1 END` / `LEVEL 2 START`. The
  equal-duration split is therefore an approximation: the biosignal assigned to
  pseudo-subject "level 1" is the first third of the GAME phase, not necessarily
  the exact physiological segment of level 1.
- The pseudo-subjects of one real person share baseline physiology, so this is
  closer to "leave-one-level-out" than true subject-independent LOSO.

### Feature
A single number extracted from one window. Example: `SDNN` = standard deviation of NN intervals (a time-domain HRV feature).

### Feature matrix `X`
A 2-D array where:
- Each row is one window.
- Each column is one feature.

### Target vector `y`
A 1-D array of labels, one per window.

---

## 2. Cross-validation

### Why not a simple train/test split?

If we randomly shuffle all windows into 80% train / 20% test, windows from the **same subject** can appear in both sets. The model might learn that subject’s personal physiology instead of a general flow pattern. This is called **data leakage**.

### LOSO — Leave-One-Subject-Out

LOSO is the standard evaluation for person-specific data like biosignals.

1. Leave one subject out as the **test set**.
2. Train the model on all remaining subjects.
3. Test the model on the left-out subject.
4. Repeat so that every subject is left out exactly once.
5. Average the results across all folds.

For BIRAFFE2 with 102 subjects, there are **102 folds**.

### Fold
One round of LOSO. Fold *i* trains on 101 subjects and tests on subject *i*.

### Train set / test set
- **Train set**: the data used to teach the model (101 subjects).
- **Test set**: the data used to evaluate the model (1 subject). The model must never see the test subject during training.

---

## 3. Metrics

### Accuracy
Percentage of correctly classified windows (or subjects).

- `1.0` = everything correct.
- `0.5` = coin-flip level for a balanced binary problem.

### F1-macro
The average of per-class F1 scores. Useful when the classes are imbalanced.

### Precision
Out of all windows predicted as class X, how many actually belong to class X.

### Recall
Out of all windows that really belong to class X, how many did the model correctly identify.

### ROC-AUC (Area Under the Receiver Operating Characteristic curve)
A measure of how well the model ranks high-flow subjects above low-flow subjects, independent of the classification threshold.

- `1.0` = perfect ranking.
- `0.5` = random ranking.
- `< 0.5` = worse than random (invert the prediction).

### Why was AUC `nan` in the first run?

In BIRAFFE2, each subject has only one label. When a single subject is left out as the test set, the test set contains only one class (all windows are either low flow or all high flow). AUC needs both classes in the test set, so it is undefined → `nan`.

### Subject-level AUC fix

To solve this, the pipeline aggregates window predictions into **one prediction per subject**:

- `subject_true` = the known label of the left-out subject.
- `subject_pred` = majority vote across that subject’s windows.
- `subject_score` = mean probability of class 1 across that subject’s windows.

After all 102 folds, AUC is computed across the 102 subject-level scores. This gives a valid, scientifically meaningful AUC for datasets with one label per subject.

---

## 4. Preprocessing

### ECG cleaning
Removing noise and baseline drift from the raw ECG signal. The pipeline supports three packages: NeuroKit2, heartpy, and biosppy.

### R-peaks / R-R intervals
The R-peak is the sharp spike in the ECG wave. The time between two consecutive R-peaks is called the **R-R interval** (or NN interval when normal). HRV features are computed from these intervals.

### HRV features
Features derived from heart-rate variability:

- **Time domain**: `hr_mean`, `SDNN`, `RMSSD`, `pNN50`.
- **Frequency domain**: `VLF`, `LF`, `HF`, `LF_HF`, `TP`.
- **Nonlinear**: `sample_entropy`, `DFA_alpha1`, `DFA_alpha2`.

### How ECG features are computed

The pipeline reads only the **raw ECG voltage** from the CSV. For each window it does
the following:

1. **Clean** the ECG signal (remove noise and baseline drift).
2. **Detect R-peaks** — the sharp spikes in the ECG wave.
3. Compute **R-R intervals** — the time between consecutive heartbeats.
4. Derive all HRV features from that R-R interval series.

Example transformation for a 60-second window:

```text
Raw ECG voltage (60,000 samples)
        ↓
Cleaned ECG
        ↓
R-peaks detected (e.g. 90 peaks)
        ↓
R-R intervals in ms (e.g. [759, 729, 702, ...])
        ↓
hr_mean, SDNN, RMSSD, pNN50, VLF, LF, HF, LF_HF, TP, sample_entropy, DFA_alpha1, DFA_alpha2
```

The features are **not** in the CSV — they are computed from the ECG signal by the
code.

### Why some features are missing (NaN)

| Feature | Why it can be NaN | Window-length implication |
|---------|-------------------|---------------------------|
| `VLF` | Very-low-frequency power needs very slow oscillations (25–333 s cycles) | Cannot be reliably estimated from 60 s |
| `DFA_alpha2` | Long-range correlation scaling exponent | Needs several minutes of data |
| Frequency features (`LF`, `HF`, `TP`) | Need enough R-peaks and stable spectrum | 60 s is borderline; 5 min preferred |
| `sample_entropy` | Needs a minimum number of R-R intervals | Can fail on very short/noisy windows |

This is why the 5-minute window setup (Setup 07) is an important ablation.

### Subject-specific physiology

Each person has a different baseline physiology that may be unrelated to flow:

- Fitness level (trained athletes have lower resting heart rate and higher HRV)
- Age (HRV tends to decrease with age)
- Chronic stress or anxiety (changes autonomic balance)
- Medication (e.g. beta-blockers affect heart rate)
- Sleep quality and circadian state
- Genetics

When feature differences between subjects are driven by these factors rather than by
their momentary flow state, the model learns person-specific patterns instead of
flow-specific patterns. LOSO cross-validation is designed to prevent this, but if the
flow signal is weak, the model still struggles to generalise.

---

## 5. Complete config option reference

This section documents every option that can appear in the YAML experiment configs. Use it when creating new setups or interpreting existing results.

### 5.1 `dataset`

| Option | Example values | What it controls |
|---|---|---|
| `name` | `"BIRAFFE2"`, `"Irshad_PhySF"` | Which loader and dataset format to use. |
| `path` | path to dataset root | Root folder (BIRAFFE2) or zip archive (PhySF). |
| `modalities` | `["ECG"]`, `["ECG", "EDA", "EEG"]` | Which biosignals are extracted. Adding a modality adds features but can reduce `n` if the signal is missing or unusable. |
| `treat_levels_as_subjects` | `true` / `false` | In BIRAFFE2, expand each real subject into up to N pseudo-subjects, one per game level. |
| `procedure_path` | path | Folder with BIRAFFE2 procedure files that mark `GAME START`, `GAME END`, `BASELINE START`, etc. |
| `raw_geq_dir` | path | Folder containing raw GEQ item CSVs (Version 2). Used when `recompute_flow_from_items` is `true`. |
| `recompute_flow_from_items` | `true` / `false` | Recompute the Flow score from raw item responses instead of using the pre-aggregated metadata column. |
| `exclude_time_distortion` | `true` / `false` | When recomputing the Flow score, drop item 25 (Time Distortion) and use only items 5, 13, 28, 31. |
| `raw_geq_levels` | `[1, 2, 3]` | Which GEQ levels to include when `recompute_flow_from_items` is `true`. |
| `games_zip_path` | path to `BIRAFFE2-games.zip` | Read real level start/end times from game logs instead of splitting the GAME phase equally. |
| `face_zip_path` | path to `BIRAFFE2-photo.zip` | Read pre-computed affect CSVs if `FACE` / `WEBCAM` is in `modalities`. |
| `external_zip_path` | path to `PhySF.zip` | Alternative to `path` for the Irshad/PhySF zip archive. |

### 5.2 `label`

| Option | Example values | What it controls |
|---|---|---|
| `method` | `"median_split"`, `"extreme_percentile"`, `"filename"` | How continuous flow scores (or filename labels) are turned into binary classes. |
| `margin` | `0.0`, `0.25`, `0.5` | Exclusion band around the decision boundary, expressed as a fraction of the IQR. Only scores outside the band are kept. |
| `percentile_low` | `0.20` | Lower percentile for `extreme_percentile`. Scores ≤ this percentile are labeled low flow. |
| `percentile_high` | `0.80` | Upper percentile for `extreme_percentile`. Scores ≥ this percentile are labeled high flow. |
| `items` | `"full_subscale"`, `"without_time_distortion"` | Which GEQ items are used to build the Flow score. |
| `classes` | `["low", "high"]` | Names of the two output classes. |

#### `method: median_split`

Computes the median of all available flow scores and splits:

- `score ≤ median` → low flow (`0`)
- `score > median` → high flow (`1`)

With `margin > 0`, an exclusion band is added around the median:

```text
low_threshold  = median - margin * IQR
high_threshold = median + margin * IQR
excluded       = scores between low_threshold and high_threshold
```

Example: median = 3.5, IQR = 2.0, margin = 0.25
```text
low  = score ≤ 3.0
high = score ≥ 4.0
excluded = 3.0 < score < 4.0
```

#### `method: extreme_percentile`

Keeps only the most extreme subjects:

- `score ≤ percentile_low` (e.g. bottom 20 %) → low flow
- `score ≥ percentile_high` (e.g. top 20 %) → high flow
- everything in between → excluded

Example: `percentile_low = 0.20`, `percentile_high = 0.80`
```text
Bottom 20 % of scores → low flow
Top 20 % of scores    → high flow
Middle 60 %           → excluded
```

The goal is to reduce label noise by removing ambiguous, middle-range flow scores.

#### `method: filename`

Used for Irshad/PhySF. The label is derived directly from the filename:

- `s<id>_flow.csv` → high flow (`1`)
- `s<id>_no_flow.csv` → low flow (`0`)

`margin` has no effect here because the labels are already binary.

### 5.3 `preprocessing`

| Option | Example values | What it controls |
|---|---|---|
| `cleaning_package` | `"neurokit2"`, `"heartpy"`, `"biosppy"` | Which library cleans/filters ECG and EDA signals. |
| `z_standardise` | `true` / `false` | Standardize features to zero mean and unit variance inside each LOSO fold (fitted on train, applied to test). |
| `per_subject_normalize` | `true` / `false` | Normalize each subject's windows independently before LOSO, using that subject's own mean and std. |
| `outlier_strategy` | `"none"`, `"train_only"`, `"full_data"` | How/whether to remove windows with extreme feature values using IQR-based bounds. |
| `baseline_correction` | `"none"`, `"change_score"`, `"quotient"` | How to remove resting-baseline physiology from the game-phase features. |
| `baseline_length_s` | `60` | Maximum seconds of baseline signal used for correction. |
| `baseline_from_procedure` | `true` / `false` | Use exact `BASELINE START` / `BASELINE END` events from procedure files. If `false`, use the first `baseline_length_s` seconds. |

#### `cleaning_package`

- **ECG cleaning**: removes noise, baseline wander, and powerline interference so R-peaks can be detected reliably.
- **EDA cleaning**: decomposes the signal into **tonic** (slow SCL) and **phasic** (fast SCR) components.

The default and most used package is `neurokit2`. `heartpy` is used in Setup 09.

#### `z_standardise`

Inside each LOSO fold:

```text
mean_train = mean of feature across training windows
std_train  = std of feature across training windows
X_train    = (X_train - mean_train) / std_train
X_test     = (X_test - mean_train) / std_train
```

Important: the mean and std are learned from the **training fold only** to avoid data leakage.

Models like SVM, kNN, LogisticRegression, and deep networks need this. Tree-based models (RandomForest, XGBoost) are scale-invariant, but z-standardisation still helps numerical stability.

#### `per_subject_normalize`

Before LOSO, for each subject separately:

```text
X_subject = (X_subject - mean(X_subject)) / std(X_subject)
```

This removes between-subject differences in absolute physiological levels. The model then learns within-subject deviations rather than absolute values.

This is different from `z_standardise`:
- `per_subject_normalize`: happens **before** LOSO, per subject.
- `z_standardise`: happens **inside** each LOSO fold, on training data.

#### `outlier_strategy`

Detects outlier windows using the IQR rule:

```text
Q1    = 25th percentile of a feature
Q3    = 75th percentile of a feature
IQR   = Q3 - Q1
lower = Q1 - 1.5 * IQR
upper = Q3 + 1.5 * IQR
```

A window is kept only if **all** its feature values lie inside `[lower, upper]`.

The `1.5` factor is hardcoded in `flow_lol/preprocessing/outlier_handler.py`. It is configurable in the constructor but not exposed in the YAML configs, so all current experiments use `1.5`.

Strategies:

- `"none"`: keep all windows.
- `"train_only"`: compute IQR thresholds on the training fold only, then apply them to train and test separately. **This is the safe, default choice** — no data leakage.
- `"full_data"`: compute thresholds on train + test together, then remove outliers. This can leak test information into preprocessing and is only useful as a sensitivity check.

Practical impact: with many features (e.g. multimodal ECG+EDA+EEG), `outlier_strategy` can drop a large fraction of windows. Setup 06 uses `"none"` because the IQR rule was removing too many windows and causing empty folds.

#### `baseline_correction`

BIRAFFE2 recordings include a resting baseline before the game. This option removes each subject's individual resting physiology from the game-phase features.

- `"none"`: do not apply baseline correction.
- `"change_score"`: subtract baseline features from game features:
  ```text
  X_corrected = X_game - mean(X_baseline)
  ```
- `"quotient"`: divide game features by baseline features:
  ```text
  X_corrected = X_game / mean(X_baseline)
  ```

Setup 12 (`biraffe2_baseline_correction`) uses `"change_score"` and is one of the best-performing BIRAFFE2 setups.

#### `baseline_length_s` and `baseline_from_procedure`

- `baseline_length_s`: maximum seconds of baseline to read. If the recorded baseline is shorter, whatever is available is used.
- `baseline_from_procedure: true`: read the exact `BASELINE START` / `BASELINE END` timestamps from the procedure file.
- `baseline_from_procedure: false`: assume the baseline starts at recording time 0 and lasts `baseline_length_s` seconds.

Using procedure events is more accurate because the baseline does not always start at time 0.

### 5.4 `segmentation`

| Option | Example values | What it controls |
|---|---|---|
| `window_length_s` | `60`, `300` | Duration of each analysis window in seconds. |
| `step_s` | `30`, `150` | How many seconds the window advances between consecutive windows. |

Example: `window_length_s = 60`, `step_s = 30` means 60-second windows overlapping by 30 seconds.

### 5.5 `features`

| Option | Example values | What it controls |
|---|---|---|
| `ecg.time` | `["hr_mean", "SDNN", "RMSSD", "pNN50"]` | Time-domain HRV features. |
| `ecg.frequency` | `["VLF", "LF", "HF", "LF_HF", "TP"]` | Frequency-domain HRV features. |
| `ecg.nonlinear` | `["sample_entropy", "DFA_alpha1", "DFA_alpha2"]` | Nonlinear HRV features. |
| `eeg.bands` | `["theta", "alpha", "beta"]` | EEG frequency bands for band-power extraction. |
| `package` | `"neurokit2"`, `"heartpy"` | Which package computes ECG/HRV features. |

### 5.6 `models`

| Option | Example values | What it controls |
|---|---|---|
| `classical` | `["RandomForest"]`, `["RandomForest", "SVM", "kNN", "LogisticRegression", "XGBoost"]` | Classical scikit-learn / XGBoost classifiers to train. |
| `deep` | `["MLP", "LSTM", "CNN1D"]` | PyTorch neural-network architectures to train. |

### 5.7 `validation`

| Option | Example values | What it controls |
|---|---|---|
| `strategy` | `"LOSO"` | Cross-validation strategy. Currently only LOSO is implemented. |
| `permutation` | `true` / `false` | Compute permutation feature importance after training. |
| `metrics` | list of metric names | Which metrics are reported per fold. |

---

## 6. Why `n` differs across setups

The `n` column in the result tables is the number of valid subjects / pseudo-subjects after preprocessing and labeling. It is not always the same because:

1. **Missing data**: some BIRAFFE2 game logs are missing (SUB322 Level 3, SUB668 Levels 2 and 3).
2. **Label exclusion**: `median_split` with `margin > 0` or `extreme_percentile` drops subjects whose scores fall in the excluded band.
3. **Feature extraction failure**: a modality may be missing, flat, or too noisy, producing all-NaN features. The subject is then skipped.
4. **Outlier removal**: if every window of a subject is flagged as an outlier, that subject has `n_test = 0` and is skipped from LOSO.
5. **Modality requirements**: requiring ECG+EDA+EEG keeps fewer subjects than ECG-only because more signals must be clean.

Example from Irshad/PhySF:

| Setup | Required modalities | n |
|---|---|---|
| ECG only | ECG | 25 |
| ECG + EDA | ECG + EDA | 18 |
| ECG + EDA + EEG | ECG + EDA + EEG | 9 |

---

## 7. AUC reliability with single-class folds

With `extreme_percentile` labeling, many real subjects can have all their levels labeled the same (all low or all high). When such a subject is the test fold, AUC is undefined (`nan`) because the test set has only one class. The pipeline skips these folds and reports AUC averaged over the remaining folds.

This means AUC may reflect only a subset of subjects (those with mixed labels across levels). To mitigate this limitation, the tables report both **AUC** and **accuracy**:

- AUC is computed from valid subject-level folds.
- Accuracy is computed across all folds, including single-class folds.

A good critical point for the thesis:

> "Extreme-percentile labeling intentionally removes ambiguous middle-range labels, but it also increases the number of single-class LOSO folds. The reported AUC therefore reflects the subset of subjects with mixed flow labels, while accuracy provides a complementary view across all folds."

---

## 8. Model terminology

### Random Forest
An ensemble of decision trees. Each tree votes, and the majority wins.

### SVM, k-NN, XGBoost
Other classical classifiers available in the pipeline.

### Deep models
Neural-network architectures (MLP, LSTM, 1D-CNN). Implemented as PyTorch wrappers in the pipeline.

---

## 9. Ablation study

An experiment where you change one component at a time to see how much it affects performance. In this project each YAML config file is one ablation setup.

Example ablations:
- Change the margin band around the median split.
- Remove the Time Distortion item from the flow score.
- Turn z-standardisation on/off.
- Use 60-second vs. 5-minute windows.
- Compare ECG-only vs. multimodal features.
- Treat each BIRAFFE2 level as a separate pseudo-subject.
- Apply baseline correction vs. no correction.
- Use extreme-percentile labels vs. median-split labels.

---

## 10. Files and scripts

- `config/biraffe2/**/*.yaml` — BIRAFFE2 experiment configurations and batch definitions.
- `config/irshad/**/*.yaml` — Irshad/PhySF experiment configurations and batch definitions.
- `scripts/run_experiment_fast.py` — parallel runner.
- `scripts/run_grid_search.py` — grid-search runner for classical classifiers.
- `flow_lol/validation/loso_cv.py` — LOSO cross-validation.
- `flow_lol/features/extractors/ecg_features.py` — ECG/HRV feature extraction.
- `flow_lol/data/labelers/flow_labeler.py` — flow-score labeling logic.
- `results/biraffe2/<experiment_name>/` — BIRAFFE2 output metrics and config for each run.
- `results/irshad/<experiment_name>/` — Irshad/PhySF output metrics and config for each run.
- `results/biraffe2/ablation_comparison.md` — combined BIRAFFE2 results table.
- `results/irshad/ablation_comparison.md` — combined Irshad/PhySF results table.

---

## 11. GEQ items and flow-score construction

For the full list of GEQ items, the original 2013 subscale mapping, and the Time Distortion item, see [`GEQ_ITEMS.md`](GEQ_ITEMS.md).
