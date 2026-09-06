# Implementation Status Report — Flow-LoL ML Pipeline

**Date:** 2026-09-06  
**Project:** Master's thesis — Real-time flow detection in League of Legends from physiological signals  
**Student:** Ahmed Mousa  
**Supervisor:** Cosima von Uechtritz

---

## 1. What the pipeline currently does

The repository implements a config-driven, reproducible ML pipeline for training
and evaluating classifiers that detect a player's flow state from physiological
signals. The current focus is on offline ablation experiments using public
datasets.

### Implemented components

| Component | Status | Notes |
|-----------|--------|-------|
| Config system (YAML → dataclass) | ✅ Done | One config per ablation setup |
| BIRAFFE2 ECG loader | ✅ Done | Reads zip + metadata, caches CSVs |
| Level-as-subjects mode | ✅ Done | Splits GAME phase into 3 equal segments; creates pseudo-subjects |
| Setup 01c run | ✅ Done | RandomForest AUC 0.630 on 248 pseudo-subjects |
| Label creation (median split + margin band) | ✅ Done | `FlowLabeler` with tunable margin |
| ECG cleaning (neurokit2 / heartpy / biosppy stubs) | ✅ Partial | neurokit2 and heartpy work; biosppy stub not wired |
| Window segmentation | ✅ Done | 60 s sliding / 300 s fixed |
| ECG feature extraction | ✅ Done | Time, frequency, nonlinear HRV features via neurokit2 and heartpy |
| Feature matrix + imputation | ✅ Done | `features_to_matrix`, `impute_missing` |
| Outlier handling | ✅ Done | `none`, `train_only`, `full_data` strategies |
| Z-standardisation | ✅ Done | Per-fold, train-fit / test-transform |
| LOSO cross-validation | ✅ Done | Subject-level aggregation for valid AUC |
| Classical classifiers | ✅ Done | RandomForest; SVM / XGBoost / k-NN configured but not yet all tested |
| Deep learning models | 🟡 Stubs | MLP / LSTM / 1D-CNN wrappers exist but not wired to runner |
| Reporting | ✅ Done | Saves JSON results + config per run |
| Parallel runner | ✅ Done | `run_experiment_fast.py` with subject- and fold-level parallelism |
| Batch runner | ✅ Done | `run_batch_setups.py` for runnable configs |
| Documentation | ✅ Done | README, glossary, GEQ items, code walkthrough |

---

## 2. Which ablation setups already run

All setups below have been executed end-to-end on BIRAFFE2.

| Setup | What it tests | Subject-level AUC | n |
|-------|---------------|-------------------|---|
| 01 single-level | ECG-only baseline, `GEQ-1-FLOW-2018` | 0.336 | 99 |
| 01b avg-levels | ECG-only, mean of 3 GEQ Flow scores | 0.362 | 99 |
| 02 margin 0.1 | Median split with 0.1 IQR margin | 0.358 | 92 |
| 03 no time dist. | Without Time Distortion (aggregated column) | 0.336 | 99 |
| 04 no z-score | No z-standardisation | 0.336 | 99 |
| 05 no outlier | No outlier removal | 0.382 | 102 |
| 07 5-min window | 300 s fixed window | 0.237 | 90 |
| 09 heartpy | heartpy ECG cleaning/features | 0.396 | 100 |
| 01c level-as-subjects | 3 pseudo-subjects per real subject | **0.630** | 248 |

: **Setup 01c (RandomForest, level-as-subjects)** with AUC **0.630**.
This represents a substantial improvement over the previous ceiling of ~0.40 and
suggests that label misalignment and the single-label-per-subject limitation were
major bottlenecks, not just weak ECG signal. The caveat is that pseudo-subjects from
the same real person still share baseline physiology, so this is closer to
"leave-one-level-out" than true cross-person generalisation.

---

## 3. What is not yet implemented

### 3.1 Proper Setup 03 — Flow without Time Distortion

**What exists:** A config `setup_03_without_time_distortion.yaml` that simply reads
`GEQ-1-FLOW-2018` and changes a flag.

**What should happen:** Recompute the Flow score from the raw GEQ item responses
(items 5, 13, 28, 31) by excluding item 25 ("I lost track of time"). This
requires reading the raw GEQ CSVs (`BIRAFFE2-metadata-RAW-GEQ-Level01.csv`,
`Level02.csv`, `Level03.csv`) and computing a custom Flow score.

**Why it matters:** Supervisor comment #3 explicitly asks for this variant.

**Open question:** Should the recomputation also support averaging across the
three levels?

### 3.2 Baseline correction for BIRAFFE2

