# Flow-LoL Machine Learning Pipeline

**Goal:** Detect player flow states from physiological signals and build an adaptive support layer for League of Legends.

This repository implements the pipeline described in the Master's thesis and in the updated `ML_Pipeline.docx` report, including every ablation dimension requested by the supervisor.

---

## Quick start

```bash
# Create environment
conda env create -f environment.yml
conda activate flow_lol

# Or with pip
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# Run the baseline setup (fast parallel runner)
python scripts/run_experiment_fast.py --config config/setup_01_biraffe2_ecg_baseline.yaml --n-jobs -1

# Run the averaged-levels baseline
python scripts/run_experiment_fast.py --config config/setup_01_biraffe2_ecg_baseline_avg_levels.yaml --n-jobs -1

# Run all ablation setups that need no new loaders (Setups 02-05, 07, 09)
python scripts/run_batch_setups.py
```

---

## Repository structure

```text
config/                 # YAML configs, one per ablation setup
flow_lol/               # Main package
├── data/               # Loaders and labelers
├── preprocessing/      # Signal cleaning, normalisation, outlier handling, baseline correction
├── segmentation/       # Windowing strategies
├── features/           # Feature extractors per modality
├── models/             # Classical and deep-learning classifiers
├── validation/         # LOSO CV, metrics, permutation analysis
├── reporting/          # Ablation tables and plots
└── utils/              # Config helpers
scripts/                # Experiment runners
notebooks/              # Exploration notebooks
results/                # Outputs (ignored by git)
tests/                  # Unit tests
```

---

## Implemented setups

| Setup | File | Purpose |
|-------|------|---------|
| 01 | `config/setup_01_biraffe2_ecg_baseline.yaml` | BIRAFFE2 ECG-only baseline |
| 01b | `config/setup_01_biraffe2_ecg_baseline_avg_levels.yaml` | Baseline with averaged 3-level Flow label |
| 01c | `config/setup_01c_biraffe2_ecg_levels_as_subjects.yaml` | Treat each GEQ level as a separate pseudo-subject |
| 02 | `config/setup_02_label_margin_01.yaml` | Median split with margin band 0.1 |
| 03 | `config/setup_03_without_time_distortion.yaml` | Labels without Time Distortion item |
| 04 | `config/setup_04_no_zscore.yaml` | No z-standardisation |
| 05 | `config/setup_05_no_outlier.yaml` | No outlier removal |
| 06 | `config/setup_06_full_multimodal.yaml` | BIRAFFE2 ECG + EDA + webcam |
| 07 | `config/setup_07_5min_window.yaml` | 5-minute fixed window |
| 08 | `config/setup_08_irshad_physf.yaml` | Irshad/PhySF ECG + EDA + EEG with baseline correction |
| 09 | `config/setup_09_heartpy.yaml` | ECG cleaning/features with heartpy |
| 10 | `config/setup_10_all_models.yaml` | All classical + LSTM model comparison |
| 01d | `config/setup_01d_drop_unreliable_60s_features.yaml` | Drop VLF/DFA_alpha2/frequency features from 60 s windows |
| 01e | `config/setup_01e_per_subject_normalization.yaml` | Per-subject normalization before LOSO |
| 01f | `config/setup_01f_shorter_step.yaml` | 60 s windows with 10 s step |
| 01g | `config/setup_01g_levels_as_subjects_per_subject_norm.yaml` | Setup 01c + per-subject normalization |
| 11 | `config/setup_11_raw_geq_without_time_distortion.yaml` | Recompute Flow from raw GEQ items excluding item 25 |
| 12 | `config/setup_12_biraffe2_baseline_correction.yaml` | Baseline correction from procedure-file baseline |

Both Setup 03 and Setup 11 read the raw GEQ item CSVs (`BIRAFFE2-metadata-RAW-GEQ-Level01.csv`, etc.) and recompute the level-1 Flow score from items 5, 13, 28, 31, dropping item 25 ("I lost track of time"). See `docs/GEQ_ITEMS.md` for the item mapping.

Run any setup with:

```bash
python scripts/run_experiment.py --config config/setup_01_biraffe2_ecg_baseline.yaml
```

---

## Ablation dimensions

Each config changes one or more of the following:

