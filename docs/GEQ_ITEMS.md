# GEQ Core Module Items in BIRAFFE2

The raw GEQ files (`BIRAFFE2-metadata-RAW-GEQ-Level01.csv`, `Level02.csv`, `Level03.csv`)
contain 33 item columns numbered `1` to `33`. The original GEQ (2013) groups these
items into seven subscales. Below is the mapping based on the official GEQ item list.

## Response scale

Each item is answered on a 0–4 Likert scale:

| Not at all | Slightly | Moderately | Fairly | Extremely |
|------------|----------|------------|--------|-----------|
| 0          | 1        | 2          | 3      | 4         |

## All 33 GEQ items

| # | Item text | Original 2013 subscale | Notes |
|---|-----------|------------------------|-------|
| 1 | I felt content | Positive Affect | |
| 2 | I felt skilful | Competence | |
| 3 | I was interested in the game's story | Immersion | |
| 4 | I thought it was fun | Positive Affect | |
| 5 | I was fully occupied with the game | **Flow** | |
| 6 | I felt happy | Positive Affect | |
| 7 | It gave me a bad mood | Negative Affect | Reverse-scored |
| 8 | I thought about other things | Flow / removed in GEQ-R | Cross-loaded / removed in revised scoring |
| 9 | I found it tiresome | Negative Affect | Reverse-scored |
| 10 | I felt competent | Competence | |
| 11 | I thought it was hard | Challenge | |
| 12 | It was aesthetically pleasing | Immersion | |
| 13 | I forgot everything around me | **Flow** | |
| 14 | I felt good | Positive Affect | |
| 15 | I was good at it | Competence | |
| 16 | I felt bored | Negative Affect / Tension | Reverse-scored |
| 17 | I felt successful | Competence | |
| 18 | I felt imaginative | Immersion | |
| 19 | I felt that I could explore things | Immersion | |
| 20 | I enjoyed it | Positive Affect | |
| 21 | I was fast at reaching the game's targets | Competence | |
| 22 | I felt annoyed | Tension | |
| 23 | I felt pressured | Challenge | |
| 24 | I felt irritable | Tension | |
| 25 | I lost track of time | **Flow / Time Distortion** | Classic flow item; supervisor wants to test removing this |
| 26 | I felt challenged | Challenge | |
| 27 | I found it impressive | Immersion | |
| 28 | I was deeply concentrated in the game | **Flow** | |
| 29 | I felt frustrated | Tension | |
| 30 | It felt like a rich experience | Immersion | |
| 31 | I lost connection with the outside world | **Flow** | |
| 32 | I felt time pressure | Challenge | |
| 33 | I had to put a lot of effort into it | Challenge | |

## Original 2013 Flow subscale

The original GEQ Flow subscale uses these 5 items:

| Item # | Text |
|--------|------|
| 5 | I was fully occupied with the game |
| 13 | I forgot everything around me |
| 25 | I lost track of time |
| 28 | I was deeply concentrated in the game |
| 31 | I lost connection with the outside world |

The Time Distortion item is **#25: "I lost track of time"**.

## Flow without Time Distortion

If the supervisor wants the Flow subscale without the Time Distortion item, the
remaining items would be:

| Item # | Text |
|--------|------|
| 5 | I was fully occupied with the game |
| 13 | I forgot everything around me |
| 28 | I was deeply concentrated in the game |
| 31 | I lost connection with the outside world |

## 2013 vs. 2018 scoring

The BIRAFFE2 metadata file contains both `GEQ-*-FLOW-2013` and `GEQ-*-FLOW-2018`
columns. They are not different item sets in the raw files — both come from the same
33 item responses. The difference is the **factor structure** used to group items into
subscales.

### Original 2013 GEQ — 7 factors

The original GEQ proposed seven subscales:

| Factor | Items | Count |
|--------|-------|-------|
| Positive Affect | 1, 4, 6, 14, 20 | 5 |
| Negative Affect | 7, 9, 16 | 3 |
| Tension | 22, 24, 29 | 3 |
| Challenge | 11, 23, 26, 32, 33 | 5 |
| Competence | 2, 10, 15, 21 | 4 |
| Immersion | 3, 12, 18, 19, 27, 30 | 6 |
| **Flow** | **5, 13, 25, 28, 31** | **5** |

### Revised GEQ-R 2018 — 5 factors

