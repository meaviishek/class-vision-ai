"""Reusable widgets and small helpers shared by the pages."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence, Tuple

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QThread, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QImage, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import (QAbstractItemView, QDialog, QFrame, QHeaderView, QLabel, QMessageBox,
                               QProgressBar, QPushButton, QSizePolicy, QStyledItemDelegate, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from ..services.attendance import breaks_between
from ..utils import fmt_clock, fmt_dur
from ..vision import models
from . import theme
from .theme import set_role

AL = Qt.AlignmentFlag


# ---------------------------------------------------------------- small factories
def label(text: str = "", role: Optional[str] = None, wrap: bool = False) -> QLabel:
    lab = QLabel(text)
    if role:
        set_role(lab, role)
    lab.setWordWrap(wrap)
    return lab


def button(text: str, role: Optional[str] = None, tip: str = "") -> QPushButton:
    b = QPushButton(text)
    if role:
        set_role(b, role)
    if tip:
        b.setToolTip(tip)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    return b


def panel() -> QFrame:
    f = QFrame()
    set_role(f, "panel")
    return f


# ------------------------------------------------------------------- video view
class VideoView(QWidget):
    """Shows the latest camera frame, letterboxed, with name boxes drawn by QPainter (Unicode-safe)."""

    def __init__(self, placeholder: str = "Camera is off", parent=None):
        super().__init__(parent)
        self._img: Optional[QImage] = None
        self._overlays: list = []
        self._placeholder = placeholder
        self.setMinimumSize(320, 220)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_frame(self, img: QImage) -> None:
        self._img = img
        self.update()

    def set_overlays(self, overlays: list) -> None:
        self._overlays = overlays
        self.update()

    def set_placeholder(self, text: str) -> None:
        self._placeholder = text
        self.update()

    def clear(self) -> None:
        self._img, self._overlays = None, []
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        r = self.rect()
        p.fillRect(r, QColor(theme.VIDEO_BG))
        if self._img is None:
            p.setPen(QColor("#7F93A8"))
            p.drawText(r, AL.AlignCenter.value, self._placeholder)
            return
        iw, ih = self._img.width(), self._img.height()
        scale = min(r.width() / iw, r.height() / ih)
        w, h = iw * scale, ih * scale
        x0, y0 = (r.width() - w) / 2, (r.height() - h) / 2
        p.drawImage(QRectF(x0, y0, w, h), self._img)
        font = QFont(p.font())
        font.setPixelSize(12)
        font.setBold(True)
        p.setFont(font)
        fm = p.fontMetrics()
        for o in self._overlays:
            box = QRectF(x0 + o.x * w, y0 + o.y * h, o.w * w, o.h * h)
            colour = QColor(o.color)
            p.setPen(QPen(colour, 2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(box, 3, 3)
            text = " - ".join(t for t in (o.label, o.sub) if t)
            if not text:
                continue
            tw, th = fm.horizontalAdvance(text) + 12, fm.height() + 4
            top = box.top() - th if box.top() - th >= y0 else box.top()
            chip = QRectF(box.left(), top, tw, th)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(colour)
            p.drawRoundedRect(chip, 3, 3)
            p.setPen(QColor("#0B1620"))
            p.drawText(chip, AL.AlignCenter.value, text)


# ----------------------------------------------------------------- presence bar
def paint_presence(p: QPainter, rect: QRectF, start: float, end: float, intervals: Iterable,
                   check_in: Optional[float] = None, check_out: Optional[float] = None,
                   now: Optional[float] = None) -> None:
    """One student's class timeline: filled = seen in the room, empty = away, markers = gate checks."""
    total = max(1.0, end - start)

    def x_of(t: float) -> float:
        return rect.left() + (min(max(t, start), end) - start) / total * rect.width()

    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(theme.TRACK))
    p.drawRoundedRect(rect, 3, 3)
    p.setBrush(QColor(theme.GREEN))
    for a, b in intervals:
        if b < start or a > end:
            continue
        x0, x1 = x_of(a), x_of(b)
        p.drawRect(QRectF(x0, rect.top(), max(2.0, x1 - x0), rect.height()))
    p.setBrush(QColor(theme.INK))
    if check_in is not None:
        x = x_of(check_in)
        p.drawPolygon(QPolygonF([QPointF(x - 3.5, rect.top() - 6), QPointF(x + 3.5, rect.top() - 6),
                                 QPointF(x, rect.top() - 1)]))
    if check_out is not None:
        x = x_of(check_out)
        p.drawPolygon(QPolygonF([QPointF(x - 3.5, rect.bottom() + 6), QPointF(x + 3.5, rect.bottom() + 6),
                                 QPointF(x, rect.bottom() + 1)]))
    if now is not None and start <= now <= end:
        p.setPen(QPen(QColor(theme.RED), 1.5))
        x = x_of(now)
        p.drawLine(QPointF(x, rect.top() - 3), QPointF(x, rect.bottom() + 3))


