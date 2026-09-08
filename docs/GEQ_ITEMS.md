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

Each is the **average of the 5 Flow items** (5, 13, 25, 28, 31) for that level.
They are **not** already aggregated across levels.

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

## Setup 01c — each level as a separate pseudo-subject

Instead of averaging the three level scores, Setup 01c (`setup_01c_biraffe2_ecg_levels_as_subjects.yaml`)
treats each level as an independent pseudo-subject. It uses the GAME START and GAME END
timestamps from the BIRAFFE2 procedure files to split the continuous recording into
three equal-duration segments, then labels each segment with the matching level-specific
Flow score:

- Segment 1 → `GEQ-1-FLOW-2018`
- Segment 2 → `GEQ-2-FLOW-2018`
- Segment 3 → `GEQ-3-FLOW-2018`

This creates up to 306 pseudo-subjects from 102 real subjects and is the closest the
current pipeline can get to time-varying labels without raw item-level recomputation.
The exact level boundaries are approximated because BIRAFFE2 does not record when
level 1 ends and level 2 begins.

Setup 01g (`setup_01g_levels_as_subjects_per_subject_norm.yaml`) extends this
design to six score columns by adding the three GEQ 2013 Flow scores. The loader
now supports any number of score columns in level-as-subjects mode, so the GAME
phase is split into six equal-duration segments and one real subject can yield
up to 612 pseudo-subjects.

## What Setup 03 should do

Setup 03 (`setup_03_without_time_distortion.yaml`) should recompute the Flow score
from the raw GEQ items by averaging the Flow items **without item 25**, then apply
the median split. Currently the config only changes a metadata field
(`items: "without_time_distortion"`), but the `FlowLabeler` still reads the
pre-computed `GEQ-1-FLOW-2018` column. To make Setup 03 meaningful, the loader or
labeler needs to read the raw GEQ item responses and compute the custom Flow score.