**What exists:** Config keys `baseline_correction` and `baseline_length_s` in the
preprocessing config. A stub baseline corrector.

**What should happen:** Extract the first 60 seconds of each BIRAFFE2 recording,
compute per-subject baseline HRV/EDA features, then apply:
- Change scores: `feature - baseline`
- Quotient: `feature / baseline`
- Raw features as reference.

**Why it matters:** Supervisor comment #5 asks for this. Baseline correction
removes subject-specific physiology (fitness, age, stress) that dominates
between-subject variance.

**Blocker:** The BIRAFFE2 procedure files that mark the actual baseline segment
must be located or a convention must be chosen (first 60 s of the biosignal).

### 3.3 Multimodal BIRAFFE2 track (Setup 06)

**What exists:** A config `setup_06_full_multimodal.yaml` that requests ECG + EDA
+ webcam.

**What should happen:** Implement EDA cleaning + feature extraction, and load
BIRAFFE2 webcam-derived affect features. Combine ECG, EDA and webcam features in
one matrix.

**Why it matters:** Pure ECG is weak. EDA and facial expressions are expected to
add complementary flow information. This is the most promising near-term
improvement.

**Blockers:**
- EDA feature extractor not fully integrated into runner.
- Webcam loader not implemented (`flow_lol/data/loaders/biraffe2_face_loader.py`).

### 3.4 Irshad/PhySF track (Setup 08)

**What exists:** A config `setup_08_irshad_physf.yaml`.

**What should happen:** Implement a loader for the Irshad/PhySF dataset (ECG +
EDA + EEG), with baseline correction and EEG preprocessing via MNE-Python.

**Why it matters:** It is the only dataset in the pipeline that contains EEG,
which may be more informative than ECG/EDA alone.

**Blocker:** No loader exists yet; dataset format and path must be confirmed.

### 3.5 Alternative packages fully wired

**What exists:** `clean_ecg()` supports `neurokit2`, `heartpy`, and `biosppy`
stubs. Feature extraction supports neurokit2 and heartpy.

**What should happen:**
- Wire `biosppy` fully into the runner.
- Add an MNE-based ECG/HRV path if useful.
- Document package-specific differences.

**Why it matters:** Supervisor comments #6 and #7 ask for cross-package
comparison.

### 3.6 Permutation analysis

**What exists:** A function `compute_permutation_importance()` in
`flow_lol/validation/metrics.py`.

**What should happen:** Wire it into `run_loso_cv()` and store per-feature and
per-feature-group importance in the results JSON.

**Why it matters:** Supervisor comment #10 asks for it; it quantifies which
feature families drive predictions.

### 3.7 Deep-learning models

**What exists:** Wrappers in `flow_lol/models/deep.py` for MLP, LSTM, 1D-CNN.

**What should happen:** Integrate them into `run_experiment.py` / `run_experiment_fast.py`
so `setup_10_all_models.yaml` can compare classical and deep models.

**Why it matters:** Supervisor comments mention model comparison (comment 0 / 10).

**Open question:** Deep models need subject-level window sequences as input, not
just flat per-window feature vectors. The current data structure supports flat
features only.

### 3.8 Experiment tracking and ablation comparison table

**What exists:** Each run writes its own JSON results.

**What should happen:** Build a script that reads all `results/*/results.json`
files and creates a single comparison table (CSV or Markdown) with all setups,
metrics, and configs.

**Why it matters:** The thesis needs a clear ablation overview, not scattered per-run files.

### 3.9 Live prototype

**What exists:** Described in the thesis and pipeline document only.

**What should happen:** Build a small real-time application that reads a chest-belt
ECG + webcam, runs the trained model in 60-second windows, and interfaces with
the Riot Live Client Data API for interventions.

**Why it matters:** It is the end goal of the thesis and the focus of the ethics
application.

**Blocker:** The ML model is not yet good enough to deploy meaningfully; the
pipeline must first show better offline performance, likely from multimodal
features.

---

## 4. Current problems and risks

### Problem 1: Pure ECG/HRV is a weak flow predictor in BIRAFFE2

**Evidence:** All ECG-only setups are at or below chance. Best AUC = 0.396
(heartpy). 5-minute window is worse (AUC 0.237).

**Interpretation:** Either
- the physiological signal does not strongly covary with the GEQ Flow score in
  this dataset, or
- the single-label-per-subject design and across-subject physiology variance make
  the task very hard, or
- the relevant information is in other modalities (EDA, webcam, EEG) or in
  temporal dynamics.