Law et al. (2018) re-analysed the GEQ with exploratory and confirmatory factor
analysis. They found that the 7-factor structure did not fit the data well and
proposed a revised 5-factor structure:

| Factor | Items | Count |
|--------|-------|-------|
| Positive Affect | 1, 4, 6, 14, 20 | 5 |
| Negativity | 7, 22, 24, 29, 23, 32, 33 | 7 |
| Competence | 2, 10, 15, 21 | 4 |
| Immersion | 3, 18, 19, 27, 30 | 5 |
| **Flow** | **5, 13, 25, 28, 31** | **5** |

Eight items were removed because they **cross-loaded** on more than one factor or
had weak loadings. **Cross-loading** means an item is related to more than one
psychological construct at the same time (e.g. "I felt bored" could relate both to
Negative Affect and to the absence of Flow). Such items blur the boundaries between
subscales.

The Flow subscale happens to keep the same 5 items in both versions, but the other
subscales changed substantially.

### Why we use 2018, not 2013

We use `GEQ-*-FLOW-2018` as the label source because:

1. It is the **empirically validated** revised factor structure (Law et al., 2018).
2. The original 2013 7-factor structure was **not confirmed** in that validation
   study; several items cross-loaded and the model fit was poor.
3. BIRAFFE2 provides both versions, and the 2018 scoring reflects current best
   practice in player-experience research.

We do **not** use `GEQ-*-FLOW-2013` as the main label. It is kept only as a reference
or sensitivity check.

## What the pre-computed `GEQ-X-FLOW-2018` columns mean

The BIRAFFE2 metadata file has three 2018 Flow columns per subject:

| Column | Meaning |
|--------|---------|
| `GEQ-1-FLOW-2018` | Flow subscale after game level 1 |
| `GEQ-2-FLOW-2018` | Flow subscale after game level 2 |
| `GEQ-3-FLOW-2018` | Flow subscale after game level 3 |

Each is the **average of the 5 Flow item responses** (5, 13, 25, 28, 31) for that level, **minus 1** to rescale the 1–5 Likert response to a 0–4 score.
They are **not** already aggregated across levels.

### Exact scoring formula

If a participant responded to item *i* with value *r<sub>i</sub>* on the 0–4 Likert scale, the BIRAFFE2 pre-computed Flow column is:

```text
GEQ-X-FLOW = mean(r_5, r_13, r_25, r_28, r_31) - 1
```

The subtraction shifts the response scale from 0–4 (Likert) to the reported 0–4 Flow score range. When the loader recomputes the Flow score from raw items (Setups 03 / 11), it uses the same formula so that the labels stay on the identical scale as the pre-computed metadata columns.

In BIRAFFE2 the three scores have slightly different distributions:

| Level | Mean | Median | Std |
|-------|------|--------|-----|
| 1 | 1.99 | 2.0 | 0.85 |
| 2 | 2.02 | 2.0 | 0.96 |
| 3 | 1.35 | 1.2 | 0.79 |

Level 3 tends to be lower, possibly because players became tired or the level design
changed.

## Why averaging the three levels can make sense

The biosignals (ECG, EDA, etc.) are recorded continuously across **all three game
levels**. Using only `GEQ-1-FLOW-2018` as the label means we try to predict how the
player felt after level 1 from physiology measured across the whole session. If the
player's flow state changed between levels, the label does not match large parts of
the signal.

Averaging `GEQ-1-FLOW-2018`, `GEQ-2-FLOW-2018`, and `GEQ-3-FLOW-2018` gives one
subject-level flow score that better represents the player's overall experience across
the entire recording. This is implemented in the separate config
`setup_01_biraffe2_ecg_baseline_avg_levels.yaml`.

## Level-as-subjects approximation

Several setups (01c, 01g, 03, 11) treat each game level as a separate
"pseudo-subject" to obtain time-varying labels. The procedure file provides only
`GAME START` and `GAME END`, not the boundaries between levels. Therefore the
loader splits the GAME phase into **N equal-duration segments** (N = number of
levels) and assigns each segment the label of the corresponding level:

- Segment 1 = first 1/N of GAME phase → label from level 1
- Segment 2 = second 1/N of GAME phase → label from level 2
- Segment N = last 1/N of GAME phase → label from level N

For the 3-level designs this means:

