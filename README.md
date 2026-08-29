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

# Run the baseline setup
python scripts/run_experiment.py --config config/setup_01_biraffe2_ecg_baseline.yaml
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
| 02 | `config/setup_02_label_margin.yaml` | Median split with margin band |
| 03 | `config/setup_03_without_time_distortion.yaml` | Labels without Time Distortion item |
| 04 | `config/setup_04_no_zscore.yaml` | No z-standardisation |
| 05 | `config/setup_05_no_outlier_removal.yaml` | No outlier removal |
| 06 | `config/setup_06_full_multimodal.yaml` | BIRAFFE2 ECG + EDA + webcam |
| 07 | `config/setup_07_5min_window.yaml` | 5-minute fixed window |
| 08 | `config/setup_08_irshad_physf.yaml` | Irshad/PhySF ECG + EDA + EEG with baseline correction |
| 09 | `config/setup_09_heartpy_package.yaml` | ECG cleaning/features with heartpy |
| 10 | `config/setup_10_all_models.yaml` | All classical + LSTM model comparison |

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
- **Windowing:** 60 s sliding vs 300 s fixed
- **Features:** feature families and calculation package
- **Models:** classical vs deep-learning classifiers
- **Validation:** LOSO, per-class metrics, permutation analysis

Results are written to `results/<experiment_name>/`.

---

## Notes

- Raw data are **not** committed; only relative paths are stored in configs.
- Every run is fully determined by its config file.
- The first implemented setup (`setup_01`) runs end-to-end on BIRAFFE2 ECG data.
