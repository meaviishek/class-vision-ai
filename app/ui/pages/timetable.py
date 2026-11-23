"""Timetable page: create and manage daily schedules, and start classes according to timetable."""
from __future__ import annotations

import datetime
from typing import Callable, Optional

from PySide6.QtCore import QTime, Qt
from PySide6.QtWidgets import (QComboBox, QCompleter, QDialog, QFormLayout, QFrame,
                               QGridLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
                               QPushButton, QScrollArea, QSpinBox, QTabWidget,
                               QTimeEdit, QVBoxLayout, QWidget)

from .. import theme
from ..widgets import button, label, make_table, set_cell

AL = Qt.AlignmentFlag
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


class TimetableSlotDialog(QDialog):
    def __init__(self, ctx, slot=None, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.slot_id = slot["id"] if slot else None
        self.setWindowTitle("Edit Scheduled Class" if slot else "Add Class to Timetable")
        self.setMinimumWidth(500)
        lay = QVBoxLayout(self)
        form = QFormLayout()
        form.setLabelAlignment(AL.AlignLeft)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

        self.day = QComboBox()
        self.day.addItems(DAYS)
        if slot and slot["day_of_week"] in DAYS:
            self.day.setCurrentText(slot["day_of_week"])
        else:
            today = datetime.datetime.now().strftime("%A")
            if today in DAYS:
                self.day.setCurrentText(today)

        self.subcode = QLineEdit(slot["subcode"] if slot and slot.get("subcode") else "")
        self.subcode.setPlaceholderText("e.g. CSE408, PEA306, CSE471, INT331")

        self.subject = QLineEdit(slot["subject"] if slot else "")
        self.subject.setPlaceholderText("e.g. Artificial Intelligence, Cloud Computing Lab")

        self.section = QLineEdit(slot["section"] if slot and slot["section"] else "")
        self.section.setPlaceholderText("e.g. K3P24WX, K24WX, K202411 (optional)")
        self.section.setCompleter(QCompleter(self.ctx.db.sections(), self.section))

        self.teacher = QLineEdit(slot["teacher"] if slot and slot["teacher"] else "")
        self.teacher.setPlaceholderText("e.g. Dr. Sharma, Prof. Alan Turing")

        self.room = QLineEdit(slot["room"] if slot and slot["room"] else "")
        self.room.setPlaceholderText("e.g. 37-603, 28-502, 33-311")

        self.start_time = QTimeEdit()
        self.start_time.setDisplayFormat("HH:mm")
        st_val = QTime.fromString(slot["start_time"], "HH:mm") if slot and slot["start_time"] else QTime(10, 20)
        self.start_time.setTime(st_val if st_val.isValid() else QTime(10, 20))

        self.end_time = QTimeEdit()
        self.end_time.setDisplayFormat("HH:mm")
        et_val = QTime.fromString(slot["end_time"], "HH:mm") if slot and slot["end_time"] else QTime(11, 10)
        self.end_time.setTime(et_val if et_val.isValid() else QTime(11, 10))

        self.duration = QSpinBox()
        self.duration.setRange(1, 600)
        self.duration.setSuffix(" min")
        self.duration.setValue(int(slot["duration_min"]) if slot and slot["duration_min"] else 50)

        self.min_presence = QSpinBox()
        self.min_presence.setRange(1, 600)
        self.min_presence.setSuffix(" min")
        self.min_presence.setValue(int(slot["min_presence_min"]) if slot and slot["min_presence_min"] else 40)

        self.cam_src = QLineEdit(slot["camera_source"] if slot and slot["camera_source"] else "0")
        self.cam_src.setPlaceholderText("0 or RTSP URL")

        self.notes = QLineEdit(slot["notes"] if slot and slot["notes"] else "")
        self.notes.setPlaceholderText("e.g. Lecture, Practical, Tutorial")

        self.start_time.timeChanged.connect(self._sync_duration_from_times)
        self.end_time.timeChanged.connect(self._sync_duration_from_times)

        form.addRow("Day of week *", self.day)
        form.addRow("Subject Code", self.subcode)
        form.addRow("Subject Name *", self.subject)
        form.addRow("Section", self.section)
        form.addRow("Room / Venue", self.room)
        form.addRow("Teacher / Instructor", self.teacher)
        form.addRow("Start time *", self.start_time)
        form.addRow("End time *", self.end_time)
        form.addRow("Duration", self.duration)
        form.addRow("Minimum presence required", self.min_presence)
        form.addRow("Camera source", self.cam_src)
        form.addRow("Notes / Class type", self.notes)
        lay.addLayout(form)

        btns = QHBoxLayout()
        cancel = button("Cancel")
        save = button("Save changes" if slot else "Save class", "primary")
        cancel.clicked.connect(self.reject)
        save.clicked.connect(self.save)
        btns.addStretch(1)
        btns.addWidget(cancel)
        btns.addWidget(save)
        lay.addLayout(btns)

    def _sync_duration_from_times(self) -> None:
        st = self.start_time.time()
        et = self.end_time.time()
        diff = (et.hour() * 60 + et.minute()) - (st.hour() * 60 + st.minute())
        if diff > 0:
            self.duration.blockSignals(True)
            self.duration.setValue(diff)
            self.duration.blockSignals(False)
            if self.min_presence.value() > diff:
                self.min_presence.setValue(max(1, int(diff * 0.8)))

    def save(self) -> None:
        subject = self.subject.text().strip()
        if not subject:
            QMessageBox.warning(self, "Subject missing", "Please enter the Subject Name.")
            return
        st_str = self.start_time.time().toString("HH:mm")
        et_str = self.end_time.time().toString("HH:mm")
        dur = self.duration.value()
        min_p = min(self.min_presence.value(), dur)
        data = dict(
            day_of_week=self.day.currentText(),
            subcode=self.subcode.text().strip().upper(),
            subject=subject,
            section=self.section.text().strip(),
            teacher=self.teacher.text().strip(),
            room=self.room.text().strip(),
            start_time=st_str,
            end_time=et_str,
            duration_min=dur,
            min_presence_min=min_p,
            camera_source=self.cam_src.text().strip() or "0",
            notes=self.notes.text().strip()
        )
        try:
            if self.slot_id is None:
                self.ctx.db.add_timetable_entry(**data)
            else:
                self.ctx.db.update_timetable_entry(self.slot_id, **data)
        except Exception as exc:
            QMessageBox.critical(self, "Could not save timetable", f"{exc}")
            return
        self.ctx.timetable_changed.emit()
        self.accept()


class WeeklyCalendarGrid(QScrollArea):
    """Visual weekly calendar grid showing columns for Monday through Saturday."""

    def __init__(self, ctx, on_edit_slot=None, on_start_slot=None, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.on_edit_slot = on_edit_slot
        self.on_start_slot = on_start_slot
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.container = QWidget()
        self.grid_layout = QHBoxLayout(self.container)
        self.grid_layout.setContentsMargins(4, 8, 4, 8)
        self.grid_layout.setSpacing(12)
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.setWidget(self.container)

    def refresh(self, section: Optional[str] = None) -> None:
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
        today = datetime.datetime.now().strftime("%A")

        for day in days:
            slots = self.ctx.db.list_timetable(day_of_week=day, section=section)
            is_today = (day == today)
            col_widget = QFrame()
            col_widget.setMinimumWidth(210)
            col_widget.setMaximumWidth(280)
            border_c = theme.BLUE if is_today else theme.RULE
            bg_c = "#f0fdf4" if is_today else "#ffffff"
            col_widget.setStyleSheet(f"""
                QFrame {{
                    background: {bg_c};
                    border: 2px solid {border_c};
                    border-radius: 8px;
                }}
            """)
            col_lay = QVBoxLayout(col_widget)
            col_lay.setContentsMargins(10, 10, 10, 10)
            col_lay.setSpacing(8)

            hdr = QHBoxLayout()
            day_title = QLabel(f"{day}{'  (Today)' if is_today else ''}")
            day_title.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {theme.INK}; border: none; background: transparent;")
            badge = QLabel(f"{len(slots)} class{'es' if len(slots) != 1 else ''}")
            badge.setStyleSheet("font-size: 10px; font-weight: bold; background: #e2e8f0; color: #475569; padding: 2px 6px; border-radius: 4px; border: none;")
            hdr.addWidget(day_title)
            hdr.addStretch(1)
            hdr.addWidget(badge)
            col_lay.addLayout(hdr)

            if not slots:
                no_cls = QLabel("No classes scheduled")
                no_cls.setStyleSheet(f"color: {theme.MUTED}; font-size: 11px; padding: 20px 0; border: none; background: transparent;")
                no_cls.setAlignment(Qt.AlignmentFlag.AlignCenter)
                col_lay.addWidget(no_cls)
            else:
                for s in slots:
                    card = self._create_slot_card(dict(s))
                    col_lay.addWidget(card)

            col_lay.addStretch(1)
            self.grid_layout.addWidget(col_widget)

    def _create_slot_card(self, s: dict) -> QFrame:
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
            }
            QFrame:hover {
                background: #f8fafc;
                border: 1px solid #14304A;
            }
        """)
        cl = QVBoxLayout(card)
        cl.setContentsMargins(8, 8, 8, 8)
        cl.setSpacing(4)

        top = QHBoxLayout()
        time_lbl = QLabel(f"{s['start_time']} - {s['end_time']}")
        time_lbl.setStyleSheet("font-size: 11px; font-weight: bold; color: #0369a1; border: none; background: transparent;")
        top.addWidget(time_lbl)
        top.addStretch(1)
        if s.get("subcode"):
            code_lbl = QLabel(s["subcode"])
            code_lbl.setStyleSheet("font-size: 10px; font-weight: bold; background: #e0f2fe; color: #0284c7; padding: 1px 5px; border-radius: 3px; border: none;")
            top.addWidget(code_lbl)
        cl.addLayout(top)

        subj_lbl = QLabel(s["subject"])
        subj_lbl.setWordWrap(True)
        subj_lbl.setStyleSheet("font-size: 11px; font-weight: bold; color: #0f172a; border: none; background: transparent;")
        cl.addWidget(subj_lbl)

        loc_text = f"Room: {s.get('room', '-') or '-'} • Sec: {s.get('section', '-') or 'All'}"
        loc_lbl = QLabel(loc_text)
        loc_lbl.setStyleSheet(f"font-size: 10px; color: {theme.MUTED}; border: none; background: transparent;")
        cl.addWidget(loc_lbl)

        if s.get("notes"):
            notes_lbl = QLabel(s["notes"])
            notes_lbl.setStyleSheet("font-size: 10px; color: #64748b; font-style: italic; border: none; background: transparent;")
            cl.addWidget(notes_lbl)

        # Quick action buttons
        act = QHBoxLayout()
        act.addStretch(1)
        edit_b = QPushButton("Edit")
        edit_b.setFixedHeight(22)
        edit_b.setStyleSheet("font-size: 10px; padding: 1px 6px;")
        edit_b.clicked.connect(lambda _, slot=s: self.on_edit_slot and self.on_edit_slot(slot))
        start_b = QPushButton("Start Class")
        start_b.setFixedHeight(22)
        start_b.setStyleSheet(f"font-size: 10px; font-weight: bold; background: {theme.INK}; color: #ffffff; padding: 1px 8px; border-radius: 3px; border: none;")
        start_b.clicked.connect(lambda _, slot=s: self.on_start_slot and self.on_start_slot(slot))
        act.addWidget(edit_b)
        act.addWidget(start_b)
        cl.addLayout(act)

        return card


class TimetablePage(QWidget):
    def __init__(self, ctx, on_start_class: Optional[Callable[[dict], None]] = None, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.on_start_class = on_start_class
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 20)
        root.setSpacing(10)

        root.addWidget(label("Timetable & Schedules", "title"))
        root.addWidget(label("Weekly class timetable. Switch days or view the full visual calendar below. Start attendance capture directly according to timetable.",
                             "muted", wrap=True))

        # Top Action Bar
        bar = QHBoxLayout()
        self.day_filter = QComboBox()
        self.day_filter.setMinimumWidth(150)
        self.day_filter.addItem("All days")
        self.day_filter.addItems(DAYS)

        self.sec_filter = QComboBox()
        self.sec_filter.setMinimumWidth(140)

        self.add_btn = button("Add class", "primary")
        self.edit_btn = button("Edit class")
        self.del_btn = button("Delete", "danger")
        self.reset_btn = button("Reset to Default Timetable")
        self.reset_btn.setToolTip("Restore the default weekly timetable (28 classes)")
        self.start_btn = button("Start this class now", "primary")

        bar.addWidget(label("Day:", "muted"))
        bar.addWidget(self.day_filter)
        bar.addWidget(label("Section:", "muted"))
        bar.addWidget(self.sec_filter)
        bar.addStretch(1)
        bar.addWidget(self.reset_btn)
        bar.addWidget(self.start_btn)
        bar.addWidget(self.add_btn)
        bar.addWidget(self.edit_btn)
        bar.addWidget(self.del_btn)
        root.addLayout(bar)

        # Quick day pills navigation bar
        pills_frame = QFrame()
        pills_frame.setStyleSheet(f"background: #ffffff; border: 1px solid {theme.RULE}; border-radius: 6px; padding: 4px;")
        pills_lay = QHBoxLayout(pills_frame)
        pills_lay.setContentsMargins(6, 4, 6, 4)
        pills_lay.setSpacing(6)
        pills_lay.addWidget(label("Quick Day Switch:", "muted"))

        self.day_pills: dict[str, QPushButton] = {}
        for d in ["All days", *DAYS]:
            btn = QPushButton(d)
            btn.setFixedHeight(28)
            btn.clicked.connect(lambda _, day_name=d: self._set_day(day_name))
            pills_lay.addWidget(btn)
            self.day_pills[d] = btn
        pills_lay.addStretch(1)
        root.addWidget(pills_frame)

        # Tabbed interface: Table View & Visual Weekly Calendar Grid
        self.tabs = QTabWidget()

        # Tab 1: Schedule Table View
        table_container = QWidget()
        tl = QVBoxLayout(table_container)
        tl.setContentsMargins(0, 8, 0, 0)
        tl.setSpacing(8)

        headers = ["Day", "Time", "Code", "Subject Name", "Room", "Section", "Teacher", "Duration", "Min presence"]
        self.table = make_table(headers, stretch=[3], row_height=36)
        tl.addWidget(self.table, 1)

        # Enhanced Helpful Empty State Box
        self.empty_box = QFrame()
        self.empty_box.setStyleSheet(f"background: #ffffff; border: 1px dashed {theme.RULE}; border-radius: 8px; padding: 24px;")
        eb_lay = QVBoxLayout(self.empty_box)
        eb_lay.setAlignment(AL.AlignCenter)
        eb_lay.setSpacing(10)

        self.empty_title = QLabel("No classes scheduled for this selection.")
        ef = self.empty_title.font()
        ef.setPointSize(13)
        ef.setBold(True)
        self.empty_title.setFont(ef)
        self.empty_title.setStyleSheet(f"color: {theme.INK};")
        self.empty_title.setAlignment(AL.AlignCenter)
        eb_lay.addWidget(self.empty_title)

        self.empty_sub = QLabel("Weekly timetable classes are scheduled Monday through Saturday (28 classes total).")
        self.empty_sub.setStyleSheet(f"color: {theme.MUTED}; font-size: 12px;")
        self.empty_sub.setAlignment(AL.AlignCenter)
        eb_lay.addWidget(self.empty_sub)

        quick_row = QHBoxLayout()
        quick_row.setAlignment(AL.AlignCenter)
        quick_row.setSpacing(10)

        self.jump_mon_btn = button("View Monday's Schedule (7 classes)", "primary")
        self.jump_mon_btn.clicked.connect(lambda: self._set_day("Monday"))
        quick_row.addWidget(self.jump_mon_btn)

        self.jump_all_btn = button("View All Days (28 classes)")
        self.jump_all_btn.clicked.connect(lambda: self._set_day("All days"))
        quick_row.addWidget(self.jump_all_btn)

        self.empty_add_btn = button("+ Add Class to this Day")
        self.empty_add_btn.clicked.connect(self.add_slot)
        quick_row.addWidget(self.empty_add_btn)

        eb_lay.addLayout(quick_row)
        tl.addWidget(self.empty_box)

        # For backwards compatibility with tests that access self.empty
        self.empty = self.empty_box

        self.tabs.addTab(table_container, "Schedule Table")

        # Tab 2: Visual Weekly Calendar Grid
        self.weekly_grid = WeeklyCalendarGrid(self.ctx, on_edit_slot=self._edit_specific_slot,
                                             on_start_slot=self.on_start_class)
        self.tabs.addTab(self.weekly_grid, "Weekly Calendar Grid")

        root.addWidget(self.tabs, 1)

        # Initial smart selection: if today has classes, show today. Otherwise show Monday (or All days)
        today = datetime.datetime.now().strftime("%A")
        today_has_classes = len(self.ctx.db.list_timetable(today)) > 0
        if today_has_classes:
            initial_day = today
        elif len(self.ctx.db.list_timetable("Monday")) > 0:
            initial_day = "Monday"
        else:
            initial_day = "All days"

        init_idx = self.day_filter.findText(initial_day)
        if init_idx >= 0:
            self.day_filter.setCurrentIndex(init_idx)

        # Connect signals
        self.day_filter.currentIndexChanged.connect(self.refresh)
        self.sec_filter.currentIndexChanged.connect(self.refresh)
        self.add_btn.clicked.connect(self.add_slot)
        self.edit_btn.clicked.connect(self.edit_slot)
        self.del_btn.clicked.connect(self.delete_slot)
        self.reset_btn.clicked.connect(self.reset_default_timetable)
        self.start_btn.clicked.connect(self.start_selected_class)
        self.table.doubleClicked.connect(lambda _idx: self.edit_slot())

        ctx.timetable_changed.connect(self.refresh)
        ctx.students_changed.connect(self._refresh_sections)
        self._refresh_sections()
        self.refresh()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._refresh_sections()
        self.refresh()

    def _set_day(self, day_name: str) -> None:
        idx = self.day_filter.findText(day_name)
        if idx >= 0:
            self.day_filter.setCurrentIndex(idx)

    def _refresh_sections(self) -> None:
        current = self.sec_filter.currentText()
        self.sec_filter.blockSignals(True)
        self.sec_filter.clear()
        self.sec_filter.addItem("All sections")
        self.sec_filter.addItems(self.ctx.db.sections())
        idx = self.sec_filter.findText(current)
        self.sec_filter.setCurrentIndex(max(0, idx))
        self.sec_filter.blockSignals(False)

    def refresh(self, *_args) -> None:
        day = None if self.day_filter.currentIndex() == 0 else self.day_filter.currentText()
        sec = None if self.sec_filter.currentIndex() == 0 else self.sec_filter.currentText()
        rows = self.ctx.db.list_timetable(day, sec)
        t = self.table
        t.setRowCount(len(rows))
        for i, r in enumerate(rows):
            time_span = f"{r['start_time']} - {r['end_time']}"
            set_cell(t, i, 0, r["day_of_week"], data=r["id"], bold=True)
            set_cell(t, i, 1, time_span, center=True)
            set_cell(t, i, 2, r["subcode"] or "-", center=True, bold=True)
            set_cell(t, i, 3, r["subject"], bold=True)
            set_cell(t, i, 4, r["room"] or "-", center=True)
            set_cell(t, i, 5, r["section"] or "All")
            set_cell(t, i, 6, r["teacher"] or "-")
            set_cell(t, i, 7, f"{r['duration_min']} min", center=True)
            set_cell(t, i, 8, f"{r['min_presence_min']} min", center=True)

        # Update empty box texts
        sel_day = self.day_filter.currentText()
        self.empty_title.setText(f"No classes scheduled for {sel_day}.")
        self.empty_box.setVisible(not rows)
        self.table.setVisible(bool(rows))

        has_sel = len(rows) > 0
        self.edit_btn.setEnabled(has_sel)
        self.del_btn.setEnabled(has_sel)
        self.start_btn.setEnabled(has_sel)

        # Update day pills badges and active highlight
        all_counts = {d: len(self.ctx.db.list_timetable(day_of_week=d, section=sec)) for d in DAYS}
        total_count = sum(all_counts.values())

        for d, btn in self.day_pills.items():
            if d == "All days":
                cnt = total_count
            else:
                cnt = all_counts.get(d, 0)
            btn.setText(f"{d} ({cnt})")
            if d == sel_day:
                btn.setStyleSheet(f"background: {theme.INK}; color: #ffffff; font-weight: bold; border-radius: 4px; padding: 2px 10px;")
            else:
                btn.setStyleSheet(f"background: #f1f5f9; color: {theme.INK}; font-weight: normal; border-radius: 4px; padding: 2px 10px;")

        # Refresh the weekly visual grid
        if hasattr(self, "weekly_grid"):
            self.weekly_grid.refresh(sec)

    def _selected_slot(self) -> Optional[dict]:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            if self.table.rowCount() > 0:
                slot_id = self.table.item(0, 0).data(Qt.ItemDataRole.UserRole)
                return dict(self.ctx.db.get_timetable_entry(slot_id))
            return None
        slot_id = self.table.item(rows[0].row(), 0).data(Qt.ItemDataRole.UserRole)
        row = self.ctx.db.get_timetable_entry(slot_id)
        return dict(row) if row else None

    def _edit_specific_slot(self, slot: dict) -> None:
        dlg = TimetableSlotDialog(self.ctx, slot=slot, parent=self)
        dlg.exec()

    def add_slot(self) -> None:
        dlg = TimetableSlotDialog(self.ctx, parent=self)
        dlg.exec()

    def edit_slot(self) -> None:
        slot = self._selected_slot()
        if not slot:
            QMessageBox.information(self, "Select class", "Select a scheduled class from the table to edit.")
            return
        dlg = TimetableSlotDialog(self.ctx, slot=slot, parent=self)
        dlg.exec()

    def delete_slot(self) -> None:
        slot = self._selected_slot()
        if not slot:
            QMessageBox.information(self, "Select class", "Select a scheduled class to delete.")
            return
        ans = QMessageBox.question(
            self, "Confirm Delete",
            f"Delete {slot['subject']} ({slot.get('subcode', '')}) on {slot['day_of_week']} ({slot['start_time']} - {slot['end_time']}) from the timetable?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if ans == QMessageBox.StandardButton.Yes:
            self.ctx.db.delete_timetable_entry(slot["id"])
            self.ctx.timetable_changed.emit()

    def reset_default_timetable(self) -> None:
        ans = QMessageBox.question(
            self, "Restore Default Timetable",
            "Reset and load the full weekly timetable (28 classes)?\n"
            "This will replace all timetable entries with the standard university schedule.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if ans == QMessageBox.StandardButton.Yes:
            count = self.ctx.db.seed_default_timetable(force=True)
            self.ctx.timetable_changed.emit()
            QMessageBox.information(self, "Timetable Reset", f"Successfully loaded {count} default scheduled classes.")

    def start_selected_class(self) -> None:
        slot = self._selected_slot()
        if not slot:
            QMessageBox.information(self, "Select class", "Select a scheduled class to start.")
            return
        if self.on_start_class:
            self.on_start_class(slot)
