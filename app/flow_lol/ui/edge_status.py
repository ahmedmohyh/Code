"""Screen-edge status indicator for Flow-LoL.

A small always-on-top box in the top-right corner of the selected monitor shows
the latest flow prediction and key session statuses. It is designed to stay
visible when the main app is minimized.

Note: League of Legends in exclusive fullscreen will cover every normal window,
including this one. Use borderless/windowed mode or place the box on a secondary
monitor if you want it visible while playing.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from flow_lol.ui.styles import Colors, Fonts


class EdgeStatusWindow(QWidget):
    """Floating box showing flow + sensor + game + webcam status."""

    WIDTH = 220
    HEIGHT = 130

    def __init__(self) -> None:
        # No parent so the window survives main-window minimize/hide.
        super().__init__(None)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        self._title = QLabel("Flow-LoL")
        self._title.setFont(QFont("Segoe UI", Fonts.SUBHEAD, QFont.Weight.Bold))
        self._title.setStyleSheet("color: white;")
        layout.addWidget(self._title)

        self._state = QLabel("—")
        self._state.setFont(QFont("Segoe UI", Fonts.HEAD, QFont.Weight.Bold))
        self._state.setStyleSheet("color: white;")
        layout.addWidget(self._state)

        # Indicator row: H10 | REC | LOL | GAME
        indicator_layout = QHBoxLayout()
        indicator_layout.setSpacing(8)

        self._h10_icon = QLabel("● H10")
        self._rec_icon = QLabel("● REC")
        self._lol_icon = QLabel("● LOL")
        self._game_icon = QLabel("● GAME")

        for lbl in (self._h10_icon, self._rec_icon, self._lol_icon, self._game_icon):
            lbl.setFont(QFont("Segoe UI", Fonts.SMALL, QFont.Weight.Bold))
            lbl.setStyleSheet(f"color: {Colors.TEXT_MUTED};")
            indicator_layout.addWidget(lbl)
        indicator_layout.addStretch(1)
        layout.addLayout(indicator_layout)

        self._detail = QLabel("No prediction yet")
        self._detail.setFont(QFont("Segoe UI", Fonts.SMALL))
        self._detail.setStyleSheet("color: white;")
        self._detail.setWordWrap(True)
        layout.addWidget(self._detail)

        self._enabled = False
        self._screen_index = -1
        self.hide()

        # Aggressively restore visibility after a fullscreen game (e.g. LoL)
        # releases the display. This timer is cheap when the window is already OK.
        self._restore_timer = QTimer(self)
        self._restore_timer.timeout.connect(self._restore_if_needed)
        self._restore_timer.start(1000)

    def _screen(self) -> object | None:
        """Return the QScreen to use, or primary screen if index is invalid."""
        screens = QApplication.screens()
        if not screens:
            return None
        if 0 <= self._screen_index < len(screens):
            return screens[self._screen_index]
        return QApplication.primaryScreen()

    def _position_on_screen(self) -> None:
        screen = self._screen()
        if screen is None:
            self.setGeometry(1668, 12, self.WIDTH, self.HEIGHT)
            return
        geo = screen.availableGeometry()
        x = geo.x() + geo.width() - self.WIDTH - 12
        y = geo.y() + 12
        self.setGeometry(x, y, self.WIDTH, self.HEIGHT)

    def set_screen_index(self, index: int) -> None:
        """Place the box on the given monitor (-1 means primary)."""
        self._screen_index = index
        if self._enabled:
            self._position_on_screen()
            self.show()
            self.raise_()

    def set_enabled(self, enabled: bool) -> None:
        """Show or hide the edge window."""
        self._enabled = enabled
        if enabled:
            self._position_on_screen()
            self.show()
            self.raise_()
        else:
            self.hide()

    def _restore_if_needed(self) -> None:
        if not self._enabled:
            return
        if not self.isVisible():
            self._position_on_screen()
            self.show()
            self.raise_()
            self.activateWindow()

    def update_state(self, label: int) -> None:
        """Update the box color and text based on the latest prediction label."""
        if label == 1:
            color = Colors.FLOW
            text = "FLOW"
        else:
            color = Colors.NO_FLOW
            text = "NO FLOW"
        self.setStyleSheet(
            f"background-color: {color};"
            f"border: 2px solid white;"
            f"border-radius: 8px;"
        )
        self._state.setText(text)
        self._detail.setText("Prediction updated")

    def set_unknown(self) -> None:
        """Reset to the no-flow / unknown state."""
        self.setStyleSheet(
            f"background-color: {Colors.NO_FLOW};"
            f"border: 2px solid white;"
            f"border-radius: 8px;"
        )
        self._state.setText("NO FLOW")
        self._detail.setText("No prediction yet")

    def set_detail(self, text: str) -> None:
        """Set a custom detail line, e.g. sensor or match status."""
        self._detail.setText(text)

    def set_h10_active(self, active: bool) -> None:
        self._h10_icon.setStyleSheet(f"color: {Colors.SUCCESS if active else Colors.TEXT_MUTED};")

    def set_recording(self, active: bool) -> None:
        self._rec_icon.setStyleSheet(f"color: {Colors.DANGER if active else Colors.TEXT_MUTED};")

    def set_lol_open(self, active: bool) -> None:
        self._lol_icon.setStyleSheet(f"color: {Colors.PRIMARY if active else Colors.TEXT_MUTED};")

    def set_in_match(self, active: bool) -> None:
        self._game_icon.setStyleSheet(f"color: {Colors.WARNING if active else Colors.TEXT_MUTED};")
