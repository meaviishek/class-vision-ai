"""Dashboard: where to start, whether the system is ready, and what happened recently."""
from __future__ import annotations

import importlib.util
from typing import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QVBoxLayout, QWidget

from ...config import DATA_DIR
from ...utils import fmt_datetime
from ...vision import models
from .. import theme
from ..theme import set_role
from ..widgets import button, label, make_table, offer_model_download, panel, set_cell

AL = Qt.AlignmentFlag


class ActionCard(QFrame):
    """A big clickable card. A frame (not a button) so its height follows the wrapped text inside it.
    Works with the mouse and from the keyboard (Tab to focus, Enter or Space to open)."""
    clicked = Signal()

    def __init__(self, title: str, text: str, parent=None):
        super().__init__(parent)
        set_role(self, "action")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 12, 18, 12)
        lay.setSpacing(3)
        for w in (label(title, "section"), label(text, "muted", wrap=True)):
            w.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            lay.addWidget(w)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit()
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.clicked.emit()
        else:
            super().keyPressEvent(event)


class DashboardPage(QWidget):
    def __init__(self, ctx, navigate: Callable[[str], None], parent=None):
        super().__init__(parent)
        self.ctx = ctx
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 20)
        root.setSpacing(14)
        root.addWidget(label("Dashboard", "title"))
        root.addWidget(label("Start a session, enroll people, or check that the system is ready.", "muted"))

        body = QHBoxLayout()
        body.setSpacing(22)
        root.addLayout(body, 1)

        left = QVBoxLayout()
        left.setSpacing(10)
        for title, text, page in (
                ("Take class attendance", "Check-in at the gate, tracking in the room, check-out at the end.", "class"),
                ("Class timetable & schedule", "Create daily timetable and schedule classes for each day of the week.", "timetable"),
                ("Proctor an exam",
                 "Attendance plus alerts for looking away, missing faces, unknown people and phones.", "exam"),
                ("Enroll a student",
                 "Capture face photos and details once; they are recognised from then on.", "enroll")):
            card = ActionCard(title, text)
            card.clicked.connect(lambda page=page: navigate(page))
            left.addWidget(card)
        left.addSpacing(6)
        check = panel()
        grid = QGridLayout(check)
        grid.setContentsMargins(16, 12, 16, 14)
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(8)
        grid.addWidget(label("System check", "section"), 0, 0, 1, 3)
        self.models_state = label("", "metric")
        self.people_state = label("", "metric")
        self.objects_state = label("", "metric")
        self.models_btn = button("Download")
        self.models_btn.clicked.connect(self._download)
        grid.addWidget(label("Face models", "muted"), 1, 0)
        grid.addWidget(self.models_state, 1, 1)
        grid.addWidget(self.models_btn, 1, 2)
        grid.addWidget(label("People enrolled", "muted"), 2, 0)
        grid.addWidget(self.people_state, 2, 1, 1, 2)
        grid.addWidget(label("Phone detection", "muted"), 3, 0)
        grid.addWidget(self.objects_state, 3, 1, 1, 2)
        grid.addWidget(label("Data folder", "muted"), 4, 0)
        folder = label(str(DATA_DIR), "hint", wrap=True)
        grid.addWidget(folder, 4, 1, 1, 2)
        grid.setColumnStretch(1, 1)
        left.addWidget(check)
        left.addStretch(1)
        body.addLayout(left, 4)

        right = QVBoxLayout()
        right.addWidget(label("Recent sessions", "section"))
        self.recent = make_table(["Date", "Session", "Type", "Present", "Alerts"], stretch=[1])
        self.empty = label("Nothing yet. Your sessions will be listed here.", "muted")
        self.empty.setAlignment(AL.AlignCenter)
        right.addWidget(self.recent, 1)
        right.addWidget(self.empty)
        body.addLayout(right, 6)

        ctx.students_changed.connect(self.refresh)
        ctx.sessions_changed.connect(self.refresh)
        self.refresh()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.refresh()

    def _paint(self, lab, text: str, ok: bool) -> None:
        lab.setText(text)
        lab.setStyleSheet(f"color: {theme.GREEN if ok else theme.RED};")

    def refresh(self) -> None:
        stats = self.ctx.db.stats()
        ready = not models.missing_models()
        self._paint(self.models_state, "Ready" if ready else "Missing: download them to start", ready)
        self.models_btn.setVisible(not ready)
        has_people = stats["students"] > 0
        self._paint(self.people_state,
                    f"{stats['students']} students, {stats['staff']} staff, {stats['samples']} photos"
                    if has_people else "No students yet. Enroll the first one.", has_people)
        has_yolo = importlib.util.find_spec("ultralytics") is not None
        self.objects_state.setText("Available" if has_yolo else "Not installed (optional: pip install ultralytics)")
        self.objects_state.setStyleSheet(f"color: {theme.GREEN if has_yolo else theme.MUTED};")

        rows = self.ctx.db.list_sessions(limit=8)
        t = self.recent
        t.setRowCount(len(rows))
        for i, r in enumerate(rows):
            done = r["status"] != "running"
            set_cell(t, i, 0, fmt_datetime(r["start_ts"]))
            set_cell(t, i, 1, r["title"])
            set_cell(t, i, 2, "Exam" if r["kind"] == "exam" else "Class")
            set_cell(t, i, 3, f"{r['n_present']}/{r['n_total']}" if done else "running", center=True)
            set_cell(t, i, 4, str(r["n_alerts"]) if r["kind"] == "exam" else "-", center=True)
        self.empty.setVisible(not rows)
        t.setVisible(bool(rows))

    def _download(self) -> None:
        offer_model_download(self, "The face detection and recognition models are not installed.")
        self.refresh()
