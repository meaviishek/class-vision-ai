"""Main window: sidebar + stacked pages."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QMainWindow, QMessageBox, QPushButton, QScrollArea,
                               QStackedWidget, QVBoxLayout, QWidget)

from ..config import APP_NAME
from .pages.dashboard import DashboardPage
from .pages.enroll import EnrollPage
from .pages.live import LivePage
from .pages.reports import ReportsPage
from .pages.settings import SettingsPage
from .pages.students import StudentsPage
from .pages.timetable import TimetablePage
from .widgets import offer_model_download

# (page key, sidebar text); None adds a thin divider between the live work and the records
NAV = [("dashboard", "Dashboard"), ("timetable", "Timetable"), ("class", "Class attendance"), ("exam", "Exam proctoring"), None,
       ("enroll", "Enroll students"), ("students", "Students"), ("reports", "Reports"), ("settings", "Settings")]


def first_window_size(width: int = 1440, height: int = 900, min_w: int = 900, min_h: int = 560):
    """1440 x 900 on a big screen, but never larger than the usable part of a small one."""
    screen = QGuiApplication.primaryScreen()
    if screen is not None:
        area = screen.availableGeometry()
        width, height = min(width, int(area.width() * 0.96)), min(height, int(area.height() * 0.94))
    return max(width, min_w), max(height, min_h)


def scrolling(page: QWidget) -> QScrollArea:
    """Wrap a page so that on a small screen it scrolls instead of forcing the window to be bigger than the screen.
    A page still fills the window when there is room."""
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setFrameShape(QFrame.Shape.NoFrame)
    area.setWidget(page)
    return area


class MainWindow(QMainWindow):
    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(900, 560)                 # laptops at 1366x768 (or 1080p at 150%) must be able to hold it
        self.resize(*first_window_size())

        self.pages = {
            "dashboard": DashboardPage(ctx, self.go),
            "timetable": TimetablePage(ctx, on_start_class=self.start_class_from_timetable),
            "class": LivePage(ctx, "class"),
            "exam": LivePage(ctx, "exam"),
            "enroll": EnrollPage(ctx),
            "students": StudentsPage(ctx),
            "reports": ReportsPage(ctx),
            "settings": SettingsPage(ctx),
        }
        self.stack = QStackedWidget()
        self.buttons = {}
        self.areas = {}                               # page key -> the scroll area that holds that page
        for key in (k[0] for k in NAV if k):
            self.areas[key] = scrolling(self.pages[key])
            self.stack.addWidget(self.areas[key])

        side = QFrame()
        side.setObjectName("sidebar")
        side.setFixedWidth(224)
        sl = QVBoxLayout(side)
        sl.setContentsMargins(0, 22, 0, 16)
        sl.setSpacing(0)
        brand = QLabel(APP_NAME)
        brand.setObjectName("brand")
        sub = QLabel("Attendance and exam monitoring")
        sub.setObjectName("brandSub")
        brand.setContentsMargins(20, 0, 0, 0)
        sub.setContentsMargins(20, 0, 0, 18)
        sl.addWidget(brand)
        sl.addWidget(sub)
        for item in NAV:
            if item is None:
                rule = QFrame()
                rule.setFixedHeight(1)
                rule.setStyleSheet("background: #2C4A66;")
                holder = QWidget()                     # the spacing lives on a wrapper: a 1 px frame cannot hold margins
                hl = QVBoxLayout(holder)
                hl.setContentsMargins(18, 10, 18, 10)
                hl.addWidget(rule)
                sl.addWidget(holder)
                continue
            key, text = item
            b = QPushButton(text)
            b.setProperty("role", "nav")
            b.setCheckable(True)
            b.setAutoExclusive(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _checked=False, k=key: self.go(k))
            self.buttons[key] = b
            sl.addWidget(b)
        sl.addStretch(1)
        note = QLabel("Face data stays on this computer.")
        note.setObjectName("brandSub")
        note.setContentsMargins(20, 0, 12, 0)
        note.setWordWrap(True)
        sl.addWidget(note)

        root = QWidget()
        rl = QHBoxLayout(root)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(0)
        rl.addWidget(side)
        rl.addWidget(self.stack, 1)
        self.setCentralWidget(root)
        self._current = None
        self.go("dashboard")

    def go(self, key: str) -> None:
        if key == self._current:
            return
        leaving = self.pages.get(self._current)
        if leaving is not None and hasattr(leaving, "on_leave"):
            leaving.on_leave()                         # e.g. the enrollment page releases the webcam
        self._current = key
        self.stack.setCurrentWidget(self.areas[key])
        self.buttons[key].setChecked(True)

    def start_class_from_timetable(self, slot: dict) -> None:
        self.go("class")
        self.pages["class"].load_timetable_slot(slot, auto_start=False)

    def prompt_models(self) -> None:
        if offer_model_download(self, "The face models are not installed yet. They are needed for recognition."):
            QMessageBox.information(self, "Models ready", "The face models are installed.")
        self.pages["dashboard"].refresh()

    def closeEvent(self, event) -> None:
        running = [self.pages[k] for k in ("class", "exam") if self.pages[k].is_running()]
        if running:
            ans = QMessageBox.question(self, "A session is running",
                                       "Stop it and save the results before closing?")
            if ans != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            for page in running:
                page.stop_if_running()
        self.pages["enroll"].on_leave()
        event.accept()
