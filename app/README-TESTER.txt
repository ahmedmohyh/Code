Flow-LoL – Tester Instructions
==============================

What this app does
------------------
Flow-LoL is a Windows desktop companion for League of Legends. It reads ECG
from a Polar H10 chest belt via Bluetooth, runs a 5-model ensemble to detect
flow/no-flow states in real time, records an optional webcam video, and shows
a post-game timeline you can click to inspect video + snapshots.

Requirements
------------
- Windows 10 or 11 (64-bit).
- A Polar H10 heart-rate sensor paired in Windows Bluetooth settings.
- A webcam (optional; needed only if you want video recordings).
- League of Legends installed (optional; needed only for auto game detection).

First-time setup
----------------
1. Pair the Polar H10 in Windows Bluetooth settings and make sure it is
   charged and blinking blue when not worn.
2. Double-click FlowLoL.exe.
3. Open File -> Settings and check these paths:
   - Replay save path: usually
     C:\Riot Games\League of Legends\Replays
   - Webcam save path and Logs save path can stay at their defaults.
4. Enable/disable individual ECG models in Settings. Leave all 5 enabled for
   the hard-majority vote to work best.

How to use during a LoL game
----------------------------
1. Start the app and press "Connect H10". Wait until the H10 LED turns green
   and the status bar shows "H10: connected".
2. Press "Start session". The status bar should show "webcam: recording" if
   webcam is enabled in Settings.
3. Queue and start a League match. The app should auto-detect the game after
   the loading screen and show "match: active".
   - If auto-detect fails, press "Start match" manually after loading.
4. Play normally.
5. When the Nexus explodes and you are back in the client, the app should
   auto-detect the match end. If not, press "End match" manually.
6. Press "Stop session".

How to review your session
--------------------------
1. Switch to the "Dashboard" tab.
2. Select your session from the dropdown.
3. The timeline shows grey windows (no-flow) and green windows (flow).
4. Click any window to open a popup with the video at that moment and the
   nearest snapshots.
5. Use "Prev window / Next window" and "Prev flow / Next flow" to navigate.

Troubleshooting
---------------
- "No webcam detected": check that another app is not using the camera and
  that Windows privacy settings allow camera access.
- "H10 not connected": remove the H10 from Windows Bluetooth, put it on so
  it blinks blue, then pair it again and retry.
- Match not auto-detected: open Settings and verify the Replay save path.
- App does not start: some antivirus tools may block PyInstaller executables
  on first run. Whitelist FlowLoL.exe if prompted.

Known limitations
-----------------
- This is a research prototype. The flow classifier was trained on lab data
  and may not be perfect for every player.
- Replay / event parsing is best-effort and depends on Riot's replay format.
- Webcam recording and snapshots take disk space (about 1 GB per hour at the
  default settings).

Contact
-------
If something is broken, send the contents of the logs/session_* folders and a
short description of what you did.