- **Dataset / modality:** BIRAFFE2, BIRAFFE2 ECG-only, Irshad/PhySF
- **Labelling:** median split, margin band width, with/without Time Distortion
- **Preprocessing:** cleaning package, z-standardisation, outlier strategy, baseline correction
- **Windowing:** 60 s sliding vs 300 s fixed, step size
- **Features:** feature families, calculation package, dropping unreliable features
- **Preprocessing:** cleaning package, z-standardisation, outlier strategy, baseline correction, per-subject normalization
- **Labelling:** median split, margin band, with/without Time Distortion, raw item recomputation
- **Models:** classical vs deep-learning classifiers
- **Validation:** LOSO, per-class metrics, permutation analysis

Results are written to `results/<experiment_name>/`.

---

## Notes

- Raw data are **not** committed; only relative paths are stored in configs.
- Every run is fully determined by its config file.
- The first implemented setup (`setup_01`) runs end-to-end on BIRAFFE2 ECG data.

## Key methodological decisions

### Why we use GEQ-R 2018, not GEQ 2013

The BIRAFFE2 metadata contains both `GEQ-*-FLOW-2013` and `GEQ-*-FLOW-2018`
columns. They come from the same 33 item responses; the difference is the factor
structure used to group them into subscales.

- **GEQ 2013** originally proposed **7 factors** (Positive Affect, Negative
  Affect, Tension, Challenge, Competence, Immersion, Flow).
- **GEQ-R 2018** (Law et al., 2018) re-analysed the items and found the 7-factor
  model did not fit well. The revised model has **5 factors** (Positive Affect,
  Negativity, Competence, Immersion, Flow) and removed 8 items that
  **cross-loaded** (related to more than one factor at the same time).

The Flow subscale happens to keep the same 5 items in both versions, but the 2018
scoring is the empirically validated one and reflects current best practice. We
therefore use `GEQ-*-FLOW-2018` as the main label and keep 2013 only as a
reference.

### How ECG features are computed

The pipeline does **not** read HRV features directly from the CSV. It reads the
raw ECG voltage and computes features through the following chain:

```text
Raw ECG voltage  →  cleaned ECG  →  R-peaks  →  R-R intervals  →  HRV features
```

For each 60-second window this produces:

| Family | Features |
|--------|----------|
| Time domain | `hr_mean`, `SDNN`, `RMSSD`, `pNN50` |
| Frequency domain | `VLF`, `LF`, `HF`, `LF_HF`, `TP` |
| Nonlinear | `sample_entropy`, `DFA_alpha1`, `DFA_alpha2` |

Some features are often missing (NaN) with 60-second windows because they need
longer recordings:

- `VLF` and `DFA_alpha2` need several minutes of data.
- Frequency features are borderline with 60 s; 5 minutes is preferred.

This is one motivation for Setup 07, which uses 5-minute windows.

### Why the baseline performed poorly

Setup 01 (BIRAFFE2 ECG-only, 60 s windows, Random Forest) achieved
subject-level AUC ≈ 0.34 and accuracy ≈ 0.39–0.45. A diagnostic script
(`scripts/diagnose_setup_01.py`) showed that this is not a code bug: the
extracted ECG/HRV features have very weak correlation with the flow labels in
this dataset. Possible reasons include:

- **Subject-specific physiology dominates.** Fitness, age, stress, medication,
  sleep, and genetics create large between-subject differences in HRV that are
  unrelated to flow.
- **60-second windows are too short** for reliable HRV frequency and nonlinear
  features.
- **ECG alone may not carry enough flow-related information.** Flow also has
  behavioural, facial, and EDA correlates that Setup 06 explores.

### Averaging the three level scores

BIRAFFE2 has three 2018 Flow scores: `GEQ-1-FLOW-2018`, `GEQ-2-FLOW-2018`, and
`GEQ-3-FLOW-2018`, one per game level. Using only the level-1 score as a label
means training on physiology from the whole session but predicting how the player
felt after level 1. Averaging the three scores gives a subject-level flow score
that better represents the overall session. This is implemented in:

```bash
config/setup_01_biraffe2_ecg_baseline_avg_levels.yaml
```

Run it with:

```bash
python scripts/run_experiment_fast.py --config config/setup_01_biraffe2_ecg_baseline_avg_levels.yaml --n-jobs -1
```

Result on all 102 subjects (RandomForest, 60 s ECG windows):

- Window-level: Accuracy=0.458, F1=0.312, AUC=nan
- Subject-level: Accuracy=0.434, F1=0.434, AUC=0.362, n=99

This is a small improvement over the single-level label (AUC 0.336), but still
near chance, confirming that the main bottleneck is the weak ECG-flow
relationship rather than the label choice.

### Setup 01c — levels as separate pseudo-subjects

