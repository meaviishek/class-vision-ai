"""Students page: browse, edit, remove, and rebuild face data."""
from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (QApplication, QComboBox, QDialog, QFileDialog, QFormLayout, QHBoxLayout, QLineEdit, QListView,
                               QListWidget, QListWidgetItem, QMessageBox, QProgressDialog, QVBoxLayout, QWidget)

from ...config import DATA_DIR
from ...services.enrollment import delete_student_files, rebuild_embeddings, sample_from_file, save_samples
from ...utils import fmt_datetime
from ...vision.engine import FaceEngine
from ..widgets import button, label, make_table, offer_model_download, set_cell

AL = Qt.AlignmentFlag


class StudentDialog(QDialog):
    def __init__(self, ctx, student, parent=None):
        super().__init__(parent)
        self.ctx, self.sid = ctx, student["id"]
        self.setWindowTitle(f"{student['name']} ({student['reg_no']})")
        self.setMinimumWidth(520)
        lay = QVBoxLayout(self)
        form = QFormLayout()
        self.fields = {}
        for key, caption in (("reg_no", "Registration no."), ("name", "Full name"), ("section", "Section"),
                             ("department", "Department"), ("course", "Course or programme"),
                             ("year", "Year or semester"), ("email", "Email"), ("phone", "Phone"),
                             ("notes", "Notes")):
            w = QLineEdit(student[key] or "")
            self.fields[key] = w
            form.addRow(caption, w)
        self.role = QComboBox()
        self.role.addItems(["Student", "Staff or invigilator"])
        self.role.setCurrentIndex(1 if student["role"] == "staff" else 0)
        form.addRow("Role", self.role)
        lay.addLayout(form)
        consent = fmt_datetime(student["consent_at"]) if student["consent_at"] else "not recorded"
        lay.addWidget(label(f"Consent recorded: {consent}", "hint"))
        lay.addWidget(label("Face photos", "section"))
        self.photos = QListWidget()
        self.photos.setViewMode(QListView.ViewMode.IconMode)
        self.photos.setIconSize(QSize(84, 84))
        self.photos.setResizeMode(QListView.ResizeMode.Adjust)
        self.photos.setMovement(QListView.Movement.Static)
        self.photos.setFixedHeight(130)
        for i, smp in enumerate(ctx.db.samples(self.sid), start=1):
            item = QListWidgetItem(QIcon(QPixmap(str(DATA_DIR / smp["image_path"]))), str(i))
            item.setData(Qt.ItemDataRole.UserRole, smp["id"])
            self.photos.addItem(item)
        lay.addWidget(self.photos)
        row = QHBoxLayout()
        self.del_photo = button("Delete selected photo", "danger")
        self.del_photo.clicked.connect(self.delete_photo)
        self.add_photo_btn = button("Upload photo from file...")
        self.add_photo_btn.clicked.connect(self.add_photo)
        cancel, save = button("Cancel"), button("Save changes", "primary")
        cancel.clicked.connect(self.reject)
        save.clicked.connect(self.save)
        row.addWidget(self.del_photo)
        row.addWidget(self.add_photo_btn)
        row.addStretch(1)
        row.addWidget(cancel)
        row.addWidget(save)
        lay.addLayout(row)

    def add_photo(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, "Choose photos of this person", "",
                                                "Images (*.jpg *.jpeg *.png *.bmp *.webp)")
        if not paths:
            return
        try:
            engine = FaceEngine(self.ctx.settings.det_score_threshold)
        except FileNotFoundError as exc:
            if offer_model_download(self, str(exc)):
                QMessageBox.information(self, "Models ready", "The face models are installed.")
            return
        student = self.ctx.db.get_student(self.sid)
        if not student:
            return
        added = 0
        smp_list = []
        for path in paths:
            smp = sample_from_file(engine, path)
            if smp is not None:
                smp_list.append(smp)
                added += 1
        if not smp_list:
            QMessageBox.warning(self, "No face found", "No clear face could be detected in the selected image(s).")
            return
        start_idx = len(self.ctx.db.samples(self.sid)) + 1
        save_samples(self.ctx.db, self.sid, student["reg_no"], student["name"], smp_list, start_index=start_idx)
        self.photos.clear()
        for i, smp in enumerate(self.ctx.db.samples(self.sid), start=1):
            item = QListWidgetItem(QIcon(QPixmap(str(DATA_DIR / smp["image_path"]))), str(i))
            item.setData(Qt.ItemDataRole.UserRole, smp["id"])
            self.photos.addItem(item)
        self.ctx.students_changed.emit()
        QMessageBox.information(self, "Photo added", f"Added {added} photo{'s' if added != 1 else ''}.")

    def delete_photo(self) -> None:
        item = self.photos.currentItem()
        if item is None:
            return
        rel = self.ctx.db.delete_sample(item.data(Qt.ItemDataRole.UserRole))
        if rel:
            try:
                (DATA_DIR / rel).unlink()
            except OSError:
                pass
        self.photos.takeItem(self.photos.row(item))
        if self.photos.count() < self.ctx.settings.enroll_min_samples:
            QMessageBox.information(self, "Few photos left",
                                    "Recognition works best with several photos. Add more from the Enroll page.")

    def save(self) -> None:
        data = {k: w.text().strip() for k, w in self.fields.items()}
        if not data["reg_no"] or not data["name"]:
            QMessageBox.warning(self, "Details missing", "The registration number and name cannot be empty.")
            return
        data["role"] = "staff" if self.role.currentIndex() == 1 else "student"
        try:
            self.ctx.db.update_student(self.sid, **data)
        except Exception as exc:                               # e.g. duplicate registration number
            QMessageBox.warning(self, "Could not save", f"{exc}")
            return
        self.accept()


