# Setup 06 Pseudo-Subject Dropout Investigation

## Setup
- **Config**: `config/setup_06_full_multimodal.yaml`
- **Modalities**: ECG + EDA + FACE
- **Subject mode**: `treat_levels_as_subjects: true`
- **Score columns**: GEQ-1-FLOW-2018, GEQ-2-FLOW-2018, GEQ-3-FLOW-2018 (3 levels)
- **Expected pseudo-subjects**: 102 real subjects × 3 levels = **306**
- **Observed entering LOSO CV**: **107**

## Findings from lightweight archive/metadata scan

A quick scan of the configured archives and metadata (no feature extraction) showed:

| Stage | Count | Notes |
|-------|-------|-------|
| Real subjects in biosig archive (`BIRAFFE2-biosigs.zip`) | 102 | — |
| Real subjects present in metadata | 102 | — |
| Real subjects with **all three** GEQ level scores | 85 | 17 real subjects are missing at least one level score |
| Face files present (`BIRAFFE2-photo.zip`) | 102 | Face data exists for **every** real subject |
| Pseudo-subjects created by `BIRAFFE2Loader.list_subjects()` | **288** | 18 pseudo-subjects dropped because their GEQ score is NaN |
| Pseudo-subjects after labeler median-split mask | ≈288 (margin=0.0) | Very few, if any, dropped at the median split |
| Pseudo-subjects surviving feature extraction | **107** | **181 dropped** during `_process_one_subject` |

**Net loss**: 306 → 107 (65 % dropout).
The first 18 losses are metadata-level missing scores. The remaining ~181 losses happen inside the feature-extraction pipeline.

## Where in the pipeline subjects are dropped

### 1. `BIRAFFE2Loader.list_subjects()` — metadata/label availability
File: `flow_lol/data/loaders/biraffe2_loader.py`

For each real subject the loader checks whether each configured `score_column` is non-NaN. If a level score is missing, that pseudo-subject is never created.
Diagnostic counters added here report:
- `real_in_archive`
- `real_in_metadata`
- `real_with_all_<N>_levels`
- `pseudo_expected`
- `pseudo_created`
- `dropped_no_metadata`
- `dropped_missing_score`
- `face_files_present`

**Impact**: 18 pseudo-subjects lost (6 real subjects missing at least one GEQ level).

### 2. `FlowLabeler.transform()` — median-split exclusion band
File: `flow_lol/data/labelers/flow_labeler.py`

With `margin: 0.0`, only scores exactly equal to the median are excluded. This is expected to remove very few pseudo-subjects.

### 3. `_extract_signal_features()` in `run_experiment_fast.py`
File: `scripts/run_experiment_fast.py`

This is the main dropout stage. The function is called once per pseudo-subject (and again for baseline correction if enabled). Hard drops happen when:

1. **ECG column missing or signal empty** (`drop_reason: no_ecg_or_empty_signal`).
2. **No 60-second windows fit** after cropping to the level segment (`drop_reason: no_windows`).
3. **All per-window feature dicts are empty** (`drop_reason: all_windows_empty`).

EDA cleaning failures and missing/empty FACE overlap do **not** drop a pseudo-subject by themselves, because ECG features can still be present. The added diagnostics now return per-call counters for:
- `signal_rows`
- `n_windows`
- `empty_ecg_windows`
- `eda_requested` / `eda_present` / `eda_cleaning_ok`
- `face_requested` / `face_present` / `face_windows_with_data`
- `drop_reason`

### 4. `_crop_to_level()` — per-level segment cropping
File: `flow_lol/data/loaders/biraffe2_loader.py`

In level-as-subjects mode the full recording (or GAME phase from the procedure file) is divided into `N` equal-duration chunks, one per GEQ level. Each pseudo-subject receives only its chunk. A diagnostic warning is now emitted for any chunk shorter than 60 seconds:

```text
[crop <real_id>.<level>] SHORT/EMPTY: game=(...), level=(...), duration=..., samples=...
```

If a level segment is shorter than the 60 s window, `segmenter.segment()` returns no windows and the pseudo-subject is dropped.

### 5. LOSO CV aggregation
File: `flow_lol/validation/loso_cv.py` (not modified)

No additional subjects are dropped during LOSO CV; the 107 count is the number of pseudo-subjects that successfully produced features and were passed into `run_loso_cv`.

## Most likely root cause

The largest block of dropout (≈181 pseudo-subjects) occurs because **per-level cropped signal segments are too short to yield a 60-second analysis window**.

Evidence:
- Face data are available for all 102 real subjects, so FACE availability cannot explain the 65 % dropout.
- EDA failures are caught and tolerated; they do not drop the pseudo-subject.
- The config uses `window_length_s: 60` and `step_s: 30` on 1 kHz ECG.
- `_crop_to_level()` splits the GAME phase (or whole recording) into 3 equal parts. If a subject's GAME phase is short or has gaps, one or more level chunks can fall below 60 s.
- The observed 288 → 107 drop (≈63 %) is consistent with many level segments being shorter than the required window length.

A secondary possibility is that some longer segments still produce no usable ECG features (e.g., R-peak detection fails), leading to `drop_reason: all_windows_empty`. The added `empty_ecg_windows` counter will quantify this when the experiment is rerun.

## Suggested fixes

1. **Inspect the new per-level crop warnings first.** Rerun Setup 06 and count how many `[crop ...] SHORT/EMPTY` messages appear and what durations they report. This confirms the window-length hypothesis.

2. **Reduce the window length or increase overlap flexibility** if level segments are genuinely short. For example, try `window_length_s: 30` with `step_s: 15`, or keep 60 s windows but require only one window per level instead of multiple.

3. **Review procedure GAME START/END times.** The loader uses `BIRAFFE2-procedure.zip` to define the GAME phase. If the procedure events are missing or incorrect for many subjects, `_crop_to_level()` falls back to the whole recording, which may produce uneven or short level segments.

4. **Check for recordings with very short GAME phases.** If some subjects have total game durations only a few minutes long, 3 equal levels of 60-second windows is inherently impossible. Those subjects will necessarily contribute fewer than 3 pseudo-subjects.

5. **Separate debugging of `all_windows_empty` drops.** If some pseudo-subjects have windows but still produce empty merged feature dicts, investigate ECG cleaning / R-peak detection (`clean_ecg`, `extract_ecg_features`) and consider lowering the required number of R-peaks or selecting a different ECG cleaning package.

6. **(Optional) Relax the drop rule.** Currently a pseudo-subject is dropped when `not merged or all(not m for m in merged)`. If the project goal is to maximize usable pseudo-subjects, you could keep pseudo-subjects that have at least one non-empty modality window, but this changes the feature matrix shape and requires careful handling of missing modalities during LOSO CV.

## Instrumentation added

- `flow_lol/data/loaders/biraffe2_loader.py`
  - `list_subjects()` now prints aggregate creation/dropout counts.
  - `_crop_to_level()` emits a warning for any level segment shorter than 60 seconds.
  - `load_subject()` records `face_status` in the returned record.

- `scripts/run_experiment_fast.py`
  - `load_biraffe2_data_fast()` prints expected vs. created vs. masked pseudo-subject counts.
  - `_extract_signal_features()` returns a `diagnostics` dict without changing behavior.
  - `_process_one_subject()` returns and prints per-pseudo-subject dropout reasons.
  - Final aggregation prints counts for each drop reason, FACE/EDA availability, and total windows kept.

No experiment logic was changed; only counters, logging, and safe no-op diagnostics were added.
