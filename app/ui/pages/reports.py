"""Reports page: review finished sessions, correct results by hand, export CSV."""
from __future__ import annotations

import os
import shutil
from collections import Counter
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QFileDialog, QHBoxLayout, QInputDialog, QLabel, QMessageBox, QSplitter, QTabWidget,
                               QVBoxLayout, QWidget)

from ...config import DATA_DIR, EVIDENCE_DIR, EXPORT_DIR
from ...services.attendance import breaks_between
from ...services.exports import export_attendance_csv, export_events_csv, export_risk_csv
from ...services.proctor import EVENT_INFO
from ...utils import fmt_clock, fmt_datetime, fmt_dur
from .. import theme
from ..proctor_dialogs import AlertReviewDialog, generate_proctoring_html_report
from ..widgets import (RISK_HEADERS, PresenceData, PresenceDelegate, TimelineWidget, button, fill_risk_table, label,
                       make_table, set_cell, set_status_cell)

AL = Qt.AlignmentFlag
SEVERITY_COLOUR = {3: theme.RED, 2: theme.AMBER, 1: theme.MUTED}
ATT_COLS = ["Reg. no", "Name", "Result", "Check-in", "Check-out", "In class", "Presence", "Breaks", "Reason"]


class ReportsPage(QWidget):
    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self._sid: Optional[int] = None
        self._build()
        ctx.sessions_changed.connect(self.refresh)
        ctx.students_changed.connect(self.refresh)
        self.refresh()

    # ------------------------------------------------------------------ layout
    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 20)
        root.setSpacing(12)
        root.addWidget(label("Reports", "title"))
        root.addWidget(label("Review any finished session, fix a result by hand, and export it for your records.",
                             "muted", wrap=True))
        split = QSplitter(Qt.Orientation.Horizontal)

        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 8, 0)
        self.sessions = make_table(["Date", "Session", "Present"], stretch=[1])
        self.sessions.setMinimumWidth(380)
        self.sessions.itemSelectionChanged.connect(self._on_session_selected)
        self.empty = label("No sessions yet. Start a class to see its attendance here.", "muted", wrap=True)
        self.empty.setAlignment(AL.AlignCenter)
        ll.addWidget(self.sessions, 1)
        ll.addWidget(self.empty)
        split.addWidget(left)

        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(8, 0, 0, 0)
        self.summary = label("Select a session on the left.", "section", wrap=True)
        self.counts = label("", "muted")
        rl.addWidget(self.summary)
        rl.addWidget(self.counts)
        self.tabs = QTabWidget()

        att = QWidget()
        al = QVBoxLayout(att)
        al.setContentsMargins(8, 8, 8, 8)
        self.att = make_table(ATT_COLS, stretch=[6, 8], row_height=36)
        self.att.setItemDelegateForColumn(6, PresenceDelegate(self.att))
        self.att.itemSelectionChanged.connect(self._on_student_selected)
        self.timeline = TimelineWidget()
        al.addWidget(self.att, 1)
        al.addWidget(self.timeline)
        self.tabs.addTab(att, "Attendance")

        alerts = QWidget()
        xl = QVBoxLayout(alerts)
        xl.setContentsMargins(8, 8, 8, 8)
        self.alerts = make_table(["Time", "Student / Origin", "Event / Instruction", "Severity", "Confidence", "Status", "Remarks", "Detail"], stretch=[7])
        self.alerts.itemSelectionChanged.connect(self._show_evidence)
        self.evidence = QLabel("Select an alert to see its snapshot.")
        self.evidence.setAlignment(AL.AlignCenter)
        self.evidence.setMinimumHeight(150)
        xl.addWidget(self.alerts, 3)
        xl.addWidget(self.evidence, 2)

        rev_row = QHBoxLayout()
        rev_row.addStretch(1)
        self.rev_btn = button("Update Review Decision...", "primary")
        self.rev_btn.clicked.connect(self._review_alert)
        rev_row.addWidget(self.rev_btn)
        xl.addLayout(rev_row)

        self.tabs.addTab(alerts, "Alerts & Instruction Logs")

        self.ranking = make_table(RISK_HEADERS, stretch=[0])
        self.tabs.addTab(self.ranking, "Suspicion ranking")
        rl.addWidget(self.tabs, 1)

        bar = QHBoxLayout()
        self.set_btn = button("Set status by hand...")
        self.exp_att = button("Export attendance (CSV)", "primary")
        self.exp_ev = button("Export alerts (CSV)")
        self.exp_risk = button("Export ranking (CSV)")
        self.exp_html = button("Export Proctoring Report (HTML)", "primary")
        self.del_btn = button("Delete session", "danger")
        self.set_btn.clicked.connect(self._override)
        self.exp_att.clicked.connect(lambda: self._export("attendance", export_attendance_csv))
        self.exp_ev.clicked.connect(lambda: self._export("alerts", export_events_csv))
        self.exp_risk.clicked.connect(lambda: self._export("ranking", export_risk_csv))
        self.exp_html.clicked.connect(self._export_html_report)
        self.del_btn.clicked.connect(self._delete)
        bar.addWidget(self.del_btn)
        bar.addStretch(1)
        for b in (self.set_btn, self.exp_ev, self.exp_risk, self.exp_html, self.exp_att):
            bar.addWidget(b)
        rl.addLayout(bar)
        split.addWidget(right)
        split.setStretchFactor(0, 4)
        split.setStretchFactor(1, 7)
        root.addWidget(split, 1)
        self._enable_actions(False)

    def _enable_actions(self, on: bool) -> None:
        for b in (self.set_btn, self.exp_att, self.exp_ev, self.exp_risk, self.exp_html, self.del_btn):
            b.setEnabled(on)

    # -------------------------------------------------------------- session list
    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.refresh()

    def refresh(self) -> None:
        rows = self.ctx.db.list_sessions()
        t = self.sessions
        t.blockSignals(True)
        t.setRowCount(len(rows))
        keep = None
        for i, r in enumerate(rows):
            title = r["title"] + ("  (exam)" if r["kind"] == "exam" else "")
            result = f"{r['n_present']}/{r['n_total']}" if r["status"] != "running" else "running"
            set_cell(t, i, 0, fmt_datetime(r["start_ts"]), data=r["id"])
            set_cell(t, i, 1, title)
            set_cell(t, i, 2, result, center=True)
            if r["id"] == self._sid:
                keep = i
        t.blockSignals(False)
        self.empty.setVisible(not rows)
        t.setVisible(bool(rows))
        if keep is not None:
            t.selectRow(keep)
            self._load(self._sid)
        elif self._sid is not None:
            self._sid = None
            self._clear_details()

    def _on_session_selected(self) -> None:
        rows = self.sessions.selectionModel().selectedRows()
        if rows:
            self._load(self.sessions.item(rows[0].row(), 0).data(Qt.ItemDataRole.UserRole))

    def _clear_details(self) -> None:
        self.summary.setText("Select a session on the left.")
        self.counts.setText("")
        for t in (self.att, self.alerts, self.ranking):
            t.setRowCount(0)
        self.timeline.clear()
        self._enable_actions(False)

    # ------------------------------------------------------------------- details
    def _load(self, sid: int) -> None:
        db = self.ctx.db
        self._sid = sid
        sess = db.get_session(sid)
        if sess is None:
            self._clear_details()
            return
        start = sess["start_ts"]
        end = start + sess["duration_min"] * 60
        rows, intervals = db.attendance(sid), db.intervals(sid)
        kind = "Exam" if sess["kind"] == "exam" else "Class"
        self.summary.setText(f"{sess['title']}: {kind}, {fmt_datetime(start)}, {sess['duration_min']} min, "
                             f"minimum {sess['min_presence_min']} min in the room")
        c = Counter(r["status"] for r in rows)
        self.counts.setText(f"Present {c['PRESENT']}     Needs review {c['REVIEW']}     Absent {c['ABSENT']}"
                            + {"running": "     (session still running)",
                               "interrupted": "     (session was interrupted; showing the last autosave)"}.get(
                                   sess["status"], ""))

        t = self.att
        t.setRowCount(len(rows))
        for i, r in enumerate(rows):
            ivs = intervals.get(r["student_id"], [])
            gaps = breaks_between(ivs, start, end)
            breaks = f"{len(gaps)} for {fmt_dur(sum(b - a for a, b in gaps))}" if gaps else "none"
            set_cell(t, i, 0, r["reg_no"], data=r["student_id"])
            set_cell(t, i, 1, r["name"])
            set_status_cell(t, i, 2, r["status"])
            set_cell(t, i, 3, fmt_clock(r["check_in_ts"], False), center=True)
            set_cell(t, i, 4, fmt_clock(r["check_out_ts"], False), center=True)
            set_cell(t, i, 5, fmt_dur(r["present_sec"] or 0), center=True)
            set_cell(t, i, 6, "", data=PresenceData(start, end, ivs, r["check_in_ts"], r["check_out_ts"]))
            set_cell(t, i, 7, breaks, center=True)
            set_cell(t, i, 8, (r["reason"] or "") + ("  (set by hand)" if r["override"] else ""))
        self.timeline.clear()

        events = [e for e in db.events(sid) if e["severity"] > 0]
        a = self.alerts
        a.setRowCount(len(events))
        sev_map = {1: "Low", 2: "Medium", 3: "High", 4: "Critical"}
        for i, e in enumerate(events):
            info = EVENT_INFO.get(e["type"], (1, e["type"]))
            conf = e["confidence"] if "confidence" in e.keys() and e["confidence"] is not None else 0.90
            rev = e["review_status"] if "review_status" in e.keys() and e["review_status"] else "Pending Review"
            rem = e["admin_remarks"] if "admin_remarks" in e.keys() and e["admin_remarks"] else ""
            set_cell(a, i, 0, fmt_clock(e["ts"]), data=dict(e))
            set_cell(a, i, 1, e["name"] or ("Instructor / System" if e["type"] in ("INSTRUCTION", "SESSION_START", "SESSION_END") else "Unknown face"))
            set_cell(a, i, 2, info[1], bold=True, fg=SEVERITY_COLOUR.get(e["severity"], theme.MUTED))
            set_cell(a, i, 3, sev_map.get(e["severity"], "Low"), center=True)
            set_cell(a, i, 4, f"{conf:.0%}", center=True)
            set_status_cell(a, i, 5, rev)
            set_cell(a, i, 6, rem)
            set_cell(a, i, 7, e["detail"] or "")
        fill_risk_table(self.ranking, db.risk(sid))
        self.evidence.setText("Select an alert to see its snapshot.")
        self.tabs.setTabVisible(1, sess["kind"] == "exam" or bool(events))
        self.tabs.setTabVisible(2, sess["kind"] == "exam")
        self._enable_actions(True)
        self.exp_ev.setVisible(sess["kind"] == "exam" or bool(events))
        self.exp_risk.setVisible(sess["kind"] == "exam")
        self.exp_html.setVisible(sess["kind"] == "exam")

    def _on_student_selected(self) -> None:
        rows = self.att.selectionModel().selectedRows()
        if not rows:
            return
        d = self.att.item(rows[0].row(), 6).data(Qt.ItemDataRole.UserRole)
        self.timeline.set_data(d.start, d.end, d.intervals, d.check_in, d.check_out)

    def _show_evidence(self) -> None:
        rows = self.alerts.selectionModel().selectedRows()
        if not rows:
            return
        data = self.alerts.item(rows[0].row(), 0).data(Qt.ItemDataRole.UserRole)
        rel = data.get("snapshot", "") if isinstance(data, dict) else (data or "")
        pix = QPixmap(str(DATA_DIR / rel)) if rel else QPixmap()
        if pix.isNull():
            self.evidence.setText("No snapshot was saved for this alert.")
            return
        self.evidence.setPixmap(pix.scaled(self.evidence.width(), self.evidence.height(),
                                           Qt.AspectRatioMode.KeepAspectRatio,
                                           Qt.TransformationMode.SmoothTransformation))

    def _review_alert(self) -> None:
        rows = self.alerts.selectionModel().selectedRows()
        if not rows:
            QMessageBox.information(self, "Select Alert", "Select an alert from the table to review.")
            return
        data = self.alerts.item(rows[0].row(), 0).data(Qt.ItemDataRole.UserRole)
        if not isinstance(data, dict):
            return
        dlg = AlertReviewDialog(self.ctx, data, self)
        if dlg.exec():
            if self._sid:
                self._load(self._sid)

    def _export_html_report(self) -> None:
        if self._sid is None:
            return
        EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        html_content = generate_proctoring_html_report(self.ctx.db, self._sid)
        path, _ = QFileDialog.getSaveFileName(self, "Export Proctoring Report",
                                              str(EXPORT_DIR / f"proctoring_report_session_{self._sid}.html"),
                                              "HTML files (*.html)")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(html_content)
        except OSError as exc:
            QMessageBox.warning(self, "Could not export", f"{exc}")
            return
        ans = QMessageBox.question(self, "Report Exported",
                                   f"Report successfully generated and saved to:\n{path}\n\nDo you want to view it in your browser now?",
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if ans == QMessageBox.StandardButton.Yes:
            import webbrowser
            webbrowser.open(f"file:///{os.path.abspath(path)}")

    # ------------------------------------------------------------------- actions
    def _override(self) -> None:
        rows = self.att.selectionModel().selectedRows()
        if not rows or self._sid is None:
            QMessageBox.information(self, "Select a student", "Select a student in the Attendance tab first.")
            return
        row = rows[0].row()
        student_id = self.att.item(row, 0).data(Qt.ItemDataRole.UserRole)
        name = self.att.item(row, 1).text()
        choice, ok = QInputDialog.getItem(self, "Set status by hand", f"Status for {name}:",
                                          ["Present", "Absent", "Needs review"], 0, False)
        if not ok:
            return
        note, ok = QInputDialog.getText(self, "Reason", "Why are you changing this? (kept in the record)")
        if not ok:
            return
        status = {"Present": "PRESENT", "Absent": "ABSENT", "Needs review": "REVIEW"}[choice]
        self.ctx.db.set_override(self._sid, student_id, status, f"Set by hand: {note.strip() or 'no reason given'}")
        self._load(self._sid)
        self.att.selectRow(row)
        self.ctx.sessions_changed.emit()

    def _export(self, what: str, func) -> None:
        if self._sid is None:
            return
        EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        path, _ = QFileDialog.getSaveFileName(self, f"Export {what}", str(EXPORT_DIR / f"{what}_session{self._sid}.csv"),
                                              "CSV files (*.csv)")
        if not path:
            return
        try:
            func(self.ctx.db, self._sid, path)
        except OSError as exc:
            QMessageBox.warning(self, "Could not export", f"{exc}\n\nIf the file is open in Excel, close it and try again.")
            return
        QMessageBox.information(self, "Exported", f"Saved to:\n{path}")

    def _delete(self) -> None:
        if self._sid is None:
            return
        ans = QMessageBox.question(self, "Delete this session?",
                                   "This removes its attendance, alerts and evidence snapshots. It cannot be undone.")
        if ans != QMessageBox.StandardButton.Yes:
            return
        self.ctx.db.delete_session(self._sid)
        shutil.rmtree(EVIDENCE_DIR / str(self._sid), ignore_errors=True)
        self._sid = None
        self._clear_details()
        self.ctx.sessions_changed.emit()
