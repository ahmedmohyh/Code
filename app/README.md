# Flow-LoL Adaptive Feedback Windows App

A local, offline-first Windows desktop companion app for League of Legends that streams ECG from Polar sensors, detects flow states in real time, and shows a post-game flow timeline.

## Requirements origin

Derived from the MaxQDA coding results (`AF-01` … `AF-10`) and the best-performing ECG-only classifiers from the thesis experiments (BIRAFFE2 and Irshad).

## Architecture overview

- **Frontend / UI**: PyQt6 / PySide6, single-window app with a system tray icon
- **Backend / inference**: pre-trained ECG-only classifiers, loaded from disk
- **Streaming**: BLE ECG via `bleak`
  - Primary: Polar H10 chest belt
  - Secondary / optional: Polar Verity Sense (armband)
- **Classifier ensemble**: hard majority vote
  - BIRAFFE2 SVM (classical)
  - BIRAFFE2 kNN (classical)
  - BIRAFFE2 RandomForest (classical)
  - Irshad RandomForest (classical)
  - BIRAFFE2 MLP (deep learning)
  - Each model toggled by a setting; odd-number ensemble guarantees a majority winner.
- **Game detection**: manual start/stop plus LoL-client process auto-detection (`psutil`); Riot Games REST API kept as a future optional layer
- **Persistence**: local SQLite database (`flow_lol.db`)
  - `sessions` table
  - `matches` table (manual or auto-detected LoL matches inside a session)
  - `predictions` table (per-window timestamp, label, votes, probabilities, features; linked to a match when active)
  - `sensor_events` table (connection, errors, quality flags)
- **Webcam**: optional background MP4 recording per session
- **Deployment**: PyInstaller single-folder or one-file build + Inno Setup installer for the lab computer

## Settings / configuration

Stored in JSON (`config.json`) and editable in the GUI:

| Setting | Default | Notes |
|---------|---------|-------|
| Sensor selection | H10 + Verity Sense | Auto-detect connected sensors |
| Preferred sensor | auto | User can pick H10 / Verity Sense / both; if both and no preference, predictions are averaged |
| ECG save path | `app/data/ecg/` | One gzipped CSV per sensor per session (timestamp, value) |
| Webcam recording | enabled | MP4 saved under `app/data/webcam/` per session |
| Webcam save path | `app/data/webcam/` | Overridable |
| Riot API integration | disabled until key provided | Manual start/stop + LoL-client detection only in Phase 5; Riot REST API added later |
| Riot API key | empty | Development key (24 h) or persistent personal key |
| Game auto-detect | enabled | Detects `League of Legends.exe` / `LeagueClient.exe`; falls back to manual start/stop |
| Sampling window | 60 s | Matches the best BIRAFFE2 window; overridable |
| Overlap | 50 % | Matches experiment setup; overridable |
| Classifier ensemble | all 5 | Toggle individual ECG-only models on/off |

## Classifier strategy

Five **ECG-only** models are deployed as a hard-majority-vote ensemble:

| # | Model | Dataset | AUC | Type |
|---|---|---|---|---|
| 1 | BIRAFFE2 SVM | BIRAFFE2 baseline-corrected | 0.790 | classical |
| 2 | BIRAFFE2 kNN | BIRAFFE2 baseline-corrected | 0.761 | classical |
| 3 | BIRAFFE2 RandomForest | BIRAFFE2 baseline-corrected | 0.725 | classical |
| 4 | Irshad RandomForest | Irshad ECG-only | 0.692 | classical |
| 5 | BIRAFFE2 MLP | BIRAFFE2 baseline-corrected | 0.730 | deep learning |

Voting: each model predicts one label per window; the ensemble label is the label with the most votes (guaranteed majority with 5 binary classifiers). All five models can be toggled in settings; an odd count must stay enabled so a majority is always reachable.

## Decisions (answered by user)

1. **Model export**: create the exporter first; the app will not retrain at runtime.
2. **Riot API key**: no key yet; Phase 5 starts with manual start/stop + LoL-client process detection. Riot REST API integration is kept as a later TODO.
3. **Two sensors**: let the user choose a preferred sensor; if none is chosen, average predictions from both streams.
4. **Deployment target**: lab PCs run Windows 10/11 64-bit and the installer can run with admin rights.

## Implementation phases

### Core pipeline

