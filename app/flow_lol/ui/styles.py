"""Central theme, colors, and stylesheet for the Flow-LoL UI.

Applying the stylesheet:

    from PyQt6.QtWidgets import QApplication
    from flow_lol.ui.styles import AppStyles

    app = QApplication.instance() or QApplication([])
    app.setStyleSheet(AppStyles.stylesheet())
"""

from __future__ import annotations

from typing import Final


class Colors:
    """Modern, low-saturation palette."""

    BG: Final[str] = "#f4f6f8"
    SURFACE: Final[str] = "#ffffff"
    SURFACE_DIM: Final[str] = "#eef0f2"

    PRIMARY: Final[str] = "#2563eb"
    PRIMARY_HOVER: Final[str] = "#1d4ed8"
    PRIMARY_PRESSED: Final[str] = "#1e40af"

    SUCCESS: Final[str] = "#10b981"
    SUCCESS_HOVER: Final[str] = "#059669"
    WARNING: Final[str] = "#f59e0b"
    DANGER: Final[str] = "#ef4444"
    DANGER_HOVER: Final[str] = "#dc2626"

    TEXT: Final[str] = "#111827"
    TEXT_SECONDARY: Final[str] = "#6b7280"
    TEXT_MUTED: Final[str] = "#9ca3af"
    BORDER: Final[str] = "#e5e7eb"

    DARK_PANEL: Final[str] = "#111827"
    DARK_PANEL_LIGHT: Final[str] = "#1f2937"

    FLOW: Final[str] = "#10b981"
    NO_FLOW: Final[str] = "#9ca3af"
    MATCH_REGION: Final[str] = "#dbeafe"


class Spacing:
    XS: Final[int] = 4
    SM: Final[int] = 8
    MD: Final[int] = 12
    LG: Final[int] = 16
    XL: Final[int] = 24

    RADIUS_SM: Final[int] = 6
    RADIUS_MD: Final[int] = 10
    RADIUS_LG: Final[int] = 14


class Fonts:
    """Font size hints (applied in points via stylesheet)."""

    SMALL: Final[int] = 9
    BODY: Final[int] = 10
    SUBHEAD: Final[int] = 12
    HEAD: Final[int] = 16


