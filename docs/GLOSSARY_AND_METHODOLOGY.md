# Flow-LoL: Glossary and Methodology Notes

This document explains the key machine-learning and signal-processing concepts used in the Flow-LoL pipeline. It is meant as a quick reference while reading the code or writing the thesis.

---

## 1. Dataset terminology

### Subject
One participant / player in the dataset. In BIRAFFE2 there are 102 subjects.

### Biosignal
A continuously recorded physiological signal. In this project we use:
- **ECG** (electrocardiography) — heart electrical activity, sampled at 1 kHz in BIRAFFE2.
- **EDA** (electrodermal activity) — skin conductance, also at 1 kHz.
- **EEG** (electroencephalography) — brain electrical activity, when available.
- **Webcam / face video** — used for emotion recognition features, when available.

### Window
A short, fixed-length segment of a biosignal that is treated as one analysis sample. Example: a 60-second ECG window with a 30-second step gives many windows per subject.

### Label
The flow-state class assigned to a subject. In BIRAFFE2 there is **one global flow score per subject** (`GEQ-1-FLOW-2018`), so every window of that subject shares the same label.

- `0` = low flow
- `1` = high flow

### Pseudo-subject (Setup 01c)
In **level-as-subjects** mode, each real BIRAFFE2 subject is expanded into up to
three pseudo-subjects — one per game level. The GAME phase is split into three
equal-duration segments, and each segment receives the Flow score from the
matching GEQ level (`GEQ-1-FLOW-2018`, `GEQ-2-FLOW-2018`, `GEQ-3-FLOW-2018`).

Pseudo-subject IDs are encoded as `real_id * 100 + level_index`, e.g. subject 103
level 1 becomes `10300`.

Caveats:

- Exact level transition timestamps are **not** provided, so the split is an
  approximation.
- The three pseudo-subjects of one real person share baseline physiology, so this
  is closer to "leave-one-level-out" than true subject-independent LOSO.

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

### Z-standardisation
Scaling each feature to zero mean and unit variance, fitted on the training fold and applied to the test fold. Prevents features with large scales from dominating the model.

### Outlier handling
Removing windows whose feature values fall far outside the inter-quartile range. Strategies:

- `none`: keep everything.
- `train_only`: compute thresholds on the training fold only (safe).
- `full_data`: compute thresholds on train + test (information leakage; only for sensitivity checks).

### Baseline correction
Subtracting or dividing by a resting/baseline segment to remove individual physiological differences. Not used in Setup 01.

---

## 5. Model terminology

### Random Forest
An ensemble of decision trees. Each tree votes, and the majority wins.

### SVM, k-NN, XGBoost
Other classical classifiers available in the pipeline.

### Deep models
Neural-network architectures (MLP, LSTM, 1D-CNN). These are implemented as stubs and will be wired up for Setup 10.

---

## 6. Ablation study

An experiment where you change one component at a time to see how much it affects performance. In this project each YAML config file is one ablation setup.

Example ablations:
- Change the margin band around the median split.
- Remove the Time Distortion item from the flow score.
- Turn z-standardisation on/off.
- Use 60-second vs. 5-minute windows.
- Compare ECG-only vs. multimodal features.
- Treat each BIRAFFE2 level as a separate pseudo-subject.

---

## 7. Files and scripts

- `config/setup_*.yaml` — one experiment configuration per ablation.
- `scripts/run_experiment_fast.py` — parallel runner.
- `flow_lol/validation/loso_cv.py` — LOSO cross-validation.
- `flow_lol/features/extractors/ecg_features.py` — ECG/HRV feature extraction.
- `results/<experiment_name>/` — output metrics and config for each run.

---

## 8. GEQ items and flow-score construction

For the full list of GEQ items, the original 2013 subscale mapping, and the Time Distortion item, see [`GEQ_ITEMS.md`](GEQ_ITEMS.md).