Setup 01c tests the hypothesis that level-specific physiology is more
informative than a single session-level label. It uses the BIRAFFE2 procedure
files (`BIRAFFE2-procedure.zip`) to locate the GAME phase, splits that phase
into N equal-duration segments (where N equals the number of configured score
columns), and assigns each segment the label from the corresponding score column:

- Setup 01c: N=3 (`GEQ-1-FLOW-2018`, `GEQ-2-FLOW-2018`, `GEQ-3-FLOW-2018`)
  - pseudo-subject `103000` = subject 103, level 1 segment, label `GEQ-1-FLOW-2018`
  - pseudo-subject `103001` = subject 103, level 2 segment, label `GEQ-2-FLOW-2018`
  - pseudo-subject `103002` = subject 103, level 3 segment, label `GEQ-3-FLOW-2018`
- Setup 01g: N=6 by adding the three GEQ 2013 Flow scores.

This turns up to 102 real subjects into up to 306 pseudo-subjects (01c) or up to
612 pseudo-subjects (01g). LOSO CV leaves one pseudo-subject out at a time.
This is the closest the current pipeline can get to time-varying labels without
raw item-level recomputation.

Important caveats:

- The exact transitions between levels are **not** recorded in the procedure file,
  so the split is an approximation (N equal chunks of the GAME phase).
- If the procedure file is missing for a subject, the whole available recording
  is split into N equal parts as a fallback.
- Subjects with a missing level score produce fewer pseudo-subjects.
- Because the pseudo-subjects from the same real person share physiology,
  LOSO is technically "leave-one-level-out" rather than true person-level
  generalisation.

Run it with:

```bash
python scripts/run_experiment_fast.py --config config/setup_01c_biraffe2_ecg_levels_as_subjects.yaml --n-jobs -1

# Or run a batch of configs defined in a YAML file
python scripts/run_batch_from_config.py --batch config/diagnostic_01d_01g_batch.yaml
```

Result: RandomForest achieved subject-level AUC **0.630** on 248 valid pseudo-subjects, far above the previous pure-ECG ceiling of ~0.40. Setup 01g originally dropped to **0.501** when per-subject normalization was applied, but a re-run with per-subject normalization off and z-standardisation on recovered to **0.551** (n=460). This confirms that subject-specific baseline physiology is a major driver of the 01c improvement, while adding the 2013 scoring version does not beat the 3-column 01c result.

### New diagnostic configs (added to cover weak-AUC assumptions)

To diagnose why pure ECG/HRV gives poor Flow prediction, the following configs were added:

| Setup | What it tests | Subject count | Status |
|-------|---------------|---------------|--------|
| 01d | Are short-window features adding noise? | 102 | Label = mean of 6 Flow scores (3 levels × 2013 + 2018) |
| 01e | Does per-subject normalization help LOSO generalisation? | 102 | Label = mean of 6 Flow scores (3 levels × 2013 + 2018) |
| 01f | Does a shorter step / more windows help? | 102 | Label = mean of 6 Flow scores (3 levels × 2013 + 2018) |
| 01g | Level-as-subjects + per-subject normalization | 540 pseudo-subjects | AUC = 0.501; per-subject norm removes the benefit |
| 01g variant | Level-as-subjects + z-standardise (no per-subject norm) | 460 pseudo-subjects | AUC = 0.551; confirms subject-baseline effect |
| 11  | Does removing Time Distortion from the Flow score change results? | 102 | Run: AUC 0.298 (RF), 0.299 (LR), 0.268 (XGB); raw `mean(items) - 1` scoring verified |
| 12  | Does baseline correction from the resting segment help? | 102 | Not wired yet |

All diagnostic configs 01d–01g and 11 have been run. 01g produced 540 pseudo-subjects with subject-level AUC = 0.501 when per-subject normalization was applied, and 0.551 when it was disabled (n=460). This indicates that subject-specific physiological baselines are a major information source; removing them largely cancels the Setup 01c improvement. Adding the GEQ 2013 scores on top of 2018 scores does not outperform the 3-column 01c design. Setup 11 now recomputes Flow from raw GEQ items without Time Distortion.

## Current status

