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
- **Classifier ensemble**: majority vote
  - BIRAFFE2 best SVM classical model
  - Irshad best RandomForest (no per-window outlier filtering)
  - Optional: MLP / small neural net, gated by a setting
- **Game detection**: automatic via Riot Games API + LoL client detection, with manual start/stop fallback
- **Persistence**: local SQLite database (`flow_lol.db`)
  - sessions table
  - window_predictions table (timestamp, ensemble probabilities / vote)
  - riot_match_events table
  - sensor_quality table (packet loss, battery, connection events)
- **Webcam**: optional background MP4 recording per session
- **Deployment**: PyInstaller single-folder or one-file build + Inno Setup installer for the lab computer

## Settings / configuration

Stored in JSON (`config.json`) and editable in the GUI:

| Setting | Default | Notes |
|---------|---------|-------|
| Sensor selection | H10 + Verity Sense | Auto-detect connected sensors |
| Preferred sensor | auto | User can pick H10 / Verity Sense / both; if both and no preference, predictions are averaged |
| ECG save path | `app/data/ecg/` | One Excel per session (timestamped, gzipped xlsx) |
| Webcam recording | enabled | MP4 saved under `app/data/webcam/` per session |
| Webcam save path | `app/data/webcam/` | Overridable |
| Riot API integration | disabled until key provided | Manual start/stop + LoL-client detection only in Phase 5; Riot REST API added later |
| Riot API key | empty | Development key (24 h) or persistent personal key |
| Game auto-detect | enabled | Falls back to manual start/stop |
| Sampling window | 30 s | Matches experiment setup; overridable |
| Overlap | 50 % | Matches experiment setup |
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

Voting: each model predicts one label per window; the ensemble label is the label with the most votes (guaranteed majority with 5 binary classifiers).
3. **Optional MLP**: if its validation metrics are close and it can be exported cheaply.

Runtime voting:
- If only one sensor connected: both classifiers run on that sensor’s features.
- If two sensors connected:
  - user has set a preferred sensor → use only that sensor’s stream;
  - no preference → classifiers run on each stream, then probabilities are averaged across sensors, then across classifiers (soft vote). Hard majority vote is used as a fallback when probabilities are unavailable.

## Decisions (answered by user)

1. **Model export**: create the exporter first; the app will not retrain at runtime.
2. **Riot API key**: no key yet; Phase 5 starts with manual start/stop + LoL-client process detection. Riot REST API integration is kept as a later TODO.
3. **Two sensors**: let the user choose a preferred sensor; if none is chosen, average predictions from both streams.
4. **Deployment target**: lab PCs run Windows 10/11 64-bit and the installer can run with admin rights.

## Implementation phases

### Core pipeline

- [x] Phase 0 – Project scaffold, settings UI, config persistence
- [x] Phase 1.1 – Model export script: train and save classifiers to `app/models/`
- [ ] Phase 1.2 – Polar H10 BLE ECG streaming and buffering
- [ ] Phase 1.3 – Feature extraction from streaming ECG windows (classical only)
- [ ] Phase 1.4 – Classifier loader + runtime ensemble wiring
- [ ] Phase 1.5 – SQLite session/prediction persistence
- [ ] Phase 2.0 – LoL match auto/manual detection (Riot API optional)
- [ ] Phase 2.1 – Webcam background recording
- [ ] Phase 2.2 – Post-game dashboard / flow timeline
- [ ] Phase 2.3 – Packaging (PyInstaller + installer) and lab deployment

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
| AF-08 | Privacy and transparency (local processing, storage view, deletion) | 0, 1.5 | All processing local; data-deletion button + storage overview in settings |
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
    sensors/
      __init__.py
      polar_h10.py               <- bleak ECG streaming
      polar_verity.py            <- optional armband support
      buffer.py                  <- ECG buffering / windowing
    inference/
      __init__.py
      feature_extract.py         <- HRV/classical feature extraction
      ensemble.py                <- classifier loading + voting
    game/
      __init__.py
      detector.py                <- Riot API + process detection + manual
    persistence/
      __init__.py
      database.py                <- SQLAlchemy or sqlite3 models
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
  build/
    .gitignore                   <- ignore PyInstaller output
```

## Current status

- **Phase 0 complete.** Project scaffold, settings dialog, config persistence,
  and placeholder modules are in place under `flow_lol/`.
- The settings dialog already implements all requested items: sensor selection,
  preferred-sensor fallback, ECG/webcam save paths, webcam toggle,
  auto-detect/manual match control, Riot API placeholder, classifier ensemble
  selection, and screen-edge-only status for AF-04.
- Phase 1.1 is next: train and save the chosen classifiers as joblib files.

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

## Notes for deployment

- Use Python 3.11 (stable PyInstaller target).
- BLE on Windows requires `bleak` + WinRT / `Bleak` backend; no extra driver for most Windows 10/11 machines with built-in Bluetooth 4.0+.
- PyInstaller must bundle `numpy`, `scipy`, `sklearn` joblib models, and OpenCV DLLs.
- The installer should create shortcuts and a `data/` directory outside `Program Files` (e.g. `%USERPROFILE%\FlowLoL\`) so recordings are writable without admin rights.