@dataclass
class PresenceData:
    """What a presence-bar cell needs. A plain object (not a dict) so Qt stores it untouched."""
    start: float
    end: float
    intervals: List[Tuple[float, float]]
    check_in: Optional[float] = None
    check_out: Optional[float] = None
    now: Optional[float] = None


class PresenceDelegate(QStyledItemDelegate):
    """Paints the presence bar in a table cell whose UserRole data is a PresenceData."""

    def paint(self, painter, option, index) -> None:
        super().paint(painter, option, index)
        d = index.data(Qt.ItemDataRole.UserRole)
        if not d:
            return
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(option.rect).adjusted(6, 12, -6, -12)
        paint_presence(painter, rect, d.start, d.end, d.intervals, d.check_in, d.check_out, d.now)
        painter.restore()

    def sizeHint(self, option, index) -> QSize:
        return QSize(220, 34)


class TimelineWidget(QWidget):
    """Large version of the presence bar with a time axis and labelled breaks."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._d = None
        self.setMinimumHeight(92)

    def set_data(self, start, end, intervals, check_in=None, check_out=None) -> None:
        self._d = (start, end, list(intervals), check_in, check_out)
        self.update()

    def clear(self) -> None:
        self._d = None
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        small = QFont(p.font())
        small.setPixelSize(11)
        p.setFont(small)
        if self._d is None:
            p.setPen(QColor(theme.MUTED))
            p.drawText(self.rect(), AL.AlignCenter.value, "Select a student to see when they were in the room.")
            return
        start, end, intervals, ci, co = self._d
        bar = QRectF(12, 34, self.width() - 24, 22)
        paint_presence(p, bar, start, end, intervals, ci, co)
        total = max(1.0, end - start)
        step = 600 if total <= 7200 else 1800
        p.setPen(QColor(theme.MUTED))
        t = start
        while t <= end + 1:
            x = bar.left() + (t - start) / total * bar.width()
            p.drawLine(QPointF(x, bar.bottom() + 8), QPointF(x, bar.bottom() + 12))
            p.drawText(QPointF(x - 14, bar.bottom() + 25), fmt_clock(t, False))
            t += step
        for a, b in breaks_between(intervals, start, end):
            x0 = bar.left() + (a - start) / total * bar.width()
            x1 = bar.left() + (b - start) / total * bar.width()
            if x1 - x0 > 54:
                p.drawText(QRectF(x0, bar.top() - 20, x1 - x0, 14), AL.AlignCenter.value, f"break {fmt_dur(b - a)}")
        p.setPen(QColor(theme.MUTED))
        p.drawText(QPointF(12, 14), "Green: in the room.  Triangles: check-in above the bar, check-out below it.")


# ---------------------------------------------------------------------- banner
BANNER_STYLE = {"ok": (theme.GREEN, theme.GREEN_BG), "info": (theme.MUTED, "#EAEFF4"),
                "warn": (theme.AMBER, theme.AMBER_BG), "bad": (theme.RED, theme.RED_BG)}


class Banner(QLabel):
    def __init__(self, text: str = "", kind: str = "info", parent=None):
        super().__init__(parent)
        self.setWordWrap(True)
        self.setMinimumHeight(46)
        self.set_state(kind, text)

    def set_state(self, kind: str, text: str) -> None:
        fg, bg = BANNER_STYLE.get(kind, BANNER_STYLE["info"])
        self.setStyleSheet(f"background: {bg}; color: {fg}; border-radius: 6px; padding: 10px 14px; "
                           f"font-size: 15px; font-weight: bold;")
        self.setText(text)


# ----------------------------------------------------------------------- tables
def make_table(headers: Sequence[str], stretch: Sequence[int] = (), row_height: int = 34) -> QTableWidget:
    t = QTableWidget(0, len(headers))
    t.setHorizontalHeaderLabels(list(headers))
    t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    t.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    t.setAlternatingRowColors(True)
    t.setShowGrid(False)
    t.setWordWrap(False)
    t.verticalHeader().setVisible(False)
    t.verticalHeader().setDefaultSectionSize(row_height)
    head = t.horizontalHeader()
    head.setHighlightSections(False)
    head.setStretchLastSection(False)
    for i in range(len(headers)):
        head.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch if i in stretch
                                  else QHeaderView.ResizeMode.ResizeToContents)
    return t


def set_cell(table: QTableWidget, row: int, col: int, text: str, bold: bool = False,
             fg: Optional[str] = None, bg: Optional[str] = None, data=None, center: bool = False) -> QTableWidgetItem:
    item = table.item(row, col)
    if item is None:
        item = QTableWidgetItem()
        table.setItem(row, col, item)
    item.setText(text)
    font = item.font()
    font.setBold(bold)
    item.setFont(font)
    item.setForeground(QBrush(QColor(fg)) if fg else QBrush(QColor(theme.TEXT)))
    item.setBackground(QBrush(QColor(bg)) if bg else QBrush())
    item.setData(Qt.ItemDataRole.UserRole, data)
    item.setTextAlignment(AL.AlignCenter if center else (AL.AlignLeft | AL.AlignVCenter))
    return item


def set_status_cell(table: QTableWidget, row: int, col: int, status: str, text: Optional[str] = None) -> None:
    fg, bg = theme.STATUS_STYLE.get(status, (theme.TEXT, None))
    set_cell(table, row, col, text or status.capitalize(), bold=True, fg=fg, bg=bg, center=True)


RISK_HEADERS = ["Student", "Level", "Score", "Looking away", "Look-aways", "Not visible", "Objects", "Flags"]


def fill_risk_table(t: QTableWidget, rows: list) -> None:
    """Fill the suspicion-ranking table (rows come from ProctorEngine.summary or Database.risk)."""
    t.setRowCount(len(rows))
    for i, r in enumerate(rows):
        set_cell(t, i, 0, r["name"])
        set_status_cell(t, i, 1, r["level"], r["level"].capitalize())
        set_cell(t, i, 2, f"{r['score']:.0f}", center=True)
        set_cell(t, i, 3, f"{r.get('away_pct', 0):.0f}%", center=True)
        set_cell(t, i, 4, str(r.get("glances", 0)), center=True)
        set_cell(t, i, 5, fmt_dur(r.get("missing_sec", 0)), center=True)
        set_cell(t, i, 6, str(r.get("objects", 0)), center=True)
        set_cell(t, i, 7, str(r.get("flags", 0)), center=True)


# --------------------------------------------------------------- model download
class _DownloadThread(QThread):
    progress = Signal(str, int, int)
    done = Signal(str)             # empty string = success, otherwise the error text

    def run(self) -> None:
        try:
            models.download_models(lambda name, got, total: self.progress.emit(name, got, total))
            self.done.emit("")
        except Exception as exc:   # network errors etc. are reported to the user, not raised
            self.done.emit(str(exc) or exc.__class__.__name__)


class ModelDownloadDialog(QDialog):
    """Downloads the two face models (about 39 MB) with a progress bar."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Download face models")
        self.setModal(True)
        self.setMinimumWidth(460)
        lay = QVBoxLayout(self)
        lay.setSpacing(10)
        self.info = label("Downloading the face detection and recognition models (about 39 MB).", wrap=True)
        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.close_btn = button("Please wait...")
        self.close_btn.setEnabled(False)               # a blocking download cannot be cancelled safely
        self.close_btn.clicked.connect(self.reject)
        lay.addWidget(self.info)
        lay.addWidget(self.bar)
        lay.addWidget(self.close_btn, 0, AL.AlignRight)
        self._thread = _DownloadThread(self)
        self._thread.progress.connect(self._on_progress)
        self._thread.done.connect(self._on_done)
        self._started = False
        self.ok = False

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self._started:                         # showEvent also fires on restore from minimised
            self._started = True
            self._thread.start()

    def _on_progress(self, name: str, got: int, total: int) -> None:
        self.info.setText(f"Downloading {name}")
        self.bar.setValue(int(100 * got / total) if total else 0)

    def _on_done(self, error: str) -> None:
        self._thread.wait(2000)                   # the thread is just about to return; let it finish
        if error:
            self.info.setText(f"The download failed.\n{error}\n\nCheck your internet connection and try again, "
                              f"or download the .onnx files in a browser and put them in {models.DETECTOR.parent}.")
            self.close_btn.setText("Close")
            self.close_btn.setEnabled(True)
        else:
            self.ok = True
            self.accept()

    def reject(self) -> None:
        if self._thread.isRunning():
            return                            # ignore Esc / window close until the download ends
        super().reject()


def offer_model_download(parent, message: str) -> bool:
    """Ask whether to download the face models now. Returns True once they are installed."""
    ans = QMessageBox.question(parent, "Face models needed", f"{message}\n\nDownload them now (about 39 MB)?")
    if ans != QMessageBox.StandardButton.Yes:
        return False
    dlg = ModelDownloadDialog(parent)
    dlg.exec()
    return dlg.ok
