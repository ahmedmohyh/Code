"""Reusable UI widgets used across the Flow-LoL frontend."""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, Qt, pyqtProperty, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPaintEvent
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from flow_lol.ui.styles import Colors, Spacing


class CardWidget(QWidget):
    """White rounded panel with a thin border and optional header."""

    def __init__(
        self,
        title: Optional[str] = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setProperty("class", "CardWidget")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(Spacing.MD, Spacing.MD, Spacing.MD, Spacing.MD)
        layout.setSpacing(Spacing.SM)

        if title:
            self._header = QLabel(title)
            self._header.setProperty("role", "heading")
            layout.addWidget(self._header)
        else:
            self._header = None

        self._content = QVBoxLayout()
        self._content.setSpacing(Spacing.SM)
        layout.addLayout(self._content, stretch=1)

    def content_layout(self) -> QVBoxLayout:
        return self._content


class SidebarButton(QPushButton):
    """Checkable button for the vertical navigation sidebar."""

    def __init__(
        self,
        icon: str,
        label: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(f"{icon}  {label}", parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)


class ToggleActionButton(QPushButton):
    """Single button that toggles between an active and an idle state.

    Example:
        btn = ToggleActionButton(
            idle_text="▶ Start session",
            active_text="■ Stop session",
            idle_role="primary",
            active_role="danger",
        )
    """

    def __init__(
        self,
        idle_text: str,
        active_text: str,
        idle_role: str = "primary",
        active_role: str = "danger",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(idle_text, parent)
        self.idle_text = idle_text
        self.active_text = active_text
        self.idle_role = idle_role
        self.active_role = active_role
        self._active = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.set_active(False)

    def set_active(self, active: bool) -> None:
        self._active = active
        self.setText(self.active_text if active else self.idle_text)
        role = self.active_role if active else self.idle_role
        self.setProperty("role", role)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def is_active(self) -> bool:
        return self._active


class StatusPill(QLabel):
    """Small rounded badge used in the status bar."""

    def __init__(
        self,
        text: str = "",
        active: bool = False,
        warning: bool = False,
        danger: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(text, parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.set_active(active, warning=warning, danger=danger)

    def set_active(self, active: bool, warning: bool = False, danger: bool = False) -> None:
        self.setProperty("active", "true" if active else "false")
        self.setProperty("warning", "true" if warning else "false")
        self.setProperty("danger", "true" if danger else "false")
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def set_text(self, text: str) -> None:
        self.setText(text)


class IconLabel(QLabel):
    """Label with a small colored indicator dot."""

    def __init__(
        self,
        text: str = "",
        color: Optional[str] = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__("", parent)
        self._base_text = text
        self._color = color or Colors.TEXT_SECONDARY
        self.setText(self._render())

    def set_color(self, color: str) -> None:
        self._color = color
        self.setText(self._render())

    def set_text(self, text: str) -> None:
        self._base_text = text
        self.setText(self._render())

    def _render(self) -> str:
        # Unicode circle that takes the label's color.
        return f'<span style="color:{self._color}">●</span> {self._base_text}'


class CompactActionBar(QWidget):
    """Horizontal row of icon/text buttons with consistent spacing."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self._box = QHBoxLayout(self)
        self._box.setContentsMargins(0, 0, 0, 0)
        self._box.setSpacing(Spacing.SM)

    def add_button(self, text: str, role: str = "") -> QPushButton:
        btn = QPushButton(text)
        if role:
            btn.setProperty("role", role)
        self._box.addWidget(btn)
        return btn

    def add_stretch(self) -> None:
        self._box.addStretch(1)


class StatusLed(QWidget):
    """Small circular LED indicator."""

    def __init__(
        self,
        color: str = Colors.TEXT_MUTED,
        size: int = 12,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._color = color
        self._size = size
        self.setFixedSize(size, size)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)

    def set_color(self, color: str) -> None:
        self._color = color
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(self._color))
        painter.drawEllipse(0, 0, self._size, self._size)
        painter.end()


class Switch(QWidget):
    """Animated ON/OFF toggle switch.

    Emits toggled(bool) when the user changes the switch.
    """

    toggled = pyqtSignal(bool)

    _TRACK_WIDTH = 44
    _TRACK_HEIGHT = 24
    _KNOB_DIAMETER = 18

    def __init__(
        self,
        checked: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._checked = checked
        self._knob_x = self._end_x() if checked else self._start_x()
        self.setFixedSize(self._TRACK_WIDTH, self._TRACK_HEIGHT)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)

        self._animation = QPropertyAnimation(self, b"knob_x")
        self._animation.setDuration(120)
        self._animation.setEasingCurve(QEasingCurve.Type.InOutCubic)

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, checked: bool) -> None:
        if checked == self._checked:
            return
        self._checked = checked
        self._animate_to(self._end_x() if checked else self._start_x())
        self.update()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.setChecked(not self._checked)
            self.toggled.emit(self._checked)
        super().mousePressEvent(event)

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        track_color = Colors.SUCCESS if self._checked else Colors.BORDER
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(track_color))
        painter.drawRoundedRect(
            0,
            0,
            self._TRACK_WIDTH,
            self._TRACK_HEIGHT,
            self._TRACK_HEIGHT / 2,
            self._TRACK_HEIGHT / 2,
        )

        painter.setBrush(QColor(Colors.SURFACE))
        y = (self._TRACK_HEIGHT - self._KNOB_DIAMETER) / 2
        painter.drawEllipse(int(self._knob_x), int(y), self._KNOB_DIAMETER, self._KNOB_DIAMETER)
        painter.end()

    def _start_x(self) -> float:
        return 3.0

    def _end_x(self) -> float:
        return self._TRACK_WIDTH - self._KNOB_DIAMETER - 3.0

    def _animate_to(self, target: float) -> None:
        self._animation.stop()
        self._animation.setStartValue(self._knob_x)
        self._animation.setEndValue(target)
        self._animation.start()

    def get_knob_x(self) -> float:
        return self._knob_x

    def set_knob_x(self, value: float) -> None:
        self._knob_x = value
        self.update()

    knob_x = pyqtProperty(float, get_knob_x, set_knob_x)