- Pseudo-subject `103000` = subject 103, **first third of GAME phase**, label from level 1
- Pseudo-subject `103001` = subject 103, **second third of GAME phase**, label from level 2
- Pseudo-subject `103002` = subject 103, **third third of GAME phase**, label from level 3

> **Important limitation:** This assumes the levels took roughly equal time and
> happened in order. The biosignal assigned to pseudo-subject "level 1" is the
> first third of the GAME phase, not the exact physiological segment of level 1.

## Setup 01c — each level as a separate pseudo-subject

Setup 01c (`setup_01c_biraffe2_ecg_levels_as_subjects.yaml`) uses the labels from
the metadata columns `GEQ-1-FLOW-2018`, `GEQ-2-FLOW-2018`, and `GEQ-3-FLOW-2018`
and applies the level-as-subjects approximation described above. This creates up to
306 pseudo-subjects from 102 real subjects. Setup 01g extends the same approach
to six levels by also including the three `GEQ-*-FLOW-2013` columns.

## Setup 03 / Setup 11 — raw item recomputation without Time Distortion

Both `setup_03_without_time_distortion.yaml` and
`setup_11_raw_geq_without_time_distortion.yaml` now recompute the Flow score from the
raw GEQ item responses instead of reading the pre-computed metadata column, and
they treat each of the three game levels as a separate pseudo-subject.

Config flags used:

```yaml
raw_geq_dir: "../dataset/data/BIRAFFE2/Version 2"
recompute_flow_from_items: true
exclude_time_distortion: true
treat_levels_as_subjects: true
raw_geq_levels: [1, 2, 3]
```

When `recompute_flow_from_items` is true, `BIRAFFE2Loader` reads the files
`BIRAFFE2-metadata-RAW-GEQ-Level01.csv`, `Level02.csv`, `Level03.csv` and computes
the per-level Flow score by averaging the relevant item columns.

### Full Flow subscale vs. without Time Distortion

| Variant | Items used |
|---------|------------|
| Full GEQ-R 2018 Flow | 5, 13, **25**, 28, 31 |
| Without Time Distortion | 5, 13, 28, 31 |

Item **25** is "I lost track of time". Excluding it tests whether the classic
Time Distortion item is helping or hurting physiological prediction.

### How the loader matches columns to levels

The `raw_geq_levels` list explicitly selects which raw GEQ levels to use. In
`setup_03_without_time_distortion.yaml` and `setup_11_raw_geq_without_time_distortion.yaml`
this list is `[1, 2, 3]`. The `score_column` value (`GEQ-1-FLOW-2018`) is **not**
read as a label; it is kept only as a fallback for level inference when
`raw_geq_levels` is not provided.

### Pseudo-subject design

Because `treat_levels_as_subjects: true` and `raw_geq_levels: [1, 2, 3]`, the
loader:

1. Reads the GAME START / GAME END timestamps from the BIRAFFE2 procedure file.
2. Splits the GAME phase into three equal-duration segments.
3. For each segment, recomputes the Flow score from raw items 5, 13, 28, 31.
4. Creates up to **306 pseudo-subjects** from 102 real subjects.

This is the same level-as-subjects logic as Setup 01c, but the labels are now
recomputed without the Time Distortion item. It answers the question:

> *If each level has its own Time-Distortion-free Flow label, can ECG predict it?*

Because the GAME phase is split into three equal-duration segments, the
biosignal-to-label alignment is approximate, just as in Setup 01c. Setup 12 uses
the same level-as-subjects design but with the standard GEQ-R 2018 labels and
adds resting-segment baseline correction.

### Results

After rerun, both setups achieved subject-level AUC **0.618** with RandomForest on
260 pseudo-subjects (accuracy 0.573, F1 0.571). Setup 11 per-model AUCs:
RandomForest 0.618, LogisticRegression 0.579, XGBoost 0.543. This is very close
to Setup 01c (0.630) but slightly lower, suggesting that the Time Distortion item
contributes a small amount of useful signal for this ECG-based classifier, or
that removing it slightly destabilises the label distribution.

### Why this matters

The pre-computed `GEQ-1-FLOW-2018` column includes item 25. Simply dropping that
column from the metadata is not enough; the score itself must be recomputed from
the raw responses. The loader now does this automatically when the config flags are
set, so both setups actually test the Flow-without-Time-Distortion label. With
`raw_geq_levels` and `treat_levels_as_subjects`, the setups also avoid the
single-label-per-subject limitation of the first implementation.