class StudentsPage(QWidget):
    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 20)
        root.setSpacing(12)
        root.addWidget(label("Students", "title"))
        root.addWidget(label("Everyone enrolled in the system. Double-click a row to edit details or manage photos.",
                             "muted", wrap=True))
        bar = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search by name or registration number")
        self.search.setFixedWidth(320)
        self.section = QComboBox()
        self.section.setMinimumWidth(160)
        self.edit_btn = button("Edit details")
        self.remove_btn = button("Remove", "danger")
        self.rebuild_btn = button("Rebuild face data", tip="Recompute every face fingerprint from the saved photos. "
                                                          "Use this after changing the recognition model.")
        bar.addWidget(self.search)
        bar.addWidget(self.section)
        bar.addStretch(1)
        bar.addWidget(self.rebuild_btn)
        bar.addWidget(self.edit_btn)
        bar.addWidget(self.remove_btn)
        root.addLayout(bar)
        self.table = make_table(["Reg. no", "Name", "Role", "Section", "Department", "Photos", "Consent"],
                                stretch=[1])
        root.addWidget(self.table, 1)
        self.empty = label("No one is enrolled yet. Open Enroll students to add the first person.", "muted")
        self.empty.setAlignment(AL.AlignCenter)
        root.addWidget(self.empty)

        self.search.textChanged.connect(self.refresh)
        self.section.currentIndexChanged.connect(self.refresh)
        self.edit_btn.clicked.connect(self.edit)
        self.remove_btn.clicked.connect(self.remove)
        self.rebuild_btn.clicked.connect(self.rebuild)
        self.table.doubleClicked.connect(lambda _idx: self.edit())
        ctx.students_changed.connect(self.refresh)
        self.refresh()

    def refresh(self, *_args) -> None:
        current = self.section.currentText()
        self.section.blockSignals(True)
        self.section.clear()
        self.section.addItem("All sections")
        self.section.addItems(self.ctx.db.sections())
        self.section.setCurrentIndex(max(0, self.section.findText(current)))
        self.section.blockSignals(False)
        section = None if self.section.currentIndex() == 0 else self.section.currentText()
        rows = self.ctx.db.list_students(self.search.text().strip(), section)
        t = self.table
        t.setRowCount(len(rows))
        for i, r in enumerate(rows):
            set_cell(t, i, 0, r["reg_no"], data=r["id"])
            set_cell(t, i, 1, r["name"])
            set_cell(t, i, 2, "Staff" if r["role"] == "staff" else "Student")
            set_cell(t, i, 3, r["section"] or "")
            set_cell(t, i, 4, r["department"] or "")
            set_cell(t, i, 5, str(r["samples"]), center=True)
            set_cell(t, i, 6, "Yes" if r["consent_at"] else "Not recorded", center=True)
        self.empty.setVisible(not rows and not self.search.text().strip())
        self.table.setVisible(bool(rows) or bool(self.search.text().strip()))

    def _selected_id(self):
        rows = self.table.selectionModel().selectedRows()
        return self.table.item(rows[0].row(), 0).data(Qt.ItemDataRole.UserRole) if rows else None

    def edit(self) -> None:
        sid = self._selected_id()
        if sid is None:
            return
        if StudentDialog(self.ctx, self.ctx.db.get_student(sid), self).exec():
            self.ctx.students_changed.emit()

    def remove(self) -> None:
        sid = self._selected_id()
        if sid is None:
            return
        s = self.ctx.db.get_student(sid)
        ans = QMessageBox.question(
            self, "Remove this person?",
            f"Remove {s['name']} ({s['reg_no']})?\n\nTheir face photos and their attendance history are deleted. "
            f"This cannot be undone.")
        if ans != QMessageBox.StandardButton.Yes:
            return
        paths = self.ctx.db.delete_student(sid)
        delete_student_files(paths, sid, s["reg_no"])
        self.ctx.students_changed.emit()

    def rebuild(self) -> None:
        total = len(self.ctx.db.all_samples())
        if total == 0:
            QMessageBox.information(self, "Nothing to rebuild", "There are no saved face photos yet.")
            return
        try:
            engine = FaceEngine(self.ctx.settings.det_score_threshold)
        except FileNotFoundError as exc:
            offer_model_download(self, str(exc))
            return
        dlg = QProgressDialog("Recomputing face data from the saved photos...", "", 0, total, self)
        dlg.setCancelButton(None)
        dlg.setWindowModality(Qt.WindowModality.WindowModal)
        dlg.setMinimumDuration(0)

        def progress(done: int, count: int) -> None:
            dlg.setValue(done)
            QApplication.processEvents()

        ok, bad = rebuild_embeddings(self.ctx.db, engine, progress)
        dlg.close()
        text = f"Updated {ok} photo{'s' if ok != 1 else ''}."
        if bad:
            text += f" {bad} had no detectable face; consider deleting those photos."
        QMessageBox.information(self, "Face data rebuilt", text)
