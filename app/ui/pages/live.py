"""Live session page. One class serves both "Class attendance" and "Exam proctoring"."""
from __future__ import annotations

import time
from datetime import datetime

from PySide6.QtCore import QTime, Qt, Slot
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
                               QMessageBox, QScrollArea, QSpinBox, QSplitter, QTabWidget, QTimeEdit, QVBoxLayout, QWidget)

from ...config import DATA_DIR
from ...utils import fmt_clock, fmt_dur
from ...workers.session import SessionConfig, SessionController
from .. import theme
from ..proctor_dialogs import AlertReviewDialog, StudentCardWidget, StudentDetailDialog
from ..widgets import (RISK_HEADERS, Banner, PresenceData, PresenceDelegate, VideoView, button, fill_risk_table,
                       label, make_table, offer_model_download, panel, set_cell, set_status_cell)

AL = Qt.AlignmentFlag
SEVERITY_COLOUR = {3: theme.RED, 2: theme.AMBER, 1: theme.MUTED}

TEXT = {
    "class": ("Class attendance",
              "Students check in at the gate, the room camera tracks who stays, and they check out at the end."),
    "exam": ("Exam proctoring",
             "Attendance plus alerts for looking away, missing faces, unknown people and phones. "
             "Alerts are for a person to review; they are not proof of cheating."),
}


def _field(caption: str, widget: QWidget, hint: str = "") -> QWidget:
    box = QWidget()
    lay = QVBoxLayout(box)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(3)
    lay.addWidget(label(caption, "muted"))
    lay.addWidget(widget)
    if hint:
        widget.setToolTip(hint)
    return box


