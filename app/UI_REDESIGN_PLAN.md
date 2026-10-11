# Flow-LoL UI/UX Redesign Plan

## Goal
Modernize the PyQt6 frontend so it looks cleaner, feels more dynamic, and uses
stateful toggle controls instead of pairs of Start/Stop buttons.

## Problems with the current UI
1. **Crowded toolbar** – session, match, webcam, tab, and exit controls all live
   in one horizontal `QToolBar`.
2. **Binary actions use two buttons** – Start session / Stop session,
   Start match / Stop match. This is noisy and old-fashioned.
3. **Tabs are toolbar buttons** – navigation looks like an afterthought.
4. **Plain status presentation** – a single `QLabel` above the dashboard and a
   long text-only status bar.
5. **Inconsistent styling** – dark ECG plot next to default light group boxes,
   ad-hoc red delete buttons, no shared theme.
6. **Dashboard looks utilitarian** – group boxes, plain labels, lots of text.

## Proposed redesign

### 1. Centralized theme (`flow_lol/ui/styles.py`)
Create one module that owns colors, spacing, border radius, and the application
stylesheet. This keeps the rest of the widgets free of inline `setStyleSheet`
calls.

Palette (modern, low-saturation, accessible):
- Background: `#f4f6f8`
- Card / surface: `#ffffff`
- Primary accent: `#2563eb` (blue)
- Success: `#10b981`
- Warning: `#f59e0b`
- Danger: `#ef4444`
- Text primary: `#111827`
- Text secondary: `#6b7280`
- Border: `#e5e7eb`
- Dark panel (ECG / logs): `#111827`

Stylesheet targets:
- `QMainWindow`, `QWidget` backgrounds
- `QPushButton` with rounded corners, hover/pressed states
- `QPushButton:checked` for toggle buttons
- `QComboBox`, `QListWidget`, `QGroupBox` without 3-D chrome
- `QStatusBar` minimal styling
- `QMessageBox` / dialog defaults

### 2. Reusable components (`flow_lol/ui/components.py`)
- `ToggleActionButton(QPushButton)` – one button whose text/icon flips with
  state, e.g. `▶ Start session` ↔ `■ Stop session`.
- `SidebarButton(QPushButton)` – checkable, icon + text, used for the vertical
  navigation pane.
- `CardWidget(QWidget)` – white rounded panel with shadow/border and optional
  header.
- `StatusPill(QLabel)` – small rounded badge for sensor, model, webcam, match,
  auto-detect states.
- `IconLabel(QLabel)` – icon + text helper for status rows.

### 3. New main layout (`flow_lol/ui/main_window.py`)
Replace the current toolbar + stacked widget with:

```
+-------------------------------------------------------------+
| [≡]  Flow-LoL          [▶ Start session]  [Mode ▼]  [⏹ End]  |
+------+------------------------------------------------------+
|  📊  |                                                  |
| Dash |              Central stack (Dashboard /          |
|  📈  |              Live Logs / Webcam)                   |
|      |                                                  |
|  📹  |                                                  |
| Web  |                                                  |
|      |                                                  |
|  ⚙️  |                                                  |
| Sett |                                                  |
+------+------------------------------------------------------+
|  H10 ● | models 5/5 | webcam ● | auto-detect ● | no match  |
+-------------------------------------------------------------+
```

- **Top header bar** – app title/branding on the left, global session toggle
  and match controls on the right. The session button becomes a large primary
  toggle. When a session is running, the button turns into a red "Stop session".
- **Left sidebar** – vertical navigation with icon + text buttons for
  Dashboard, Live ECG/Logs, Webcam, Settings. The active page is highlighted.
- **Central area** – current tab content, inside a `CardWidget` or clean panel.
- **Bottom status bar** – status pills instead of one long string:
  - H10 status (connected / scanning / offline)
  - Models enabled count
  - Webcam on/off
  - Auto-detect on/off
  - Match in progress

### 4. Toggle-button behavior
| Control | Idle state | Active state | Notes |
|---|---|---|---|
| Session toggle | `▶ Start session` (primary blue) | `■ Stop session` (danger red) | Disables/enables match and webcam controls |
| Match toggle | `▶ Start match` | `■ End match` | Only enabled when session is running and no match active |
| Webcam toggle | `▶ Enable webcam` | `■ Disable webcam` | Only enabled after sensor connects |

The two-button pairs are removed. `_start_session` / `_stop_session` are merged
behind the toggle; same for match.

### 5. Tab modernization
- Tabs move from the toolbar to the left sidebar.
- Each tab gets a clear icon + label.
- The current tab button is `checked` and styled distinctly.
- Dashboard remains the landing tab.

### 6. Dashboard facelift (`flow_lol/ui/dashboard.py`)
- Wrap sections in `CardWidget`s.
- Header card: session selector, compact action row (refresh, mark finished,
  delete selected, clear all).
- Timeline card: larger, cleaner painter widget with subtle grid, better
  colors, and a legend.
- Details card: structured rows (duration, sensors, predictions, flow %) instead
  of a block of text.
- Match list: styled `QListWidget` with clearer item text and alternating rows.

### 7. Logs / ECG tab facelift (`flow_lol/ui/logs_widget.py`)
- Keep the vertical splitter.
- Put the ECG plot in a dark `CardWidget` so it matches its own theme.
- Add a small legend / stats row under the plot (sample count, time range).
- Log viewer: card with monospaced text, subtle line numbers optional.
- Toolbar row for Refresh / Delete as icon buttons or compact pills.

### 8. Webcam tab facelift (`flow_lol/ui/webcam_widget.py`)
- Recording list in a card.
- Preview + live control in a card.
- Replace Play/Pause/Stop text buttons with icon buttons.
- Webcam toggle button styled as a primary toggle.
- Delete button as a compact danger pill with an icon.

### 9. Settings dialog cleanup (`flow_lol/ui/settings_dialog.py`)
- Keep the tab structure but style the tabs and form rows.
- Use `CardWidget` for each tab's content area.
- Consistent row labels and spacing.
- Disable / visually de-emphasize the unused Riot API controls instead of just
  disabling them.

## Files to create / modify
- **Create** `flow_lol/ui/styles.py` – theme constants and global stylesheet.
- **Create** `flow_lol/ui/components.py` – `ToggleActionButton`,
  `SidebarButton`, `CardWidget`, `StatusPill`, `IconLabel`.
- **Modify** `flow_lol/ui/main_window.py` – new header/sidebar/status layout,
  toggle buttons.
- **Modify** `flow_lol/ui/dashboard.py` – card-based layout, cleaner timeline.
- **Modify** `flow_lol/ui/logs_widget.py` – card-based layout, icon controls.
- **Modify** `flow_lol/ui/webcam_widget.py` – card-based layout, icon controls.
- **Modify** `flow_lol/ui/settings_dialog.py` – tab and card styling.

## Out of scope
- No changes to sensor worker, inference pipeline, persistence, LCU client,
  or configuration schema.
- No new features (just better presentation of existing ones).

## Verification
- `python -m py_compile` on all modified modules.
- Import check: `from flow_lol.ui.main_window import MainWindow`.
- Manual smoke test: open the app, start/stop a session, toggle match, toggle
  webcam, switch tabs, verify the status pills update.
