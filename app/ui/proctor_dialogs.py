"""Dialogs and widgets for the AI-Powered Smart Exam Proctoring System.

Includes:
- StudentCardWidget: Live monitoring card with photo, score progress, status indicators, and colored border.
- StudentDetailDialog: In-depth student dossier with evidence gallery, incident history, and charts.
- AlertReviewDialog: Invigilator decision modal to confirm concerns, mark false positives, or resolve incidents.
- generate_proctoring_html_report: Generates a self-contained, printable enterprise HTML examination report.
"""
from __future__ import annotations

import base64
import html
import os
import time
from typing import Dict, List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QPixmap
from PySide6.QtWidgets import (QDialog, QFrame, QGridLayout, QHBoxLayout, QLabel,
                             QLineEdit, QMessageBox, QProgressBar, QPushButton,
                             QScrollArea, QTextEdit, QVBoxLayout, QWidget, QComboBox)

from ..config import DATA_DIR
from ..utils import fmt_clock, fmt_datetime, fmt_dur
from . import theme
from .widgets import button, label, make_table, set_cell, set_status_cell

AL = Qt.AlignmentFlag

LEVEL_COLORS = {
    "Normal": ("#16a34a", "#f0fdf4", "#bbf7d0"),
    "Low": ("#ca8a04", "#fefce8", "#fef08a"),
    "Medium": ("#ea580c", "#fff7ed", "#fed7aa"),
    "High": ("#dc2626", "#fef2f2", "#fecaca"),
    "Critical": ("#7f1d1d", "#fdf2f2", "#fca5a5"),
}


