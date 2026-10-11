"""Reusable UI widgets used across the Flow-LoL frontend."""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt
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
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.set_active(False)

    def set_active(self, active: bool) -> None:
        self.setText(self.active_text if active else self.idle_text)
        role = self.active_role if active else self.idle_role
        self.setProperty("role", role)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def is_active(self) -> bool:
        return self.text() == self.active_text


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