class LivePage(QWidget):
    def __init__(self, ctx, kind: str, parent=None):
        super().__init__(parent)
        self.ctx, self.kind = ctx, kind
        self.ctrl = SessionController(ctx, kind, self)
        self._hold_until = 0.0
        self._build()
        c = self.ctrl
        c.frame.connect(self._on_frame)
        c.overlays.connect(self._on_overlays)
        c.attendance.connect(self._on_attendance)
        c.gate_msg.connect(self._on_gate_msg)
        c.alert.connect(self._on_alert)
        c.risk.connect(self._on_risk)
        c.tick.connect(self._on_tick)
        c.status.connect(self._on_status)
        c.finished.connect(self._on_finished)
        ctx.students_changed.connect(self._refresh_sections)
        ctx.settings_changed.connect(self._apply_defaults)
        ctx.timetable_changed.connect(self._refresh_timetable_combo)
        self._apply_defaults()
        self._refresh_timetable_combo()

    # ------------------------------------------------------------------ layout
    def _build(self) -> None:
        title, blurb = TEXT[self.kind]
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 20)
        root.setSpacing(12)
        root.addWidget(label(title, "title"))
        root.addWidget(label(blurb, "muted", wrap=True))

        setup = panel()
        sl = QVBoxLayout(setup)
        sl.setContentsMargins(16, 12, 16, 14)
        sl.setSpacing(10)

        # Timetable quick selection row
        t_row = QHBoxLayout()
        self.timetable_combo = QComboBox()
        self.timetable_combo.setToolTip("Select a class from today's timetable to auto-fill its title, section, timing and camera")
        self.timetable_combo.currentIndexChanged.connect(self._on_timetable_selected)
        t_row.addWidget(label("Today's Timetable:", "section"))
        t_row.addWidget(self.timetable_combo, 1)
        sl.addLayout(t_row)

        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(8)
        self.title = QLineEdit()
        self.section = QComboBox()
        self.start_time = QTimeEdit(QTime.currentTime())
        self.start_time.setDisplayFormat("HH:mm")
        self.now_box = QCheckBox("Start now")
        self.now_box.setChecked(True)
        self.start_time.setEnabled(False)
        self.now_box.toggled.connect(lambda on: self.start_time.setEnabled(not on))
        when = QWidget()
        wl = QHBoxLayout(when)
        wl.setContentsMargins(0, 0, 0, 0)
        wl.addWidget(self.start_time)
        wl.addWidget(self.now_box)
        self.length = QSpinBox()
        self.length.setRange(1, 600)
        self.min_presence = QSpinBox()
        self.min_presence.setRange(1, 600)
        self.class_src = QLineEdit()
        self.gate_src = QLineEdit()
        self.objects = QCheckBox("Detect phones, books and laptops")
        grid.addWidget(_field("Title", self.title), 0, 0)
        grid.addWidget(_field("Students", self.section, "Limit the roster to one section"), 0, 1)
        grid.addWidget(_field("Starts at", when, "Class time. Tick 'Start now' to use the current time."), 0, 2)
        grid.addWidget(_field("Length (minutes)", self.length), 0, 3)
        grid.addWidget(_field("Minimum time in room (minutes)", self.min_presence,
                              "A student must be seen in the room this long to count as present."), 0, 4)
        grid.addWidget(_field("Classroom camera", self.class_src,
                              "Webcam number such as 0, an rtsp:// address, or a video file path."), 1, 0, 1, 2)
        grid.addWidget(_field("Gate camera", self.gate_src,
                              "'same' uses the classroom camera, 'none' turns the gate off, "
                              "or enter a second camera."), 1, 2)
        if self.kind == "exam":
            grid.addWidget(_field("Optional", self.objects, "Needs: pip install ultralytics"), 1, 3, 1, 2)
        self.start_btn = button("Start", "primary")
        self.stop_btn = button("Stop and save", "danger")
        self.stop_btn.setEnabled(False)
        self.start_btn.clicked.connect(self._start)
        self.stop_btn.clicked.connect(self._stop)
        btns = QHBoxLayout()
        btns.addStretch(1)
        btns.addWidget(self.start_btn)
        btns.addWidget(self.stop_btn)
        grid.addLayout(btns, 2, 0, 1, 5)
        sl.addLayout(grid)
        root.addWidget(setup)

        strip = QHBoxLayout()
        self.phase = label("No session running.", "section")
        self.gate_state = label("", "muted")
        self.counts = label("", "muted")
        strip.addWidget(self.phase)
        strip.addSpacing(18)
        strip.addWidget(self.gate_state)
        strip.addStretch(1)
        strip.addWidget(self.counts)
        root.addLayout(strip)

        if self.kind == "exam":
            self.exec_bar = panel()
            eb_lay = QHBoxLayout(self.exec_bar)
            eb_lay.setContentsMargins(14, 8, 14, 8)
            eb_lay.setSpacing(12)

            def _metric(title: str, val: str, color: str = theme.INK) -> tuple[QLabel, QWidget]:
                w = QWidget()
                vl = QVBoxLayout(w)
                vl.setContentsMargins(0, 0, 0, 0)
                vl.setSpacing(1)
                num = QLabel(val)
                num.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {color};")
                num.setAlignment(AL.AlignCenter)
                lbl = QLabel(title)
                lbl.setStyleSheet(f"font-size: 11px; color: {theme.MUTED};")
                lbl.setAlignment(AL.AlignCenter)
                vl.addWidget(num)
                vl.addWidget(lbl)
                return num, w

            self.m_total, w_total = _metric("Enrolled", "0")
            self.m_active, w_active = _metric("Active", "0", theme.BLUE)
            self.m_normal, w_normal = _metric("Normal", "0", "#16a34a")
            self.m_low, w_low = _metric("Low", "0", "#ca8a04")
            self.m_med, w_med = _metric("Medium", "0", "#ea580c")
            self.m_high, w_high = _metric("High/Crit", "0", "#dc2626")
            self.m_incidents, w_inc = _metric("Alerts", "0")

            eb_lay.addWidget(w_total)
            eb_lay.addWidget(w_active)
            eb_lay.addWidget(w_normal)
            eb_lay.addWidget(w_low)
            eb_lay.addWidget(w_med)
            eb_lay.addWidget(w_high)
            eb_lay.addWidget(w_inc)
            root.addWidget(self.exec_bar)

        split = QSplitter(Qt.Orientation.Horizontal)
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 8, 0)
        self.class_view = VideoView("Classroom camera appears here once the session starts")
        self.gate_view = VideoView("Gate camera")
        self.gate_view.setMinimumHeight(160)
        self.gate_view.hide()
        self.gate_banner = Banner("Gate: waiting for a session", "info")
        self.cam_status = label("", "hint")
        ll.addWidget(self.class_view, 3)
        ll.addWidget(self.gate_view, 2)
        ll.addWidget(self.gate_banner)
        ll.addWidget(self.cam_status)
        split.addWidget(left)

        tabs = QTabWidget()
        self.table = make_table(["Reg. no", "Name", "Now", "Check-in", "Check-out", "In class", "Presence",
                                 "Outlook", "Result"], stretch=[1, 6], row_height=36)
        self.table.setItemDelegateForColumn(6, PresenceDelegate(self.table))
        self.table.setMinimumWidth(520)
        tabs.addTab(self.table, "Roster")

        # Activity & Instruction Logs Tab
        logs_widget = QWidget()
        log_layout = QVBoxLayout(logs_widget)
        log_layout.setContentsMargins(6, 6, 6, 6)
        log_layout.setSpacing(8)
        self.logs_table = make_table(["Time", "Type", "Instruction / Activity Event", "Student / Origin"], stretch=[2], row_height=32)
        log_layout.addWidget(self.logs_table, 1)

        instr_panel = panel()
        ip_lay = QVBoxLayout(instr_panel)
        ip_lay.setContentsMargins(10, 8, 10, 8)
        ip_lay.setSpacing(6)
        row_top = QHBoxLayout()
        row_top.addWidget(label("Log Instruction or Event:", "section"))
        self.quick_instr_combo = QComboBox()
        self.quick_instr_combo.addItems([
            "-- Select Quick Instruction --",
            "Class commenced according to timetable",
            "Instruction: Settle down and maintain silence",
            "Instruction: Open textbooks / course slides",
            "Instruction: Start practical / lab assignment",
            "Instruction: Group discussion / Q&A session",
            "Mid-class interval / break",
            "Instruction: Turn in assignments",
            "Class concluded / dismissed"
        ])
        self.quick_instr_combo.currentIndexChanged.connect(self._on_quick_instr_selected)
        row_top.addWidget(self.quick_instr_combo, 1)
        ip_lay.addLayout(row_top)

        row_bottom = QHBoxLayout()
        self.instr_input = QLineEdit()
        self.instr_input.setPlaceholderText("Type teacher instruction or classroom event note...")
        self.instr_input.returnPressed.connect(self._log_instruction_action)
        self.log_instr_btn = button("Log Instruction", "primary")
        self.log_instr_btn.clicked.connect(self._log_instruction_action)
        self.log_instr_btn.setEnabled(False)
        row_bottom.addWidget(self.instr_input, 1)
        row_bottom.addWidget(self.log_instr_btn)
        ip_lay.addLayout(row_bottom)

        log_layout.addWidget(instr_panel)
        tabs.addTab(logs_widget, "Activity & Instruction Logs")

        if self.kind == "exam":
            # 1. Student Cards Grid Tab
            self.cards_scroll = QScrollArea()
            self.cards_scroll.setWidgetResizable(True)
            self.cards_scroll.setFrameShape(QFrame.Shape.NoFrame)
            self.cards_container = QWidget()
            self.cards_layout = QGridLayout(self.cards_container)
            self.cards_layout.setSpacing(10)
            self.cards_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
            self.cards_scroll.setWidget(self.cards_container)
            self._cards: Dict[int, StudentCardWidget] = {}
            tabs.insertTab(0, self.cards_scroll, "Student Cards Grid")

            self.alerts = make_table(["Time", "Student", "Alert", "Detail"], stretch=[3])
            self.alerts.itemSelectionChanged.connect(self._show_evidence)
            self.evidence = QLabel("Select an alert to see its snapshot.")
            self.evidence.setAlignment(AL.AlignCenter)
            self.evidence.setMinimumHeight(150)
            self.evidence.setProperty("role", "muted")
            holder = QWidget()
            hl = QVBoxLayout(holder)
            hl.setContentsMargins(0, 0, 0, 0)
            hl.addWidget(self.alerts, 3)
            hl.addWidget(self.evidence, 2)

            rev_bar = QHBoxLayout()
            rev_bar.addStretch(1)
            self.review_alert_btn = button("Review Incident Status...", "primary")
            self.review_alert_btn.clicked.connect(self._open_alert_review)
            rev_bar.addWidget(self.review_alert_btn)
            hl.addLayout(rev_bar)

            tabs.addTab(holder, "Alerts")
            self.ranking = make_table(RISK_HEADERS, stretch=[0])
            tabs.addTab(self.ranking, "Suspicion ranking")
        split.addWidget(tabs)
        split.setStretchFactor(0, 5)
        split.setStretchFactor(1, 6)
        root.addWidget(split, 1)
        self._refresh_sections()

    # ---------------------------------------------------------------- defaults
    def _apply_defaults(self) -> None:
        if self.ctrl.running:
            return
        s = self.ctx.settings
        self.title.setText(f"{'Class' if self.kind == 'class' else 'Exam'} {datetime.now():%d %b %Y}")
        self.length.setValue(s.class_duration_min)
        self.min_presence.setValue(s.min_presence_min)
        self.class_src.setText(s.classroom_source)
        self.gate_src.setText(s.gate_source)
        self.objects.setChecked(s.object_detection)
        self._refresh_timetable_combo()

    def _refresh_timetable_combo(self) -> None:
        self.timetable_combo.blockSignals(True)
        self.timetable_combo.clear()
        self.timetable_combo.addItem("-- Select class from today's timetable --", None)
        today_rows = self.ctx.db.get_today_timetable()
        for r in today_rows:
            rd = dict(r)
            code_prefix = f"[{rd['subcode']}] " if rd.get("subcode") else ""
            label_text = f"{rd['start_time']} - {rd['end_time']} | {code_prefix}{rd['subject']}"
            if rd.get("section"):
                label_text += f" ({rd['section']})"
            if rd.get("room"):
                label_text += f" [{rd['room']}]"
            self.timetable_combo.addItem(label_text, rd)
        self.timetable_combo.blockSignals(False)

    def _on_timetable_selected(self, index: int) -> None:
        if index <= 0:
            return
        slot = self.timetable_combo.itemData(index)
        if slot:
            self.load_timetable_slot(slot)

    def load_timetable_slot(self, slot: dict, auto_start: bool = False) -> None:
        code = slot.get("subcode", "")
        subj = slot.get("subject", "")
        title_str = f"{code}: {subj}" if code else subj
        if slot.get("room"):
            title_str += f" - {slot['room']}"
        self.title.setText(title_str)
        sec = slot.get("section", "")
        if sec:
            idx = self.section.findText(sec)
            if idx >= 0:
                self.section.setCurrentIndex(idx)
            else:
                self.section.addItem(sec)
                self.section.setCurrentIndex(self.section.count() - 1)
        else:
            self.section.setCurrentIndex(0)
        st_str = slot.get("start_time")
        if st_str:
            t = QTime.fromString(st_str, "HH:mm")
            if t.isValid():
                self.start_time.setTime(t)
                self.now_box.setChecked(True)
        if slot.get("duration_min"):
            self.length.setValue(int(slot["duration_min"]))
        if slot.get("min_presence_min"):
            self.min_presence.setValue(int(slot["min_presence_min"]))
        if slot.get("camera_source"):
            self.class_src.setText(slot["camera_source"])
        if auto_start and not self.ctrl.running:
            self._start()

    def _on_quick_instr_selected(self, index: int) -> None:
        if index > 0:
            self.instr_input.setText(self.quick_instr_combo.currentText())

    def _log_instruction_action(self) -> None:
        text = self.instr_input.text().strip()
        if not text and self.quick_instr_combo.currentIndex() > 0:
            text = self.quick_instr_combo.currentText()
        if not text:
            return
        if not self.ctrl.running:
            QMessageBox.information(self, "Session not running",
                                    "Please start capturing the class session first before logging instructions.")
            return
        self.ctrl.log_instruction(text, type_="INSTRUCTION", severity=1)
        self.instr_input.clear()
        self.quick_instr_combo.setCurrentIndex(0)

    def _refresh_sections(self) -> None:
        current = self.section.currentText()
        self.section.clear()
        self.section.addItem("All students")
        self.section.addItems(self.ctx.db.sections())
        i = self.section.findText(current)
        self.section.setCurrentIndex(max(0, i))

    # ---------------------------------------------------------------- start/stop
    def _start(self) -> None:
        start_ts = time.time()
        if not self.now_box.isChecked():
            t = self.start_time.time()
            start_ts = datetime.now().replace(hour=t.hour(), minute=t.minute(), second=0, microsecond=0).timestamp()
        if start_ts + self.length.value() * 60 <= time.time():
            QMessageBox.warning(self, "That class time has passed",
                                "With this start time and length the class is already over. Choose a later start "
                                "time, or tick 'Start now'.")
            return
        gate = self.gate_src.text().strip() or "none"
        cfg = SessionConfig(
            kind=self.kind, title=self.title.text().strip() or "Untitled session",
            section="" if self.section.currentIndex() == 0 else self.section.currentText(),
            start_ts=start_ts, duration_min=self.length.value(),
            min_presence_min=min(self.min_presence.value(), self.length.value()),
            class_source=self.class_src.text().strip() or "0", gate_source=gate,
            objects=self.objects.isChecked() if self.kind == "exam" else False)
        try:
            self.ctrl.start(cfg)
        except FileNotFoundError as exc:
            self._offer_models(str(exc))
            return
        except (ValueError, RuntimeError) as exc:
            QMessageBox.warning(self, "Cannot start the session", str(exc))
            return
        except Exception as exc:                              # unexpected: show it instead of dying silently
            QMessageBox.critical(self, "Cannot start the session", f"{exc.__class__.__name__}: {exc}")
            return
        self.class_view.clear()
        self.gate_view.clear()
        separate = gate.lower() not in ("same", "none", "")
        self.gate_view.setVisible(separate)
        self.gate_banner.setVisible(gate.lower() != "none")
        self.gate_banner.set_state("info", "Gate: waiting for a student")
        if hasattr(self, "logs_table"):
            self.logs_table.setRowCount(0)
        if self.kind == "exam":
            self.alerts.setRowCount(0)
        self._set_running(True)
        if self.ctrl.notices:                                 # e.g. an optional feature that could not start
            QMessageBox.information(self, "The session is running, with one change", "\n\n".join(self.ctrl.notices))

    def _stop(self) -> None:
        att = self.ctrl.att
        if att is not None and time.time() < att.E:
            left = max(0, att.E - max(time.time(), att.S))
            ans = QMessageBox.question(
                self, "Stop before the class ends?",
                f"{fmt_dur(left)} of the class remain. Results will be worked out up to now, with the required "
                f"minutes scaled down in proportion.\n\nStop and save now?")
            if ans != QMessageBox.StandardButton.Yes:
                return
        self.ctrl.stop()

    def _offer_models(self, message: str) -> None:
        if offer_model_download(self, message):
            QMessageBox.information(self, "Models ready", "The face models are installed. Press Start again.")

    def _set_running(self, running: bool) -> None:
        for w in (self.title, self.section, self.start_time, self.now_box, self.length, self.min_presence,
                  self.class_src, self.gate_src, self.objects, self.timetable_combo):
            w.setEnabled(not running and (w is not self.start_time or not self.now_box.isChecked()))
        self.start_btn.setEnabled(not running)
        self.stop_btn.setEnabled(running)
        if hasattr(self, "log_instr_btn"):
            self.log_instr_btn.setEnabled(running)
        if hasattr(self, "instr_input"):
            self.instr_input.setEnabled(running)

    def is_running(self) -> bool:
        return self.ctrl.running

    def stop_if_running(self) -> None:
        if self.ctrl.running:
            self.ctrl.stop()

    # ------------------------------------------------------------ controller slots
    @Slot(str, QImage)
    def _on_frame(self, role, img) -> None:
        (self.gate_view if role == "gate" else self.class_view).set_frame(img)

    @Slot(str, object)
    def _on_overlays(self, role, overlays) -> None:
        (self.gate_view if role == "gate" else self.class_view).set_overlays(overlays)

    @Slot(str, str)
    def _on_status(self, role, text) -> None:
        self.cam_status.setText(f"{'Gate' if role == 'gate' else 'Classroom'} camera: {text}")
        view = self.gate_view if role == "gate" else self.class_view
        if text != "Live":
            if not text.startswith(("Processing error", "Phone, book")):
                view.clear()                                  # never leave a frozen last frame that looks live
            view.set_placeholder(text)

    @Slot(str, str)
    def _on_gate_msg(self, kind, text) -> None:
        now = time.time()
        if kind in ("info", "warn") and now < self._hold_until:
            return                                            # let a success message stay readable
        if kind == "ok":
            self._hold_until = now + 4.0
            QApplication.beep()
        self.gate_banner.set_state(kind, text)

    @Slot(object)
    def _on_tick(self, info) -> None:
        self.phase.setText(info["phase"])
        self.gate_state.setText(info["gate"])

    @Slot(object)
    def _on_attendance(self, rows) -> None:
        t = self.table
        final = not self.ctrl.running
        now = time.time() if not final else None
        if t.rowCount() != len(rows):
            t.setRowCount(len(rows))
        in_class = checked = 0
        for i, r in enumerate(rows):
            state = r["state"]
            in_class += state == "In class"
            checked += r["check_in"] is not None
            set_cell(t, i, 0, r["reg_no"])
            set_cell(t, i, 1, r["name"]).setToolTip(r["reason"])
            colour = theme.GREEN if state == "In class" else theme.AMBER if state == "Out" else theme.MUTED
            set_cell(t, i, 2, state, bold=state == "In class", fg=colour)
            set_cell(t, i, 3, fmt_clock(r["check_in"], False), center=True)
            set_cell(t, i, 4, fmt_clock(r["check_out"], False), center=True)
            set_cell(t, i, 5, fmt_dur(r["present_sec"]), center=True)
            set_cell(t, i, 6, "", data=PresenceData(r["start"], r["end"], r["intervals"], r["check_in"],
                                                    r["check_out"], now))
            proj_colour = {"Qualified": theme.GREEN, "Can still qualify": theme.MUTED}.get(r["projection"], theme.RED)
            set_cell(t, i, 7, r["projection"], fg=proj_colour)
            if final:
                set_status_cell(t, i, 8, r["status"])
                t.item(i, 8).setToolTip(r["reason"])
            else:
                set_cell(t, i, 8, "-", fg=theme.MUTED, center=True)
        t.viewport().update()
        self.counts.setText(f"In the room now: {in_class} of {len(rows)}.  Checked in: {checked}.")

    @Slot(object)
    def _on_alert(self, ev) -> None:
        if hasattr(self, "logs_table"):
            t = self.logs_table
            t.insertRow(0)
            colour = SEVERITY_COLOUR.get(ev.get("severity", 1), theme.MUTED)
            set_cell(t, 0, 0, fmt_clock(ev["ts"]))
            set_cell(t, 0, 1, ev.get("label", ev.get("type", "Event")), bold=True, fg=colour)
            set_cell(t, 0, 2, ev.get("detail", ""))
            set_cell(t, 0, 3, ev.get("name", "System"))
            while t.rowCount() > 500:
                t.removeRow(t.rowCount() - 1)
        if self.kind == "exam" and hasattr(self, "alerts"):
            t = self.alerts
            t.insertRow(0)
            colour = SEVERITY_COLOUR.get(ev.get("severity", 1), theme.MUTED)
            set_cell(t, 0, 0, fmt_clock(ev["ts"]), data=ev)
            set_cell(t, 0, 1, ev.get("name", "Unknown"))
            set_cell(t, 0, 2, ev.get("label", ev.get("type", "Alert")), bold=True, fg=colour)
            set_cell(t, 0, 3, ev.get("detail", ""))
            while t.rowCount() > 500:
                t.removeRow(t.rowCount() - 1)

    @Slot(object)
    def _on_risk(self, rows) -> None:
        fill_risk_table(self.ranking, rows)
        if self.kind == "exam":
            self._update_cards_and_metrics(rows)

    def _update_cards_and_metrics(self, rows: list) -> None:
        total_students = len(rows)
        normal_count = sum(1 for r in rows if r.get("score", 0.0) < 20.0)
        low_count = sum(1 for r in rows if 20.0 <= r.get("score", 0.0) < 40.0)
        medium_count = sum(1 for r in rows if 40.0 <= r.get("score", 0.0) < 60.0)
        high_critical = sum(1 for r in rows if r.get("score", 0.0) >= 60.0)
        total_incidents = sum(r.get("incidents", 0) for r in rows)

        if hasattr(self, "m_total"):
            self.m_total.setText(str(total_students))
            self.m_normal.setText(str(normal_count))
            self.m_low.setText(str(low_count))
            self.m_med.setText(str(medium_count))
            self.m_high.setText(str(high_critical))
            self.m_incidents.setText(str(total_incidents))

        cols = 3
        for i, r in enumerate(rows):
            sid = r.get("sid")
            key = sid or r.get("key")
            card = self._cards.get(key)
            if card is None:
                photo_path = None
                reg = ""
                if sid is not None:
                    samples = self.ctx.db.samples(sid)
                    if samples:
                        photo_path = samples[0]["image_path"]
                    st = self.ctx.db.get_student(sid)
                    if st is not None:
                        reg = st["reg_no"] if "reg_no" in st.keys() else ""
                card = StudentCardWidget(sid, r.get("name", "Student"), reg, photo_path, self.cards_container)
                card.clicked.connect(self._show_student_details)
                self._cards[key] = card
                row_idx = len(self._cards) - 1
                self.cards_layout.addWidget(card, row_idx // cols, row_idx % cols)

            face_status = "In frame (normal)"
            if r.get("missing_sec", 0) > 0:
                face_status = f"Missing ({r.get('missing_sec', 0)}s)"
            elif r.get("away_pct", 0) > 25.0:
                face_status = "Looking away"
            elif r.get("multiple_faces", 0) > 0:
                face_status = "Multiple faces"
            elif r.get("talking", 0) > 0:
                face_status = "Suspected talking"
            elif r.get("objects", 0) > 0:
                face_status = "Prohibited object"

            disp_level = r.get("suspicion_level", "Normal")
            card.update_level(disp_level, r.get("score", 0.0), r.get("incidents", 0),
                              r.get("last_activity", "Normal monitoring"), face_status)

    def _show_student_details(self, sid: int) -> None:
        if self.ctrl.session_id:
            dlg = StudentDetailDialog(self.ctx, self.ctrl.session_id, sid, self)
            dlg.exec()

    def _open_alert_review(self) -> None:
        rows = self.alerts.selectionModel().selectedRows()
        if not rows:
            QMessageBox.information(self, "Select Alert", "Select an alert from the table first.")
            return
        data = self.alerts.item(rows[0].row(), 0).data(Qt.ItemDataRole.UserRole)
        if not isinstance(data, dict):
            return
        dlg = AlertReviewDialog(self.ctx, data, self)
        dlg.exec()

    def _show_evidence(self) -> None:
        rows = self.alerts.selectionModel().selectedRows()
        if not rows:
            return
        data = self.alerts.item(rows[0].row(), 0).data(Qt.ItemDataRole.UserRole)
        rel = data.get("snapshot", "") if isinstance(data, dict) else (data or "")
        pix = QPixmap(str(DATA_DIR / rel)) if rel else QPixmap()
        if pix.isNull():
            self.evidence.setText("No snapshot saved for this alert.")
            return
        self.evidence.setPixmap(pix.scaled(self.evidence.width(), self.evidence.height(),
                                           Qt.AspectRatioMode.KeepAspectRatio,
                                           Qt.TransformationMode.SmoothTransformation))

    @Slot(int)
    def _on_finished(self, session_id) -> None:
        self._set_running(False)
        self.phase.setText("Session saved.")
        self.gate_state.setText("Open Reports for the full record and exports.")
        self.gate_banner.set_state("info", "Session finished")
        self._apply_defaults()