class StudentCardWidget(QFrame):
    """Card representing one student in the live exam monitoring grid."""
    clicked = Signal(int)

    def __init__(self, sid: Optional[int], name: str, reg_no: str, photo_path: Optional[str] = None, parent=None):
        super().__init__(parent)
        self.sid = sid
        self.name = name
        self.reg_no = reg_no
        self.photo_path = photo_path
        self._score = 0.0
        self._level = "Normal"
        self._incidents = 0
        self._last_activity = "Normal monitoring"
        self._build_ui()
        self.update_level("Normal", 0.0, 0, "Normal monitoring", "Face in frame")

    def _build_ui(self) -> None:
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setMinimumSize(220, 190)
        self.setMaximumWidth(320)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(6)

        # Header: photo + identity
        hdr = QHBoxLayout()
        hdr.setSpacing(10)

        self.avatar = QLabel()
        self.avatar.setFixedSize(48, 48)
        self.avatar.setAlignment(AL.AlignCenter)
        self._load_photo()
        hdr.addWidget(self.avatar)

        id_box = QVBoxLayout()
        id_box.setSpacing(2)
        self.name_lbl = QLabel(self.name)
        font = self.name_lbl.font()
        font.setBold(True)
        font.setPointSize(11)
        self.name_lbl.setFont(font)
        self.name_lbl.setStyleSheet(f"color: {theme.INK}; font-weight: bold;")
        self.name_lbl.setWordWrap(True)

        self.reg_lbl = QLabel(self.reg_no or f"Track #{self.sid}")
        self.reg_lbl.setStyleSheet(f"color: {theme.MUTED}; font-size: 11px;")

        id_box.addWidget(self.name_lbl)
        id_box.addWidget(self.reg_lbl)
        hdr.addLayout(id_box, 1)

        self.level_badge = QLabel("Normal")
        self.level_badge.setAlignment(AL.AlignCenter)
        self.level_badge.setFixedHeight(22)
        hdr.addWidget(self.level_badge)
        lay.addLayout(hdr)

        # Suspicion Score Bar
        score_row = QHBoxLayout()
        score_row.setSpacing(6)
        self.score_text = QLabel("Score: 0%")
        self.score_text.setStyleSheet("font-size: 11px; font-weight: bold;")
        score_row.addWidget(self.score_text)
        score_row.addStretch(1)

        self.inc_badge = QLabel("0 alerts")
        self.inc_badge.setStyleSheet("font-size: 11px; color: #4b5563; background: #e5e7eb; border-radius: 4px; padding: 2px 6px;")
        score_row.addWidget(self.inc_badge)
        lay.addLayout(score_row)

        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(8)
        lay.addWidget(self.bar)

        # Activity & Status
        self.status_lbl = QLabel("Face in frame")
        self.status_lbl.setStyleSheet("font-size: 11px; font-weight: 500; color: #374151;")
        lay.addWidget(self.status_lbl)

        self.act_lbl = QLabel("Last: Normal monitoring")
        self.act_lbl.setStyleSheet("font-size: 10px; color: #6b7280;")
        lay.addWidget(self.act_lbl)

        # Action button
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        self.view_btn = button("Details", "secondary")
        self.view_btn.setFixedHeight(26)
        self.view_btn.setStyleSheet("font-size: 11px; padding: 2px 10px;")
        self.view_btn.clicked.connect(self._on_details_clicked)
        btn_row.addWidget(self.view_btn)
        lay.addLayout(btn_row)

    def _load_photo(self) -> None:
        if self.photo_path:
            full = DATA_DIR / self.photo_path
            if full.exists():
                pix = QPixmap(str(full))
                if not pix.isNull():
                    scaled = pix.scaled(48, 48, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                        Qt.TransformationMode.SmoothTransformation)
                    self.avatar.setPixmap(scaled)
                    self.avatar.setStyleSheet("border-radius: 24px; border: 1px solid #d1d5db; overflow: hidden;")
                    return
        # Initials fallback
        initials = "".join(part[0].upper() for part in self.name.split()[:2]) or "?"
        self.avatar.setText(initials)
        self.avatar.setStyleSheet(f"background: {theme.INK}; color: #ffffff; font-weight: bold; font-size: 14px; border-radius: 24px;")

    def update_level(self, level: str, score: float, incidents: int, last_activity: str, face_status: str) -> None:
        self._level = level
        self._score = score
        self._incidents = incidents
        self._last_activity = last_activity

        fg, bg, border = LEVEL_COLORS.get(level, LEVEL_COLORS["Normal"])
        self.setStyleSheet(f"""
            StudentCardWidget {{
                background-color: {bg};
                border: 2px solid {border};
                border-radius: 8px;
            }}
            StudentCardWidget:hover {{
                border: 2px solid {fg};
            }}
        """)
        self.level_badge.setText(f" {level} ")
        self.level_badge.setStyleSheet(f"background: {border}; color: {fg}; font-weight: bold; font-size: 11px; border-radius: 4px; padding: 2px 6px;")

        self.score_text.setText(f"Suspicion: {score:.0f}%")
        self.score_text.setStyleSheet(f"font-size: 11px; font-weight: bold; color: {fg};")
        self.bar.setValue(int(score))
        self.bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: #e5e7eb;
                border-radius: 4px;
            }}
            QProgressBar::chunk {{
                background-color: {fg};
                border-radius: 4px;
            }}
        """)

        self.inc_badge.setText(f"{incidents} incident{'s' if incidents != 1 else ''}")
        self.status_lbl.setText(face_status)
        self.act_lbl.setText(f"Last: {last_activity}")

    def _on_details_clicked(self) -> None:
        if self.sid is not None:
            self.clicked.emit(self.sid)


class StudentDetailDialog(QDialog):
    """In-depth monitoring dossier for a student taking an examination."""

    def __init__(self, ctx, session_id: int, student_id: int, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.session_id = session_id
        self.student_id = student_id
        st = ctx.db.get_student(student_id)
        self.student = dict(st) if st is not None else {"name": f"Student #{student_id}", "reg_no": "", "role": "student"}
        self.setWindowTitle(f"Student Examination Dossier – {self.student['name']}")
        self.resize(780, 580)
        self._build_ui()
        self._load_data()

    def _build_ui(self) -> None:
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(14)

        # Header card
        hdr_panel = QFrame()
        hdr_panel.setStyleSheet(f"background: #ffffff; border: 1px solid {theme.RULE}; border-radius: 8px; padding: 12px;")
        hl = QHBoxLayout(hdr_panel)
        hl.setSpacing(16)

        self.photo_lbl = QLabel()
        self.photo_lbl.setFixedSize(72, 72)
        self.photo_lbl.setAlignment(AL.AlignCenter)
        hl.addWidget(self.photo_lbl)

        info_box = QVBoxLayout()
        info_box.setSpacing(3)
        name_txt = QLabel(self.student["name"])
        f = name_txt.font()
        f.setPointSize(14)
        f.setBold(True)
        name_txt.setFont(f)
        info_box.addWidget(name_txt)

        meta = f"Reg. No: <b>{self.student.get('reg_no', '-')}</b> | Section: {self.student.get('section', '-')} | Dept: {self.student.get('department', '-')}"
        info_box.addWidget(QLabel(meta))
        contact = f"Email: {self.student.get('email', '-')} | Phone: {self.student.get('phone', '-')}"
        info_box.addWidget(QLabel(contact))
        hl.addLayout(info_box, 1)

        # Suspicion status box
        self.score_box = QVBoxLayout()
        self.score_box.setAlignment(AL.AlignCenter)
        self.score_val = QLabel("0%")
        sf = self.score_val.font()
        sf.setPointSize(18)
        sf.setBold(True)
        self.score_val.setFont(sf)
        self.score_val.setAlignment(AL.AlignCenter)

        self.score_lbl = QLabel("Suspicion Score")
        self.score_lbl.setStyleSheet(f"color: {theme.MUTED}; font-size: 11px;")
        self.score_lbl.setAlignment(AL.AlignCenter)

        self.badge_lbl = QLabel("Normal")
        self.badge_lbl.setAlignment(AL.AlignCenter)
        self.badge_lbl.setStyleSheet("background: #dcfce7; color: #166534; font-weight: bold; border-radius: 4px; padding: 2px 8px;")

        self.score_box.addWidget(self.score_val)
        self.score_box.addWidget(self.score_lbl)
        self.score_box.addWidget(self.badge_lbl)
        hl.addLayout(self.score_box)
        lay.addWidget(hdr_panel)

        # Activity Breakdown Cards
        stats_row = QHBoxLayout()
        stats_row.setSpacing(10)
        self.stat_away = self._make_stat_box("Looking Away", "0s")
        self.stat_glances = self._make_stat_box("Glances", "0")
        self.stat_missing = self._make_stat_box("Missing", "0s")
        self.stat_objects = self._make_stat_box("Objects", "0")
        self.stat_flags = self._make_stat_box("Flags", "0")
        for b in (self.stat_away, self.stat_glances, self.stat_missing, self.stat_objects, self.stat_flags):
            stats_row.addWidget(b)
        lay.addLayout(stats_row)

        # Timeline / Incident History Table
        lay.addWidget(label("Suspicious Activity & Incident Timeline", "section"))
        self.table = make_table(["Time", "Activity", "Severity", "Confidence", "Status", "Remarks", "Snapshot"],
                                stretch=[1, 5], row_height=32)
        self.table.itemSelectionChanged.connect(self._on_incident_selected)
        lay.addWidget(self.table, 1)

        # Snapshot Preview & Review action row
        bottom_row = QHBoxLayout()
        self.snap_preview = QLabel("Select an incident to view evidence screenshot")
        self.snap_preview.setAlignment(AL.AlignCenter)
        self.snap_preview.setFixedHeight(120)
        self.snap_preview.setStyleSheet("background: #f9fafb; border: 1px dashed #d1d5db; border-radius: 6px; color: #6b7280;")
        bottom_row.addWidget(self.snap_preview, 1)

        act_box = QVBoxLayout()
        act_box.addStretch(1)
        self.review_btn = button("Update Review Status...", "primary")
        self.review_btn.clicked.connect(self._review_selected_incident)
        act_box.addWidget(self.review_btn)
        close_btn = button("Close")
        close_btn.clicked.connect(self.accept)
        act_box.addWidget(close_btn)
        bottom_row.addLayout(act_box)
        lay.addLayout(bottom_row)

    def _make_stat_box(self, title: str, val: str) -> QFrame:
        f = QFrame()
        f.setStyleSheet("background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 6px;")
        l = QVBoxLayout(f)
        l.setContentsMargins(6, 6, 6, 6)
        l.setSpacing(2)
        v = QLabel(val)
        v.setStyleSheet("font-size: 15px; font-weight: bold; color: #1e293b;")
        v.setAlignment(AL.AlignCenter)
        t = QLabel(title)
        t.setStyleSheet("font-size: 11px; color: #64748b;")
        t.setAlignment(AL.AlignCenter)
        l.addWidget(v)
        l.addWidget(t)
        f._val_label = v
        return f

    def _load_data(self) -> None:
        db = self.ctx.db
        samples = db.samples(self.student_id)
        if samples:
            p = DATA_DIR / samples[0]["image_path"]
            if p.exists():
                pix = QPixmap(str(p))
                if not pix.isNull():
                    self.photo_lbl.setPixmap(pix.scaled(72, 72, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                                        Qt.TransformationMode.SmoothTransformation))
                    self.photo_lbl.setStyleSheet("border-radius: 36px; border: 1px solid #d1d5db;")
        if not self.photo_lbl.pixmap():
            init = "".join(part[0].upper() for part in self.student["name"].split()[:2]) or "?"
            self.photo_lbl.setText(init)
            self.photo_lbl.setStyleSheet(f"background: {theme.INK}; color: #ffffff; font-weight: bold; font-size: 20px; border-radius: 36px;")

        # Risk record
        risks = [r for r in db.risk(self.session_id) if r.get("sid") == self.student_id]
        if risks:
            r = risks[0]
            score = r.get("score", 0.0)
            disp = r.get("suspicion_level", "Normal")
            fg, bg, _ = LEVEL_COLORS.get(disp, LEVEL_COLORS["Normal"])
            self.score_val.setText(f"{score:.0f}%")
            self.score_val.setStyleSheet(f"color: {fg}; font-size: 20px; font-weight: bold;")
            self.badge_lbl.setText(disp)
            self.badge_lbl.setStyleSheet(f"background: {bg}; color: {fg}; font-weight: bold; border-radius: 4px; padding: 2px 8px;")

            self.stat_away._val_label.setText(f"{r.get('away_pct', 0):.0f}%")
            self.stat_glances._val_label.setText(str(r.get("glances", 0)))
            self.stat_missing._val_label.setText(fmt_dur(r.get("missing_sec", 0)))
            self.stat_objects._val_label.setText(str(r.get("objects", 0)))
            self.stat_flags._val_label.setText(str(r.get("flags", 0)))

        # Events
        all_events = db.events(self.session_id)
        events = [e for e in all_events if e["student_id"] == self.student_id]
        self.table.setRowCount(len(events))
        sev_map = {1: "Low", 2: "Medium", 3: "High", 4: "Critical"}
        for i, e in enumerate(events):
            conf = e["confidence"] if "confidence" in e.keys() and e["confidence"] is not None else 0.90
            rev = e["review_status"] if "review_status" in e.keys() and e["review_status"] else "Pending Review"
            rem = e["admin_remarks"] if "admin_remarks" in e.keys() and e["admin_remarks"] else ""
            set_cell(self.table, i, 0, fmt_clock(e["ts"]), data=e)
            set_cell(self.table, i, 1, e["type"].replace("_", " ").title(), bold=True)
            set_cell(self.table, i, 2, sev_map.get(e["severity"], "Low"), center=True)
            set_cell(self.table, i, 3, f"{conf:.0%}", center=True)
            set_status_cell(self.table, i, 4, rev)
            set_cell(self.table, i, 5, rem)
            set_cell(self.table, i, 6, "Screenshot" if e["snapshot"] else "None", center=True)

    def _on_incident_selected(self) -> None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return
        e = self.table.item(rows[0].row(), 0).data(Qt.ItemDataRole.UserRole)
        snap = e["snapshot"]
        if snap:
            p = DATA_DIR / snap
            if p.exists():
                pix = QPixmap(str(p))
                if not pix.isNull():
                    self.snap_preview.setPixmap(pix.scaled(self.snap_preview.width(), self.snap_preview.height(),
                                                          Qt.AspectRatioMode.KeepAspectRatio,
                                                          Qt.TransformationMode.SmoothTransformation))
                    return
        self.snap_preview.setText("No screenshot image available for this event")

    def _review_selected_incident(self) -> None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            QMessageBox.information(self, "Select Incident", "Select an incident from the timeline table to review.")
            return
        e = self.table.item(rows[0].row(), 0).data(Qt.ItemDataRole.UserRole)
        dlg = AlertReviewDialog(self.ctx, dict(e), self)
        if dlg.exec():
            self._load_data()


class AlertReviewDialog(QDialog):
    """Admin review modal for suspected proctoring incidents."""

    def __init__(self, ctx, event_info: dict, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.event_info = event_info
        self.setWindowTitle(f"Review Incident #{event_info.get('id', '')}")
        self.resize(520, 420)
        self._build_ui()

    def _build_ui(self) -> None:
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(12)

        # Overview
        lay.addWidget(label(f"Incident: {self.event_info.get('type', '').replace('_', ' ').title()}", "section"))
        sub = f"Student: <b>{self.event_info.get('name', 'Unknown')}</b> | Time: {fmt_clock(self.event_info.get('ts', time.time()))}"
        lay.addWidget(QLabel(sub))

        # Details
        det_frame = QFrame()
        det_frame.setStyleSheet("background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 10px;")
        dl = QVBoxLayout(det_frame)
        dl.setSpacing(4)
        dl.addWidget(QLabel(f"Description: {self.event_info.get('detail', '-') or '-'}"))
        conf = self.event_info.get("confidence", 0.90)
        dl.addWidget(QLabel(f"Detection Confidence: <b>{conf:.0%}</b>"))
        lay.addWidget(det_frame)

        # Evidence snapshot preview
        snap = self.event_info.get("snapshot", "")
        if snap:
            p = DATA_DIR / snap
            if p.exists():
                pix = QPixmap(str(p))
                if not pix.isNull():
                    img_lbl = QLabel()
                    img_lbl.setFixedHeight(110)
                    img_lbl.setAlignment(AL.AlignCenter)
                    img_lbl.setPixmap(pix.scaled(480, 110, Qt.AspectRatioMode.KeepAspectRatio,
                                                 Qt.TransformationMode.SmoothTransformation))
                    lay.addWidget(img_lbl)

        # Review decision
        lay.addWidget(label("Review Decision Status:", "muted"))
        self.status_combo = QComboBox()
        self.status_combo.addItems([
            "Pending Review",
            "Confirmed Concern",
            "False Positive",
            "Resolved",
            "Escalated",
        ])
        current = self.event_info.get("review_status", "Pending Review")
        idx = self.status_combo.findText(current)
        if idx >= 0:
            self.status_combo.setCurrentIndex(idx)
        lay.addWidget(self.status_combo)

        # Remarks
        lay.addWidget(label("Administrator Remarks & Action Taken:", "muted"))
        self.remarks_edit = QTextEdit()
        self.remarks_edit.setPlaceholderText("Enter administrative notes, justification or verification details...")
        self.remarks_edit.setPlainText(self.event_info.get("admin_remarks", "") or "")
        self.remarks_edit.setMaximumHeight(80)
        lay.addWidget(self.remarks_edit)

        # Buttons
        btns = QHBoxLayout()
        btns.addStretch(1)
        cancel_btn = button("Cancel")
        cancel_btn.clicked.connect(self.reject)
        save_btn = button("Save Decision", "primary")
        save_btn.clicked.connect(self._save)
        btns.addWidget(cancel_btn)
        btns.addWidget(save_btn)
        lay.addLayout(btns)

    def _save(self) -> None:
        eid = self.event_info.get("id")
        if not eid:
            self.reject()
            return
        status = self.status_combo.currentText()
        remarks = self.remarks_edit.toPlainText().strip()
        self.ctx.db.update_event_review(eid, status, remarks)
        self.accept()


def generate_proctoring_html_report(db, session_id: int) -> str:
    """Generate an enterprise-grade printable HTML examination report."""
    sess = db.get_session(session_id)
    if sess is None:
        return "<html><body><h1>Session not found</h1></body></html>"

    students = db.attendance(session_id)
    events = db.events(session_id)
    risks = {r.get("sid"): r for r in db.risk(session_id)}

    start_str = fmt_datetime(sess["start_ts"])
    dur_min = sess["duration_min"]

    # Statistics
    total_stud = len(students)
    total_alerts = len([e for e in events if e["severity"] > 0])
    high_count = sum(1 for r in risks.values() if r.get("score", 0.0) >= 60.0)

    # Build student HTML cards
    student_blocks = []
    for s in students:
        sid = s["student_id"]
        r = risks.get(sid, {})
        score = r.get("score", 0.0)
        level = r.get("suspicion_level", "Normal")
        color = r.get("color", "#16a34a")

        # Student's events
        s_events = [e for e in events if e["student_id"] == sid]

        # Photo
        samples = db.samples(sid)
        photo_html = ""
        if samples:
            full = DATA_DIR / samples[0]["image_path"]
            if full.exists():
                try:
                    with open(full, "rb") as f:
                        b64 = base64.b64encode(f.read()).decode("utf-8")
                        photo_html = f'<img src="data:image/jpeg;base64,{b64}" style="width:64px;height:64px;border-radius:50%;object-fit:cover;border:2px solid {color};"/>'
                except Exception:
                    pass
        if not photo_html:
            init = "".join(p[0].upper() for p in s["name"].split()[:2]) or "?"
            photo_html = f'<div style="width:64px;height:64px;border-radius:50%;background:#14304A;color:#fff;display:flex;align-items:center;justify-content:center;font-weight:bold;font-size:20px;">{init}</div>'

        # Event rows
        ev_rows = []
        for e in s_events:
            conf = e["confidence"] if "confidence" in e.keys() and e["confidence"] is not None else 0.90
            rev = e["review_status"] if "review_status" in e.keys() and e["review_status"] else "Pending Review"
            rem = e["admin_remarks"] if "admin_remarks" in e.keys() and e["admin_remarks"] else "-"
            snap_tag = ""
            if e["snapshot"]:
                snap_path = DATA_DIR / e["snapshot"]
                if snap_path.exists():
                    try:
                        with open(snap_path, "rb") as f:
                            b64 = base64.b64encode(f.read()).decode("utf-8")
                            snap_tag = f'<img src="data:image/jpeg;base64,{b64}" style="height:48px;border-radius:4px;"/>'
                    except Exception:
                        snap_tag = "Available"
            ev_rows.append(f"""
                <tr>
                    <td>{fmt_clock(e['ts'])}</td>
                    <td><b>{html.escape(e['type'].replace('_', ' ').title())}</b></td>
                    <td>{e['severity']}</td>
                    <td>{conf:.0%}</td>
                    <td><span class="badge badge-{html.escape(rev.lower().replace(' ', '-'))}">{html.escape(rev)}</span></td>
                    <td>{html.escape(e['detail'] or '')}</td>
                    <td>{html.escape(rem)}</td>
                    <td>{snap_tag}</td>
                </tr>
            """)

        ev_table = f"""
            <table class="event-table">
                <thead>
                    <tr>
                        <th>Time</th>
                        <th>Incident</th>
                        <th>Severity</th>
                        <th>Confidence</th>
                        <th>Review Status</th>
                        <th>Detail</th>
                        <th>Remarks</th>
                        <th>Evidence</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(ev_rows) if ev_rows else '<tr><td colspan="8" style="text-align:center;color:#6b7280;">No suspicious activities flagged for this student.</td></tr>'}
                </tbody>
            </table>
        """

        student_blocks.append(f"""
            <div class="student-card" style="border-left: 6px solid {color};">
                <div class="student-header">
                    <div style="display:flex;align-items:center;gap:14px;">
                        {photo_html}
                        <div>
                            <div class="student-name">{html.escape(s['name'])}</div>
                            <div class="student-meta">Reg. No: <b>{html.escape(s['reg_no'] or '-')}</b> &nbsp;|&nbsp; Present: {fmt_dur(s['present_sec'] or 0)} &nbsp;|&nbsp; Status: <b>{html.escape(s['status'])}</b></div>
                        </div>
                    </div>
                    <div style="text-align:right;">
                        <span class="score-badge" style="background:{color};">{score:.0f}% Suspicion – {level}</span>
                        <div style="font-size:12px;color:#6b7280;margin-top:4px;">{len(s_events)} Incident(s) Logged</div>
                    </div>
                </div>
                {ev_table}
            </div>
        """)

    report_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8"/>
    <title>AI Proctoring Report – {html.escape(sess['title'])}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background: #f8fafc;
            color: #1e293b;
            margin: 0;
            padding: 30px;
        }}
        .header {{
            background: #14304A;
            color: #ffffff;
            padding: 24px 30px;
            border-radius: 8px;
            margin-bottom: 24px;
        }}
        .header h1 {{ margin: 0 0 6px 0; font-size: 24px; }}
        .header p {{ margin: 0; color: #94a3b8; font-size: 14px; }}
        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 16px;
            margin-bottom: 28px;
        }}
        .summary-box {{
            background: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            padding: 16px;
            text-align: center;
        }}
        .summary-box .num {{
            font-size: 26px;
            font-weight: bold;
            color: #0f172a;
        }}
        .summary-box .label {{
            font-size: 12px;
            color: #64748b;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-top: 4px;
        }}
        .student-card {{
            background: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        }}
        .student-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid #f1f5f9;
            padding-bottom: 14px;
            margin-bottom: 14px;
        }}
        .student-name {{
            font-size: 17px;
            font-weight: bold;
            color: #0f172a;
        }}
        .student-meta {{
            font-size: 13px;
            color: #64748b;
            margin-top: 2px;
        }}
        .score-badge {{
            color: #ffffff;
            font-weight: bold;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 13px;
        }}
        .event-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 12px;
            margin-top: 10px;
        }}
        .event-table th {{
            background: #f8fafc;
            color: #475569;
            text-align: left;
            padding: 8px 10px;
            border-bottom: 2px solid #e2e8f0;
        }}
        .event-table td {{
            padding: 8px 10px;
            border-bottom: 1px solid #f1f5f9;
            vertical-align: middle;
        }}
        .badge {{
            padding: 2px 8px;
            border-radius: 4px;
            font-weight: bold;
            font-size: 11px;
        }}
        .badge-pending-review {{ background: #fef3c7; color: #92400e; }}
        .badge-confirmed-concern {{ background: #fee2e2; color: #991b1b; }}
        .badge-false-positive {{ background: #f3f4f6; color: #4b5563; }}
        .badge-resolved {{ background: #dcfce7; color: #166534; }}
        .badge-escalated {{ background: #fce7f3; color: #9d174d; }}
        .footer {{
            margin-top: 40px;
            text-align: center;
            color: #94a3b8;
            font-size: 12px;
            border-top: 1px solid #e2e8f0;
            padding-top: 20px;
        }}
        @media print {{
            body {{ background: #fff; padding: 0; }}
            .student-card {{ page-break-inside: avoid; }}
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>ClassVision AI – Examination Proctoring Report</h1>
        <p>Examination: <b>{html.escape(sess['title'])}</b> | Date: {start_str} | Duration: {dur_min} minutes | Proctored via Computer Vision AI</p>
    </div>

    <div class="summary-grid">
        <div class="summary-box">
            <div class="num">{total_stud}</div>
            <div class="label">Total Students</div>
        </div>
        <div class="summary-box">
            <div class="num">{total_alerts}</div>
            <div class="label">Total Alerts Flagged</div>
        </div>
        <div class="summary-box">
            <div class="num" style="color: {'#dc2626' if high_count > 0 else '#16a34a'};">{high_count}</div>
            <div class="label">High Concern Students</div>
        </div>
        <div class="summary-box">
            <div class="num">{len(risks)}</div>
            <div class="label">Evaluated Risk Profiles</div>
        </div>
    </div>

    <h2>Student Dossiers & Incident Logs</h2>
    {''.join(student_blocks)}

    <div class="footer">
        Generated by ClassVision AI Proctoring System &bull; SQLite Verified &bull; For Human Review Only
    </div>
</body>
</html>"""
    return report_html