- [x] Phase 0 – Project scaffold, settings UI, config persistence
- [x] Phase 1.1 – Model export script: train and save classifiers to `app/models/`
- [x] Phase 1.2 – Polar H10 BLE ECG streaming and buffering
- [x] Phase 1.3 – Feature extraction from streaming ECG windows (classical only)
- [x] Phase 1.4 – Classifier loader + runtime ensemble wiring
- [x] Phase 1.5 – SQLite session/prediction persistence
- [x] Phase 2.0 – LoL match auto/manual detection (Riot API optional)
- [x] Phase 2.1 – Webcam background recording
- [x] Phase 2.2 – Post-game dashboard / flow timeline
- [x] Phase 2.3 – Packaging (PyInstaller + installer) and lab deployment

### MaxQDA requirement extensions

- [ ] Phase 9 – Pre-game readiness widget + break/tilt recommendations (AF-01, AF-09)
- [ ] Phase 10 – Context-based disturbance reduction: notification muting, adaptive lighting/audio cues, screen-edge-only status (AF-02, AF-04)
- [ ] Phase 11 – Replay integration and reflection prompts (AF-06)
- [ ] Phase 12 – Player- and role-specific threshold learning (AF-07)
- [ ] Phase 13 – Team-mode detection / team dashboard (AF-10)

## Mapping AF-01 .. AF-10 to phases

| ID | Requirement | Phase(s) | Notes |
|----|-------------|----------|-------|
| AF-01 | Pre-game flow readiness / warm-up recommendation | 9 | Simple self-report + last-session trend; not blocked by core pipeline |
| AF-02 | Context-based disturbance reduction (notifications, Discord, second monitor, adaptive audio/lighting) | 10 | Windows-specific; uses tray integration / system APIs; will be opt-in per app setting |
| AF-03 | Multimodal state sensing (webcam + HRV/ECG) | 1.2, 1.3, 1.4, 2.1, 2.2 | ECG is the real-time input; webcam is recorded for post-game reflection only, not classification |
| AF-04 | Communication-safe real-time intervention | 2.0, 10 | Avoid in-game overlays; use screen-edge / non-critical-moment status; real-time feedback deferred to safe moments |
| AF-05 | Post-game flow timeline (flow/frustration/neutral phases linked to kills/deaths/objectives) | 2.2 | Core dashboard feature |
| AF-06 | Replay integration and reflection prompts | 11 | Needs replay file parsing; optional / future extension |
| AF-07 | Personalization and learning of player-/role-specific thresholds | 12 | Low priority per requirements table; collect data first, then learn offline |
| AF-08 | Privacy and transparency (local processing, storage view, deletion) | 0, 1.5, 2.2 | All processing local; per-session deletion in dashboard; storage overview still to come |
| AF-09 | Tilt detection and break recommendation | 2.2, 9 | Use classifier probabilities / post-match trend to suggest a break |
| AF-10 | Team-mode detection (SoloQ vs team/Flex) | 2.0, 13 | Game metadata from manual selection or Riot API; team dashboard future extension |

## Repository structure (planned)

```text
app/
  README.md                      <- this file
  requirements.txt               <- pinned dependencies
  config.json                    <- user settings (created at first run)
  flow_lol/
    __init__.py
    main.py                      <- app entry point
    ui/
      main_window.py
      settings_dialog.py
      dashboard.py
      tray_icon.py
      sensor_worker.py            <- PyQt6 thread wrapping SensorManager
    sensors/
      __init__.py
      polar_h10.py               <- bleak ECG streaming
      polar_verity.py            <- optional armband support (stub)
      buffer.py                  <- ECG buffering / windowing
      manager.py                 <- orchestrates H10 + Verity streams
    inference/
      __init__.py
      feature_extract.py         <- HRV/classical feature extraction
      ensemble.py                <- classifier loading + voting
    game/
      __init__.py
      detector.py                <- Riot API + process detection + manual
    persistence/
      __init__.py
      database.py                <- SQLAlchemy models
      repository.py              <- Session / prediction / event repository
    webcam/
      __init__.py
      recorder.py                <- opencv-python background recorder
    config/
      __init__.py
      settings.py                <- config load/save/defaults
    utils/
      __init__.py
      logging.py
      paths.py
  scripts/
    export_models.py             <- Phase 1.1: train & save classifiers
    scan_polar.py                <- Phase 1.2: list nearby Polar BLE devices
    FlowLoL.spec                 <- Phase 2.3: PyInstaller spec
    build_app.py                 <- Phase 2.3: run PyInstaller
    installer.iss                <- Phase 2.3: Inno Setup installer script
  build/
    .gitignore                   <- ignore PyInstaller output
```

## Current status

- **Phase 0 complete.** Project scaffold, settings dialog, config persistence,
  and placeholder modules are in place under `flow_lol/`.
