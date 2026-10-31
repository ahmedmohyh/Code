"""Real-time interventions for Flow-LoL.

Implements the two Phase-10 intervention requirements:

* Notification muting (AF-02) — best-effort Windows Do-Not-Disturb toggle.
* Adaptive volume / audio cues (AF-04) — lower system volume while the player is in flow.

All intervention state is restored automatically when the session ends,
when flow stops, or when the app shuts down.
"""

from __future__ import annotations

import logging
from typing import Optional

from flow_lol.config.settings import AppSettings

logger = logging.getLogger(__name__)


class VolumeController:
    """Adjust the system master volume using the Core Audio API (pycaw)."""

    def __init__(self) -> None:
        self._available = False
        self._volume: Optional[object] = None
        try:
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, 0, None)
            self._volume = interface.QueryInterface(IAudioEndpointVolume)
            self._available = True
        except Exception as exc:
            logger.warning("Volume control unavailable (install pycaw to enable): %s", exc)

    def get_volume(self) -> float:
        """Return current master volume in [0.0, 1.0]."""
        if not self._available or self._volume is None:
            return 1.0
        try:
            return float(self._volume.GetMasterVolumeLevelScalar())
        except Exception:
            return 1.0

    def set_volume(self, level: float) -> None:
        """Set master volume to ``level`` in [0.0, 1.0]."""
        if not self._available or self._volume is None:
            return
        try:
            level = max(0.0, min(1.0, level))
            self._volume.SetMasterVolumeLevelScalar(level, None)
        except Exception as exc:
            logger.warning("Failed to set volume: %s", exc)

    def set_mute(self, muted: bool) -> None:
        """Mute or unmute the master volume."""
        if not self._available or self._volume is None:
            return
        try:
            self._volume.SetMute(1 if muted else 0, None)
        except Exception as exc:
            logger.warning("Failed to set mute: %s", exc)


class NotificationMuter:
    """Best-effort global Windows toast notification muting via registry.

    Windows does not expose a simple public API for Focus Assist / Do Not Disturb.
    This helper tries the documented notification-settings registry path; if the
    value is missing it creates it. The original value is restored on unmute.

    On Windows 10/11 the key toggles the global "toast enabled" switch used by
    the notification subsystem. If it has no effect on your build, enable
    Focus Assist manually and keep the setting off.
    """

    _REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Notifications\Settings"
    _VALUE_NAME = "NOC_GLOBAL_SETTING_TOASTS_ENABLED"

    def __init__(self) -> None:
        self._original_value: Optional[int] = None
        try:
            import winreg

            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self._REG_PATH) as key:
                try:
                    self._original_value, _ = winreg.QueryValueEx(key, self._VALUE_NAME)
                    if not isinstance(self._original_value, int):
                        self._original_value = int(self._original_value)
                except FileNotFoundError:
                    self._original_value = None
        except Exception as exc:
            logger.debug("Could not read notification registry state: %s", exc)

    def mute(self) -> None:
        """Try to disable toast banners globally."""
        try:
            import winreg

            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, self._REG_PATH, 0, winreg.KEY_SET_VALUE
            ) as key:
                winreg.SetValueEx(key, self._VALUE_NAME, 0, winreg.REG_DWORD, 0)
            logger.info("Notification muting enabled")
        except Exception as exc:
            logger.warning("Could not mute notifications: %s", exc)

    def unmute(self) -> None:
        """Restore the original toast-notification state."""
        try:
            import winreg

            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, self._REG_PATH, 0, winreg.KEY_SET_VALUE
            ) as key:
                if self._original_value is not None:
                    winreg.SetValueEx(
                        key, self._VALUE_NAME, 0, winreg.REG_DWORD, self._original_value
                    )
                else:
                    try:
                        winreg.DeleteValue(key, self._VALUE_NAME)
                    except FileNotFoundError:
                        pass
            logger.info("Notification muting disabled")
        except Exception as exc:
            logger.warning("Could not restore notifications: %s", exc)


class InterventionManager:
    """Apply and restore real-time flow interventions based on predictions."""

    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings
        self._volume = VolumeController()
        self._notifications = NotificationMuter()
        self._session_active = False
        self._flow_active = False
        self._original_volume: Optional[float] = None

    def on_session_state_changed(self, active: bool) -> None:
        """Start or stop monitoring for interventions."""
        self._session_active = active
        if not active:
            self._restore_all()

    def on_prediction(self, prediction_dict: dict) -> None:
        """React to a new ensemble prediction."""
        if not self._session_active:
            return
        if not (
            self.settings.notification_muting_enabled or self.settings.adaptive_cues_enabled
        ):
            return
        label = prediction_dict.get("ensemble_label", 0)
        if label == 1 and not self._flow_active:
            self._enter_flow()
        elif label == 0 and self._flow_active:
            self._exit_flow()

    def _enter_flow(self) -> None:
        self._flow_active = True
        logger.info("Entering flow state — applying interventions")
        if self.settings.adaptive_cues_enabled:
            self._original_volume = self._volume.get_volume()
            target = max(0.0, min(1.0, self.settings.adaptive_volume_percent / 100.0))
            self._volume.set_volume(target)
            logger.info("Adaptive volume: reduced to %.0f%%", target * 100)
        if self.settings.notification_muting_enabled:
            self._notifications.mute()

    def _exit_flow(self) -> None:
        self._flow_active = False
        logger.info("Leaving flow state — restoring interventions")
        self._restore_all()

    def _restore_all(self) -> None:
        if self._original_volume is not None:
            self._volume.set_volume(self._original_volume)
            logger.info("Adaptive volume: restored to %.0f%%", self._original_volume * 100)
            self._original_volume = None
        self._notifications.unmute()

    def shutdown(self) -> None:
        """Force restore everything before app exit."""
        self._restore_all()
