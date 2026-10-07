# Flow-LoL Adaptive Feedback Windows App

A local, offline-first Windows desktop companion app for League of Legends that streams ECG from Polar sensors, detects flow states in real time, and shows a post-game flow timeline.

## Requirements origin

Derived from the MaxQDA coding results (`AF-01` … `AF-10`) and the best-performing ECG-only classifiers from the thesis experiments (BIRAFFE2 and Irshad).

## Architecture overview

- **Frontend / UI**: PyQt6 / PySide6, single-window app with a system tray icon
- **Backend / inference**: pre-trained ECG-only classifiers, loaded from disk; the MLP is a self-contained PyTorch model with weights copied from the research pipeline
- **Streaming**: BLE ECG via `polar_python` (Polar PMD protocol)
  - Primary: Polar H10 chest belt
  - Secondary / optional: Polar Verity Sense (armband) — stubbed, disabled by default
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
| Sensor selection | H10 only | Verity Sense streaming is not implemented yet |
| Preferred sensor | auto | Reserved for future multi-sensor support |
| ECG save path | `app/data/ecg/` | One gzipped CSV per sensor per session (timestamp, value); written at session stop |
| Webcam recording | enabled | MP4 saved under `app/data/webcam/` per session; written continuously |
| Webcam save path | `app/data/webcam/` | Overridable |
| Logs save path | `app/data/logs/` | Overridable; takes effect after restart |
| Database path | `app/data/flow_lol.db` | Overridable; takes effect after restart |
| Riot API integration | disabled until key provided | Manual start/stop + LoL-client detection only; Riot REST API is future work |
| Riot API key | empty | Not used yet |
| Game auto-detect | enabled | Detects `League of Legends.exe` / `LeagueClient.exe`; falls back to manual start/stop |
| Sampling window | 60 s | Matches the best BIRAFFE2 window; overridable |
| Overlap | 50 % | Matches experiment setup; overridable |
| Classifier ensemble | all 5 | Toggle individual ECG-only models on/off; odd count required |

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
      logs_widget.py             <- live ECG plot + log viewer
      webcam_widget.py           <- recording list / player / delete
      tray_icon.py
      sensor_worker.py            <- PyQt6 thread wrapping SensorManager
    sensors/
      __init__.py
      polar_h10.py               <- polar_python ECG streaming
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

All core phases (0 – 2.3) are implemented. Recent work concentrated on making the
live pipeline robust enough for the lab study.

### Completed recently

- **Model export (`scripts/export_models.py`).** Exports five ECG-only bundles.
  Classical models are pickled directly; the BIRAFFE2 MLP is exported as a plain
  dict of weights/scaler so the deployed app does not need the research package.
  The scaler and outlier bounds are refit on the final feature set after
  dropping all-NaN columns, fixing a runtime shape mismatch.
- **H10 streaming (`flow_lol/sensors/polar_h10.py`).** Uses `polar_python`
  (the same backend as the working polar-ecg-viewer project) instead of raw
  `bleak`. Handles the Polar PMD control point and ECG notifications. Detects
  whether Windows already has the H10 connected and reuses the link when
  possible.
- **Sensor worker robustness (`flow_lol/ui/sensor_worker.py`).** A failing
  sensor now emits an error signal but does not crash the whole worker, so the
  session can continue for webcam/game logging.
- **UI tabs.** The main window now has three tabs:
  - **Dashboard** — session/match list and flow timeline.
  - **Logs** — live rolling ECG plot + on-disk log file viewer.
  - **Webcam** — list of recordings, built-in player (Play / Pause / Stop),
    and delete-with-confirmation.
- **Safe exit.** Toolbar **Exit** button and window close handler stop any
  running session cleanly before quitting.
- **Settings storage paths.** Storage tab now lets the user set ECG, webcam,
  logs, and database paths. Logs path is used immediately on next launch; DB
  path requires restart.
- **Webcam finalization (`flow_lol/webcam/recorder.py`).** Uses `avc1` with an
  `mp4v` fallback and makes sure `VideoWriter.release()` is called so the MP4
  container is finalised (fixes the missing `moov` atom).
- **Verity Sense** disabled by default; support is still a stub.

### Known issues / next steps

- [ ] Re-export all five models after the scaler/outlier refit fix in
      `export_models.py` (currently running / pending).
- [ ] Verify all five models load without `PicklingError` or shape mismatch.
- [ ] Test live H10 ECG streaming + predictions in a real session.
- [ ] Build PyInstaller installer once the live pipeline is verified.
- [ ] Phase 9+ (AF-01, AF-09..AF-10) remain future work after the lab study
      data collection.

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

This writes all five bundles:

* `app/models/biraffe2_svm.joblib`
* `app/models/biraffe2_knn.joblib`
* `app/models/biraffe2_rf.joblib`
* `app/models/irshad_rf.joblib`
* `app/models/biraffe2_mlp.joblib`

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
- BLE on Windows uses `polar_python`, which itself uses `bleak` + WinRT. No extra driver is needed for most Windows 10/11 machines with built-in Bluetooth 4.0+.
- PyInstaller must bundle `numpy`, `scipy`, `sklearn` joblib models, and OpenCV DLLs.
- The app stores user data under `%LOCALAPPDATA%\FlowLoL\Data` when installed; the Inno Setup script creates this folder with user-modify permissions so recordings are writable without admin rights.
