"""Visual identity. Light, paper-like workspace with an ink-blue sidebar; colour is reserved for status.

Tokens
    ink      #14304A   sidebar, headings, primary actions
    paper    #F2F4F6   window background        surface #FFFFFF  panels and tables
    rule     #D9DFE5   borders                  marigold #F2B84B only the active-page marker
    present  #178A5C   review #8A5A0C   absent #B03A2E   (each with a pale tint for table cells)
"""
from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

INK, INK_HOVER, INK_ACTIVE, MARIGOLD = "#14304A", "#1E4467", "#23496C", "#F2B84B"
PAPER, SURFACE, RULE, TEXT, MUTED = "#F2F4F6", "#FFFFFF", "#D9DFE5", "#1C2631", "#5E6E7E"
GREEN, GREEN_BG = "#178A5C", "#E3F4EC"
AMBER, AMBER_BG = "#8A5A0C", "#FBF1DC"
RED, RED_BG = "#B03A2E", "#FBE7E4"
BLUE = "#2F6FB5"
TRACK = "#E3E8ED"
VIDEO_BG = "#0E1822"

STATUS_STYLE = {                       # status -> (text colour, cell tint)
    "PRESENT": (GREEN, GREEN_BG),
    "REVIEW": (AMBER, AMBER_BG),
    "ABSENT": (RED, RED_BG),
    "CRITICAL": ("#7F1D1D", "#FEE2E2"),
    "HIGH": (RED, RED_BG),
    "MEDIUM": (AMBER, AMBER_BG),
    "LOW": (GREEN, GREEN_BG),
    "NORMAL": (GREEN, GREEN_BG),
    "Pending Review": (AMBER, AMBER_BG),
    "Confirmed Concern": (RED, RED_BG),
    "False Positive": (MUTED, "#F3F4F6"),
    "Resolved": (GREEN, GREEN_BG),
    "Escalated": ("#7F1D1D", "#FEE2E2"),
}

QSS = f"""
* {{ font-family: "Segoe UI", "SF Pro Text", "Helvetica Neue", "Noto Sans", "Ubuntu", sans-serif; font-size: 13px; }}
QLabel {{ background: transparent; color: {TEXT}; }}
QLabel[role="title"] {{ font-size: 24px; font-weight: bold; color: {INK}; }}
QLabel[role="section"] {{ font-size: 15px; font-weight: bold; color: {INK}; }}
QLabel[role="muted"] {{ color: {MUTED}; }}
QLabel[role="hint"] {{ color: {MUTED}; font-size: 12px; }}
QLabel[role="metric"] {{ font-size: 15px; font-weight: bold; color: {INK}; }}
QLabel#brand {{ color: #FFFFFF; font-size: 19px; font-weight: bold; }}
QLabel#brandSub {{ color: #9FB4C8; font-size: 12px; }}

QFrame[role="panel"] {{ background: {SURFACE}; border: 1px solid {RULE}; border-radius: 6px; }}
QFrame#sidebar {{ background: {INK}; }}

QPushButton {{ background: {SURFACE}; border: 1px solid #C5CED8; border-radius: 4px; padding: 7px 14px; color: {INK}; }}
QPushButton:hover {{ background: #EEF2F6; }}
QPushButton:pressed {{ background: #E3E9EF; }}
QPushButton:disabled {{ color: #9AA8B5; background: #F4F6F8; border-color: #E1E6EB; }}
QPushButton[role="primary"] {{ background: {INK}; color: #FFFFFF; border: 1px solid {INK}; font-weight: bold; }}
QPushButton[role="primary"]:hover {{ background: {INK_HOVER}; }}
QPushButton[role="primary"]:disabled {{ background: #8FA2B5; border-color: #8FA2B5; color: #EEF2F6; }}
QPushButton[role="danger"] {{ color: {RED}; border-color: #E3B5AF; }}
QPushButton[role="danger"]:hover {{ background: {RED_BG}; }}
QPushButton[role="nav"] {{ background: transparent; color: #B9C8D6; border: none; border-radius: 0;
    border-left: 4px solid transparent; text-align: left; padding: 11px 18px; font-size: 14px; }}
QPushButton[role="nav"]:hover {{ background: {INK_HOVER}; color: #FFFFFF; }}
QPushButton[role="nav"]:checked {{ background: {INK_ACTIVE}; color: #FFFFFF; font-weight: bold;
    border-left: 4px solid {MARIGOLD}; }}
QFrame[role="action"] {{ border: 1px solid {RULE}; border-radius: 6px; background: {SURFACE}; }}
QFrame[role="action"]:hover {{ border-color: {INK}; background: #F7F9FB; }}
QFrame[role="action"]:focus {{ border: 2px solid {BLUE}; }}

QTableWidget, QListWidget {{ background: {SURFACE}; alternate-background-color: #F7F9FB; border: 1px solid {RULE};
    border-radius: 6px; selection-background-color: #DCE9F7; selection-color: {INK}; outline: 0; }}
QTableWidget::item {{ padding: 0 8px; }}
QHeaderView::section {{ background: #EEF2F6; color: #41546A; border: none; border-bottom: 1px solid {RULE};
    padding: 8px 10px; font-weight: bold; }}
QTableCornerButton::section {{ background: #EEF2F6; border: none; }}

QTabWidget::pane {{ border: 1px solid {RULE}; background: {SURFACE}; border-radius: 6px; top: -1px; }}
QTabBar::tab {{ background: transparent; color: {MUTED}; padding: 9px 18px; border: none; border-bottom: 2px solid transparent; }}
QTabBar::tab:selected {{ color: {INK}; font-weight: bold; border-bottom: 2px solid {INK}; }}
QTabBar::tab:hover:!selected {{ color: {INK}; }}

QProgressBar {{ background: #E8EDF2; border: none; border-radius: 4px; height: 8px; text-align: center; color: transparent; }}
QProgressBar::chunk {{ background: {INK}; border-radius: 4px; }}
QScrollArea {{ border: none; background: transparent; }}
QToolTip {{ background: {INK}; color: #FFFFFF; border: none; padding: 5px 8px; }}
QGroupBox {{ border: 1px solid {RULE}; border-radius: 6px; margin-top: 10px; padding-top: 10px; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 4px; color: {INK}; font-weight: bold; }}
"""


def apply_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    pal = QPalette()
    roles = {
        QPalette.ColorRole.Window: PAPER, QPalette.ColorRole.WindowText: TEXT,
        QPalette.ColorRole.Base: SURFACE, QPalette.ColorRole.AlternateBase: "#F7F9FB",
        QPalette.ColorRole.Text: TEXT, QPalette.ColorRole.Button: SURFACE, QPalette.ColorRole.ButtonText: INK,
        QPalette.ColorRole.Highlight: INK, QPalette.ColorRole.HighlightedText: "#FFFFFF",
        QPalette.ColorRole.ToolTipBase: INK, QPalette.ColorRole.ToolTipText: "#FFFFFF",
        QPalette.ColorRole.PlaceholderText: "#8A98A6", QPalette.ColorRole.Link: BLUE,
    }
    for role, colour in roles.items():
        pal.setColor(role, QColor(colour))
    app.setPalette(pal)
    app.setStyleSheet(QSS)


def set_role(widget, role: str):
    """Tag a widget so the stylesheet can pick it up (role='primary', 'danger', 'title', ...)."""
    widget.setProperty("role", role)
    return widget