- **Phase 1.1 complete.** `scripts/export_models.py` exports five ECG-only
  classifiers as joblib bundles; `flow_lol/inference/ensemble.py` performs hard
  majority vote.
- **Phase 1.2 complete.** BLE ECG streaming module for Polar H10 using `bleak`,
  ring buffer with sliding windows, sensor manager, PyQt6 worker skeleton, and a
  small `scripts/scan_polar.py` CLI to discover nearby Polar devices. Verity Sense
  support is stubbed and will be implemented once the PPG parsing strategy is
  decided.
- **Phase 1.3 complete.** `flow_lol/inference/feature_extract.py` extracts the same
  12 classical HRV features used by the exported models (mean HR, SDNN, RMSSD, pNN50,
  VLF, LF, HF, LF/HF, TP, sample entropy, DFA α1, DFA α2) using `neurokit2`, and
  maps them to each model bundle's expected feature order.
- **Phase 1.4 complete.** `flow_lol/inference/pipeline.py` wires the sensor worker
  → feature extraction → classifier ensemble, and `main_window.py` connects the
  Start/Stop buttons to a `SensorWorker`. Predictions are displayed in the status
  label with vote counts.
- **Phase 1.5 complete.** `flow_lol/persistence/database.py` and
  `flow_lol/persistence/repository.py` store sessions, per-window predictions, and
  sensor events in a local SQLite database (`data/flow_lol.db`). The worker
  creates a session when started, writes predictions and connection events during
  streaming, and closes the session when stopped.
- **Phase 2.0 complete.** `flow_lol/game/detector.py` adds manual match
  start/stop and optional LoL-process auto-detection (`psutil`). A `matches`
  table links predictions to individual games, and the toolbar exposes mode
  selection plus Start/Stop match buttons.
- **Phase 2.1 complete.** `flow_lol/webcam/recorder.py` records the default
  webcam to a timestamped MP4 under `data/webcam/` during each session using
  OpenCV (`mp4v` codec, 640×480, 15 fps). Recording starts when the session
  starts and stops automatically when the session ends.
- **Phase 2.2 complete.** `flow_lol/ui/dashboard.py` adds a post-game dashboard
  with a session selector, match list, simple painted flow timeline, per-session
  statistics, and a delete button (removes the session + predictions + matches +
  sensor events from SQLite; leaves ECG/webcam files on disk).
- **Phase 2.3 complete.** `scripts/build_app.py` runs PyInstaller using
  `scripts/FlowLoL.spec` (single-folder build) and `scripts/installer.iss` is an
  Inno Setup installer script that creates a Windows installer, places the app
  under Program Files, and creates a writable data folder under
  `%LOCALAPPDATA%\FlowLoL\Data`.
- **Raw ECG persistence.** `flow_lol/persistence/ecg_writer.py` buffers all
  incoming ECG samples and writes a gzipped CSV per sensor per session to
  `data/ecg/`. This was added after the core phase list to match the configured
  ECG save path.

## Run / develop

```bash
cd C:\Users\user\Downloads\Masterthesis\Code\app
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m flow_lol.main
```

### Export classifiers (Phase 1.1)

The model-export script uses the research pipeline and must be run from the
research repository root:

```bash
cd C:\Users\user\Downloads\Masterthesis\Code
python app\scripts\export_models.py
```

This writes:

* `app/models/biraffe2_svm.joblib`
* `app/models/irshad_rf.joblib`

If dataset paths in the YAML configs do not match your local layout, pass
`--biraffe2-config` and/or `--irshad-config` with corrected paths.

### Build the Windows installer (Phase 2.3)

After exporting models and installing dependencies:

```bash
cd C:\Users\user\Downloads\Masterthesis\Code\app
.venv\Scripts\activate
python scripts\build_app.py
```

This creates `dist/FlowLoL/`. Then compile the Inno Setup script:

```bash
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" scripts\installer.iss
```

The installer writes `Output/FlowLoL_Setup.exe` and can be copied to the lab PC.

## Notes for deployment

- Use Python 3.11 (stable PyInstaller target).
- BLE on Windows requires `bleak` + WinRT / `Bleak` backend; no extra driver for most Windows 10/11 machines with built-in Bluetooth 4.0+.
- PyInstaller must bundle `numpy`, `scipy`, `sklearn` joblib models, and OpenCV DLLs.
- The app stores user data under `%LOCALAPPDATA%\FlowLoL\Data` when installed; the Inno Setup script creates this folder with user-modify permissions so recordings are writable without admin rights.
