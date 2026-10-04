"""System tray icon (stub for Phase 0)."""

from __future__ import annotations

from PyQt6.QtWidgets import QSystemTrayIcon, QWidget


class TrayIcon(QSystemTrayIcon):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setToolTip("Flow-LoL")
