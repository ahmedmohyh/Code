# Implementation Plan: AF-05, AF-09, AF-06

## 1. Link predictions to in-game events (AF-05)

**Goal:** Show kills, deaths, objectives, and assists on the post-game flow timeline so the user can correlate flow state with match events.

**Architecture:**
- Add a `GameEvent` SQLAlchemy model (`flow_lol/persistence/database.py`):
  - `id`, `session_id`, `match_id`, `timestamp`, `event_type`, `actor`, `target`, `description`, `source_json`.
- Extend `LcuClient` to poll the League **Live Client Data API** (`https://127.0.0.1:2999/liveclientdata/eventdata`) while a match is `InProgress`.
  - This endpoint is served by the in-game client, requires no auth, and returns the last events.
  - Poll every 1–2 s; deduplicate by event ID/timestamp.
  - Map event names to types: `ChampionKill` → `kill`/`death`/`assist`, `TurretKilled` → `objective`, `DragonKilled` → `objective`, `BaronKilled` → `objective`, `LevelUp` → optional.
- Add `SessionRepository.add_game_event()` and `.get_game_events(session_id, match_id=None)`.
- In `SensorWorker._on_match_start`, start event polling via the detector/LcuClient. In `_on_match_end`, stop it.
- Update `DashboardWidget` / `FlowTimelineWidget`:
  - Draw event markers (colored triangles/diamonds) on the timeline at event timestamps.
  - Add an event list under the match list showing event type, time, and actor.
  - Color events: green self-kill, red self-death, blue objective.

**Trade-offs:**
- The Live Client Data API only works during actual gameplay, not in ChampSelect/Lobby. The app falls back to no events if the API is unreachable.
- We store raw event JSON so future improvements can parse more fields without schema changes.

**Verification:**
- Start a custom game, kill a dummy target or die to turret, and confirm an event appears on the dashboard timeline after the match.

---

## 2. Post-match tilt / break recommendation (AF-09)

**Goal:** After a match ends, suggest whether the player should take a break based on the flow trend during that match.

**Architecture:**
- Add a simple rule-based analyzer `flow_lol/analysis/match_summary.py`:
  - Input: predictions and game events for one match.
  - Compute:
    - `% flow windows` in the match vs the whole session.
    - Trend slope: early-game flow % vs late-game flow %.
    - Frustration proxies: consecutive no-flow windows, deaths within 10 s of no-flow windows.
  - Output a `BreakRecommendation` enum / dataclass: `Continue`, `ShortBreak`, `LongBreak`, `WarmUp`.
- Store the recommendation text in `Match.notes` when the match ends.
- Expose `SessionRepository.update_match_notes(match_id, notes)`.
- In `SensorWorker._on_match_end`, call the analyzer and persist the result.
- Update `DashboardWidget._show_session` to display the recommendation next to each finished match (e.g., colored badge).

**Trade-offs:**
- Rule-based first; machine-learning personalization is AF-07 / Phase 12 and out of scope here.
- Recommendations are stored as text so they are easy to inspect and adjust later.

**Verification:**
- End a match and see a recommendation badge in the dashboard match list.

---

## 3. Replay integration (AF-06)

**Goal:** Detect League `.rofl` replay files, link them to recorded sessions/matches by timestamp, and offer a reflection prompt.

**Architecture:**
- Add `Replay` SQLAlchemy model:
  - `id`, `session_id`, `match_id`, `file_path`, `game_id`, `recorded_at`, `duration_seconds`, `notes`.
- Add a replay scanner `flow_lol/game/replay_scanner.py`:
  - Default search path: `%USERPROFILE%\Documents\League of Legends\Replays`.
  - Parse the `.rofl` header to extract `gameId` and `recordingOffset` / `recordingLength` (binary header is well-documented in the community; we read only the JSON metadata prefix).
  - Match replays to sessions by checking if the replay timestamp overlaps a session window.
- Add `SessionRepository` methods: `add_replay`, `get_replays(session_id)`, `link_replay_to_match`.
- Update `DashboardWidget`:
  - Show a "Replays" list card with file name, recording time, and a button to open the file in the League client.
  - For each replay, generate a reflection prompt: e.g., "Flow dropped at 12:30 — jump to replay?" if a no-flow window coincides with a death/objective.
- Add a setting for the replay folder path (optional; defaults to the standard LoL path).

**Trade-offs:**
- Full replay event parsing is complex; we read only the metadata header and rely on the existing game-event table for meaningful reflection prompts.
- Opening a replay launches the League client via `os.startfile(file_path)` on Windows.

**Verification:**
- Place a `.rofl` file in the replays folder, open the dashboard, and confirm the replay is listed and linked to the correct session.

---

## Files to modify / create

| File | Change |
|---|---|
| `flow_lol/persistence/database.py` | Add `GameEvent` and `Replay` models. |
| `flow_lol/persistence/repository.py` | Add CRUD methods for game events, match notes, and replays. |
| `flow_lol/game/lcu_client.py` | Add live-client event polling. |
| `flow_lol/game/replay_scanner.py` | New: scan and parse `.rofl` files. |
| `flow_lol/analysis/match_summary.py` | New: rule-based tilt/break analyzer. |
| `flow_lol/ui/sensor_worker.py` | Wire event polling and match-summary generation. |
| `flow_lol/ui/dashboard.py` | Show events, recommendations, and replays. |
| `flow_lol/ui/settings_dialog.py` | Add replay folder path setting. |
| `flow_lol/config/settings.py` | Add `replay_save_path` setting. |
| `flow_lol/ui/styles.py` | Timeline event-marker colors. |

## Out of scope
- Real-time in-game overlays (AF-04 remains partial).
- Disturbance reduction / system APIs (AF-02).
- Machine-learning personalization (AF-07).
- Team dashboard (AF-10 team part).

## Order of implementation
1. Database schema + repository methods.
2. LCU live-client event polling and storage.
3. Dashboard timeline event markers + event list.
4. Match-summary analyzer + notes persistence + dashboard badges.
5. Replay scanner + dashboard replay list + reflection prompts.
6. Settings replay path + final syntax/import checks.