**Risk:** If no combination improves above chance, the thesis contribution may
need to shift toward explaining *why* flow detection from short physiological
windows is difficult, rather than claiming a strong classifier.

### Problem 2: One label per subject

**Evidence:** BIRAFFE2 provides one GEQ Flow score per level. Setup 01 uses only
level 1; Setup 01b averages all three. In both cases every window of a subject
shares one label.

**Consequence:**
- Window-level AUC is undefined.
- The classifier can learn subject-specific patterns instead of flow-specific
  ones despite LOSO.
- Temporal variation within a session is ignored.

**Mitigation options:**
- Use the averaged label (done, Setup 01b).
- Treat each level as a separate pseudo-subject (done, Setup 01c). This uses
  GAME START/END timestamps to split the recording into level-specific segments,
  but the exact level boundaries are approximated because they are not recorded.
- Use raw GEQ item recomputation (pending Setup 03).
- Investigate whether level transitions can be used to assign time-varying labels
  (requires BIRAFFE2 procedure/timestamp files).

### Problem 3: 60-second windows are short for reliable HRV

**Evidence:** `VLF` and `DFA_alpha2` are often NaN; frequency features are noisy.
The 5-minute window did not help.

**Consequence:** Some features may be unreliable and add noise rather than
information.

**Mitigation options:**
- Drop unreliable features for short windows.
- Use longer windows only if enough subjects have long enough recordings.
- Add EDA/webcam features that do not need multi-minute windows.

### Problem 4: Subject-specific physiology dominates

**Evidence:** LOSO performance is poor. Between-subject differences in fitness,
age, medication and stress likely create larger feature variance than flow state.

**Consequence:** Even with LOSO, the model may not generalise well because the
cross-subject flow signal is weak.

**Mitigation options:**
- Baseline correction (pending).
- Use within-subject designs if the dataset allows.
- Add more discriminative modalities (EDA, EEG, webcam).

### Problem 5: Webcam features in BIRAFFE2 are not raw video

**Evidence:** BIRAFFE2 provides pre-computed webcam affect estimates, not raw
video. These differ from the Noldus/FaceReader-style features used in related
work.

**Consequence:** The ECG-only BIRAFFE2 classifier is the closest match to the
live prototype (which will use raw webcam), but its performance is weak.

**Mitigation options:**
- Train the live webcam model on a separate real-time emotion library.
- Use BIRAFFE2 webcam features as a proxy and document the limitation.

---

## 5. Recommended next steps (prioritised)

| Priority | Task | Expected impact | Effort |
|----------|------|-----------------|--------|
| 0 | Run Setup 01c (level-as-subjects) | Tests whether time-varying labels improve performance | Low |
| 1 | Implement proper Setup 03 from raw GEQ items | Satisfies supervisor comment; tests another label variant | Low |
| 2 | Implement EDA loader + features for Setup 06 | High — first real multimodal test | Medium |
| 3 | Implement webcam loader for Setup 06 | High — adds behavioural signal | Medium |
| 4 | Implement BIRAFFE2 baseline correction | High — reduces subject-specific variance | Medium |
| 5 | Build ablation comparison table script | Medium — thesis-grade overview | Low |
| 6 | Wire permutation analysis | Medium — feature importance | Low |
| 7 | Implement Irshad/PhySF loader (Setup 08) | Medium/High — EEG data | Medium |
| 8 | Wire deep learning models (Setup 10) | Medium — temporal / nonlinear patterns | High |
| 9 | Real-time prototype | Depends on offline model quality | High |

---

## 6. Immediate decision needed

Before continuing, two choices should be made:

1. **Should I run Setup 01c now?** It is fully implemented and will take the
   same time as Setup 01 (~minutes on your machine). This directly tests whether
   level-specific physiology helps.

2. **Should Setup 03 use raw GEQ item recomputation and also average across the
   three levels?** This is a small code change but affects the label semantics.

3. **Should the next big effort go into Setup 06 (multimodal BIRAFFE2: ECG + EDA
   + webcam) or into Setup 08 (Irshad/PhySF with EEG)?** Both are promising, but
   Setup 06 is closer to the planned live prototype (ECG + webcam).

---

## 7. Files to read for more detail

- `README.md` — high-level project summary and latest results
- `SUMMARY.md` — completed and pending tasks
- `docs/GLOSSARY_AND_METHODOLOGY.md` — how features are computed and why
- `docs/GEQ_ITEMS.md` — GEQ scoring and label rationale
- `docs/SETUP_01_CODE_WALKTHROUGH.md` — exact code flow for Setup 01
- `config/setup_01_biraffe2_ecg_baseline.yaml` — example config
