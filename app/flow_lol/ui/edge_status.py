"""Screen-edge status indicator for Flow-LoL.

A thin, borderless window sits at the top edge of the primary monitor and
colors itself based on the latest flow prediction. It is designed to be
unobtrusive: no focus stealing, always on top, and only a few pixels high.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QWidget

from flow_lol.ui.styles import Colors


class EdgeStatusWindow(QWidget):
    """Thin colored bar at the top edge of the screen showing flow state."""

    HEIGHT = 6

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus
            | Qt.WindowType.X11BypassWindowManagerHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"background-color: {Colors.NO_FLOW};")

        screen = QApplication.primaryScreen()
        if screen is not None:
            geo = screen.availableGeometry()
            self.setGeometry(geo.x(), geo.y(), geo.width(), self.HEIGHT)
        else:
            self.setGeometry(0, 0, 1920, self.HEIGHT)

        self._enabled = False
        self.hide()

    def set_enabled(self, enabled: bool) -> None:
        """Show or hide the edge window."""
        self._enabled = enabled
        if enabled:
            self.show()
        else:
            self.hide()

    def update_state(self, label: int) -> None:
        """Change the bar color based on the latest prediction label."""
        color = Colors.FLOW if label == 1 else Colors.NO_FLOW
        self.setStyleSheet(f"background-color: {color};")

    def set_unknown(self) -> None:
        """Reset to the no-flow / unknown color."""
        self.setStyleSheet(f"background-color: {Colors.NO_FLOW};")