- ✅ Git repository initialised
- ✅ Package skeleton and config system
- ✅ BIRAFFE2 ECG-only baseline (Setup 01) implemented and run on all 102 subjects
- ✅ 10 ablation config files created (+ averaged-levels baseline config)
- ✅ LOSO CV, per-class metrics, z-standardisation, outlier handling
- ✅ Parallel fast runner (`run_experiment_fast.py`) using all CPU cores
- ✅ Subject-level aggregation for valid ROC-AUC with per-subject labels
- ✅ Averaged 3-level Flow label config created and run
- 🔄 Stubs ready: EDA/webcam/EEG loaders, Irshad/PhySF loader, deep models, permutation analysis
- ✅ Ran remaining configs that need no new loaders (Setups 02–05, 07, 09)
- ✅ Implemented Setup 01c config + loader changes (levels as pseudo-subjects)
- ✅ Added diagnostic configs 01d, 01e, 01f, 01g, 11, 12 to test weak-AUC assumptions
- ✅ Updated README with new configs and their purposes
- ✅ Ran Setup 01c: RandomForest AUC = 0.630 on 248 pseudo-subjects
- ✅ Implemented raw-GEQ item recomputation in `BIRAFFE2Loader` (Setup 03 / Setup 11)
- ✅ Fixed raw GEQ scoring to subtract 1.0 and match BIRAFFE2 pre-computed scale
- ✅ Ran corrected Setups 03 / 11: AUC ~0.30, confirming Time Distortion helps prediction
- ✅ Added `scripts/build_ablation_table.py` and generated `results/ablation_comparison.md/csv`
- ⏳ Next: implement and run Setup 12 (procedure-file baseline correction)

### Latest ablation results (subject-level)

| Setup | Accuracy | F1 | AUC | n | Notes |
|-------|----------|----|-----|---|-------|
| 01 single-level | 0.394 | 0.376 | 0.336 | 99 | Baseline |
| 01b avg-levels | 0.434 | 0.434 | 0.362 | 99 | Averaged 3-level label |
| 01c level-as-subjects | 0.593 | 0.593 | **0.630** | 248 | Best AUC so far; time-varying labels help |
| 01g level-as-subjects + per-subject norm | 0.552 | 0.528 | 0.501 | 540 | Original 01g: per-subject norm removes the 01c benefit |
| 01g variant (z-score, no per-subj norm) | 0.546 | 0.545 | 0.551 | 460 | Recovers AUC; subject baselines matter |
| 02 margin 0.1 | 0.478 | 0.452 | 0.358 | 92 | Excludes 8 near-median subjects |
| 03 no time dist. | 0.424 | 0.400 | 0.298 | 99 | Raw items without item 25; Time Distortion helps ECG prediction |
| 11 raw GEQ no time dist. | 0.394 | 0.386 | 0.299 | 99 | Same label as 03 with RF/LR/XGB; best LR 0.299, XGB 0.268 |
| 04 no z-score | 0.394 | 0.380 | 0.336 | 99 | Worse than with z-score |
| 05 no outlier | 0.441 | 0.440 | 0.382 | 102 | Slightly better; uses all subjects |
| 07 5-minute window | 0.333 | 0.317 | 0.237 | 90 | Fewer windows, worse AUC |
| 09 heartpy | 0.420 | 0.419 | 0.396 | 100 | Previously best pure-ECG AUC |

**Setup 01c per-model subject-level AUCs (248 pseudo-subjects):**

| Model | AUC | Notes |
|-------|-----|-------|
| RandomForest | **0.630** | Best overall so far |
| XGBoost | 0.605 | Strong second |
| kNN | 0.576 | |
| LogisticRegression | 0.558 | |
| SVM | 0.537 | |

**Corrected raw GEQ scoring.** The first implementation of Setups 03 / 11 computed the
raw Flow score as the plain mean of the item responses, while the BIRAFFE2
pre-computed columns actually store `mean(items) - 1`. The loader was fixed to
subtract 1.0, so the recomputed labels are now on the same 0–4 scale as the
metadata. After the fix, subject-level AUCs for the Time-Distortion-free label are
~0.30, well below the pre-computed full-Flow result (0.336). This confirms that
excluding Time Distortion genuinely hurts ECG-based Flow prediction, rather than
being an artefact of a scaling mismatch.

A full comparison table across all runnable setups is automatically generated by
`scripts/build_ablation_table.py` and written to `results/ablation_comparison.md`
and `results/ablation_comparison.csv`.

Takeaway: the level-as-subjects design (time-varying labels) substantially improves AUC
from ~0.40 to **0.630** with RandomForest. This suggests that label misalignment and the
single-label-per-subject limitation were major bottlenecks, not just weak ECG signal.
Both 01g runs show that removing subject-specific baselines (via per-subject
normalization) or adding more pseudo-subjects from the same person does not improve
over 01c. The 0.630 AUC in 01c is therefore likely driven largely by between-subject
physiology exposed by the pseudo-subject split, not by genuine within-person Flow
variation. The pseudo-subjects per real person still share baseline physiology, so 01c is
closer to "leave-one-level-out" than true cross-person generalisation.