def stylesheet() -> str:
    """Return the global application stylesheet."""
    c = Colors
    s = Spacing

    return f"""
    /* ------------------------------------------------------------------ */
    /* Base                                                               */
    /* ------------------------------------------------------------------ */
    QMainWindow {{
        background: {c.BG};
    }}

    QWidget {{
        background: transparent;
        color: {c.TEXT};
        font-size: {Fonts.BODY}pt;
    }}

    /* Cards / panels ---------------------------------------------------- */
    CardWidget {{
        background: {c.SURFACE};
        border: 1px solid {c.BORDER};
        border-radius: {s.RADIUS_MD}px;
    }}

    QGroupBox {{
        background: {c.SURFACE};
        border: 1px solid {c.BORDER};
        border-radius: {s.RADIUS_MD}px;
        margin-top: 12px;
        padding-top: 8px;
        padding-bottom: 8px;
        padding-left: 12px;
        padding-right: 12px;
        font-weight: 500;
    }}

    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        left: 12px;
        padding: 0 6px;
        color: {c.TEXT_SECONDARY};
    }}

    /* Buttons ----------------------------------------------------------- */
    QPushButton {{
        background: {c.SURFACE_DIM};
        border: 1px solid {c.BORDER};
        border-bottom: 2px solid #9ca3af;
        border-radius: {s.RADIUS_SM}px;
        padding: 8px 16px;
        min-width: 110px;
        color: {c.TEXT};
        font-weight: 600;
    }}

    QPushButton:hover {{
        background: {c.BORDER};
        border-color: {c.TEXT_MUTED};
    }}

    QPushButton:pressed {{
        background: #d1d5db;
        border-bottom: 1px solid #9ca3af;
        margin-top: 1px;
    }}

    QPushButton:disabled {{
        background: {c.BORDER};
        color: {c.TEXT_MUTED};
        border-color: {c.BORDER};
        border-bottom: 2px solid {c.BORDER};
    }}

    QPushButton:checked {{
        background: {c.PRIMARY};
        border-color: {c.PRIMARY};
        border-bottom: 2px solid {c.PRIMARY_PRESSED};
        color: white;
    }}

    QPushButton:checked:hover {{
        background: {c.PRIMARY_HOVER};
        border-color: {c.PRIMARY_HOVER};
    }}

    /* Primary action button */
    QPushButton[role="primary"] {{
        background: {c.PRIMARY};
        border-color: {c.PRIMARY};
        border-bottom: 2px solid {c.PRIMARY_PRESSED};
        color: white;
    }}

    QPushButton[role="primary"]:hover {{
        background: {c.PRIMARY_HOVER};
        border-color: {c.PRIMARY_HOVER};
    }}

    QPushButton[role="primary"]:pressed {{
        background: {c.PRIMARY_PRESSED};
        border-color: {c.PRIMARY_PRESSED};
        border-bottom: 1px solid {c.PRIMARY_PRESSED};
        margin-top: 1px;
    }}

    /* Danger / stop button */
    QPushButton[role="danger"] {{
        background: {c.DANGER};
        border-color: {c.DANGER};
        border-bottom: 2px solid {c.DANGER_HOVER};
        color: white;
    }}

    QPushButton[role="danger"]:hover {{
        background: {c.DANGER_HOVER};
        border-color: {c.DANGER_HOVER};
    }}

    QPushButton[role="danger"]:pressed {{
        border-bottom: 1px solid {c.DANGER_HOVER};
        margin-top: 1px;
    }}

    /* Icon-only small button */
    QPushButton[role="icon"] {{
        padding: 6px 8px;
        font-size: {Fonts.SUBHEAD}pt;
    }}

    /* Sidebar button */
    SidebarButton {{
        background: transparent;
        border: none;
        border-radius: {s.RADIUS_SM}px;
        padding: 10px 12px;
        text-align: left;
        color: {c.TEXT_SECONDARY};
        font-weight: 500;
    }}

    SidebarButton:hover {{
        background: {c.SURFACE_DIM};
        color: {c.TEXT};
    }}

    SidebarButton:checked {{
        background: {c.SURFACE};
        color: {c.PRIMARY};
        border: 1px solid {c.BORDER};
    }}

    /* Inputs ------------------------------------------------------------ */
    QComboBox,
    QLineEdit,
    QSpinBox {{
        background: {c.SURFACE};
        border: 1px solid {c.BORDER};
        border-radius: {s.RADIUS_SM}px;
        padding: 6px 8px;
        min-height: 18px;
    }}

    QComboBox:hover,
    QLineEdit:hover,
    QSpinBox:hover {{
        border-color: {c.TEXT_MUTED};
    }}

    QComboBox::drop-down {{
        border: none;
        width: 24px;
    }}

    QComboBox::down-arrow {{
        image: none;
        border-left: 5px solid transparent;
        border-right: 5px solid transparent;
        border-top: 5px solid {c.TEXT_SECONDARY};
        width: 0px;
        height: 0px;
    }}

    QListWidget {{
        background: {c.SURFACE};
        border: 1px solid {c.BORDER};
        border-radius: {s.RADIUS_SM}px;
        padding: 4px;
        outline: 0;
    }}

    QListWidget::item {{
        border-radius: {s.RADIUS_SM}px;
        padding: 6px 8px;
    }}

    QListWidget::item:selected {{
        background: {c.PRIMARY};
        color: white;
    }}

    QListWidget::item:alternate {{
        background: {c.SURFACE_DIM};
    }}

    QPlainTextEdit {{
        background: {c.SURFACE};
        border: 1px solid {c.BORDER};
        border-radius: {s.RADIUS_SM}px;
        padding: 8px;
        font-family: Consolas, Monaco, monospace;
        font-size: {Fonts.SMALL}pt;
    }}

    /* Status bar / pills ------------------------------------------------ */
    QStatusBar {{
        background: {c.SURFACE};
        border-top: 1px solid {c.BORDER};
    }}

    StatusPill {{
        background: {c.SURFACE_DIM};
        border: 1px solid {c.BORDER};
        border-radius: 12px;
        padding: 2px 10px;
        color: {c.TEXT_SECONDARY};
        font-size: {Fonts.SMALL}pt;
    }}

    StatusPill[active="true"] {{
        background: {c.SUCCESS};
        border-color: {c.SUCCESS};
        color: white;
    }}

    StatusPill[warning="true"] {{
        background: {c.WARNING};
        border-color: {c.WARNING};
        color: white;
    }}

    StatusPill[danger="true"] {{
        background: {c.DANGER};
        border-color: {c.DANGER};
        color: white;
    }}

    /* Dialogs / message boxes ----------------------------------------- */
    QDialog {{
        background: {c.SURFACE};
    }}

    QDialog QLabel {{
        color: {c.TEXT};
    }}

    QMessageBox {{
        background: {c.SURFACE};
    }}

    QMessageBox QLabel {{
        color: {c.TEXT};
        font-size: {Fonts.BODY}pt;
    }}

    QMessageBox QPushButton {{
        min-width: 80px;
    }}

    /* Labels ------------------------------------------------------------ */
    QLabel {{
        color: {c.TEXT};
    }}

    QLabel[role="muted"] {{
        color: {c.TEXT_SECONDARY};
    }}

    QLabel[role="error"] {{
        color: {c.DANGER};
        font-weight: 600;
    }}

    QLabel[role="heading"] {{
        font-size: {Fonts.SUBHEAD}pt;
        font-weight: 600;
    }}

    QLabel[role="title"] {{
        font-size: {Fonts.HEAD}pt;
        font-weight: 700;
    }}

    /* Menu / tabs ------------------------------------------------------- */
    QMenuBar {{
        background: {c.SURFACE};
        color: {c.TEXT};
        border-bottom: 1px solid {c.BORDER};
    }}

    QMenuBar::item {{
        background: transparent;
        color: {c.TEXT};
        padding: 4px 12px;
    }}

    QMenuBar::item:selected {{
        background: {c.SURFACE_DIM};
        color: {c.TEXT};
    }}

    QMenu {{
        background: {c.SURFACE};
        color: {c.TEXT};
        border: 1px solid {c.BORDER};
        border-radius: {s.RADIUS_SM}px;
        padding: 4px 0px;
    }}

    QMenu::item {{
        background: transparent;
        color: {c.TEXT};
        padding: 6px 20px;
    }}

    QMenu::item:selected {{
        background: {c.PRIMARY};
        color: {c.SURFACE};
    }}

    QMenu::separator {{
        height: 1px;
        background: {c.BORDER};
        margin: 4px 8px;
    }}

    QTabWidget::pane {{
        border: 1px solid {c.BORDER};
        border-radius: {s.RADIUS_MD}px;
        background: {c.SURFACE};
        top: -1px;
    }}

    QTabBar::tab {{
        background: {c.SURFACE_DIM};
        border: 1px solid {c.BORDER};
        border-bottom: none;
        border-top-left-radius: {s.RADIUS_SM}px;
        border-top-right-radius: {s.RADIUS_SM}px;
        padding: 8px 14px;
        margin-right: 3px;
        color: {c.TEXT_SECONDARY};
        font-weight: 500;
    }}

    QTabBar::tab:hover {{
        background: {c.BORDER};
        color: {c.TEXT};
    }}

    QTabBar::tab:selected {{
        background: {c.SURFACE};
        color: {c.PRIMARY};
        border-bottom: 3px solid {c.PRIMARY};
        font-weight: 600;
    }}

    QTabBar::tab:!selected {{
        margin-top: 3px;
    }}

    QTabBar::tab:selected:!selected {{
        margin-top: 0px;
    }}

    /* Splitter ---------------------------------------------------------- */
    QSplitter::handle {{
        background: {c.BORDER};
    }}

    QSplitter::handle:horizontal {{
        width: 2px;
    }}

    QSplitter::handle:vertical {{
        height: 2px;
    }}

    /* Scroll bars ------------------------------------------------------- */
    QScrollBar:vertical {{
        background: {c.SURFACE_DIM};
        width: 8px;
        border-radius: 4px;
    }}

    QScrollBar::handle:vertical {{
        background: {c.TEXT_MUTED};
        border-radius: 4px;
        min-height: 20px;
    }}

    QScrollBar::handle:vertical:hover {{
        background: {c.TEXT_SECONDARY};
    }}

    QScrollBar::add-line:vertical,
    QScrollBar::sub-line:vertical {{
        height: 0px;
    }}

    QScrollBar:horizontal {{
        background: {c.SURFACE_DIM};
        height: 8px;
        border-radius: 4px;
    }}

    QScrollBar::handle:horizontal {{
        background: {c.TEXT_MUTED};
        border-radius: 4px;
        min-width: 20px;
    }}
    """
