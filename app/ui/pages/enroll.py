"""Enrollment page: register a student (or invigilator) with details and face samples."""
from __future__ import annotations

import time
from typing import List, Optional

from PySide6.QtCore import QSize, Qt, Slot
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QCompleter, QFileDialog, QFormLayout, QHBoxLayout,
                               QLineEdit, QListView, QListWidget, QListWidgetItem, QMessageBox, QProgressBar,
                               QVBoxLayout, QWidget)

from ...services.enrollment import (EnrollFrame, EnrollProcessor, Sample, delete_student_files, sample_from_file,
                                    save_samples)
from ...vision.engine import FaceEngine
from ...vision.gallery import Gallery
from ...workers.camera import CameraWorker, parse_source, to_qimage, webcam_index
from ..widgets import Banner, VideoView, button, label, offer_model_download, panel

AL = Qt.AlignmentFlag


class EnrollPage(QWidget):
    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.worker: Optional[CameraWorker] = None
        self.processor: Optional[EnrollProcessor] = None
        self._file_engine: Optional[FaceEngine] = None
        self.samples: List[Sample] = []
        self._build()
        ctx.settings_changed.connect(self._sync_settings)

    # ------------------------------------------------------------------ layout
    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 20)
        root.setSpacing(12)
        root.addWidget(label("Enroll students", "title"))
        root.addWidget(label("Capture a few clear face photos once. They are what the system recognises later. "
                             "Invigilators can be enrolled as staff so exam alerts ignore them.", "muted", wrap=True))
        body = QHBoxLayout()
        body.setSpacing(18)
        root.addLayout(body, 1)

        left = QVBoxLayout()
        self.view = VideoView("Press Start camera to begin")
        self.prompt = label("", "section")
        self.hint = Banner("The camera is off.", "info")
        self.source = QLineEdit(self.ctx.settings.enroll_source)
        self.source.setFixedWidth(150)
        self.source.setToolTip("Webcam number such as 0, an rtsp:// address, or a video file path.")
        self.cam_btn = button("Start camera")
        self.cap_btn = button("Start guided capture", "primary")
        self.cap_btn.setEnabled(False)
        self.file_btn = button("Add photos from files...")
        self.cam_btn.clicked.connect(self.toggle_camera)
        self.cap_btn.clicked.connect(self.start_capture)
        self.file_btn.clicked.connect(self.add_files)
        row = QHBoxLayout()
        row.addWidget(label("Camera", "muted"))
        row.addWidget(self.source)
        row.addWidget(self.cam_btn)
        row.addWidget(self.cap_btn)
        row.addStretch(1)
        row.addWidget(self.file_btn)
        left.addWidget(self.view, 1)
        left.addWidget(self.prompt)
        left.addWidget(self.hint)
        left.addLayout(row)
        body.addLayout(left, 3)

        form_panel = panel()
        form_panel.setFixedWidth(430)
        fl = QVBoxLayout(form_panel)
        fl.setContentsMargins(16, 14, 16, 14)
        fl.addWidget(label("Details", "section"))
        form = QFormLayout()
        form.setLabelAlignment(AL.AlignLeft)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.reg, self.name = QLineEdit(), QLineEdit()
        self.role = QComboBox()
        self.role.addItems(["Student", "Staff or invigilator"])
        self.section, self.department, self.course = QLineEdit(), QLineEdit(), QLineEdit()
        self.year, self.email, self.phone, self.notes = QLineEdit(), QLineEdit(), QLineEdit(), QLineEdit()
        for caption, w in (("Registration no. *", self.reg), ("Full name *", self.name), ("Role", self.role),
                           ("Section", self.section), ("Department", self.department),
                           ("Course or programme", self.course), ("Year or semester", self.year),
                           ("Email", self.email), ("Phone", self.phone), ("Notes", self.notes)):
            form.addRow(caption, w)
        fl.addLayout(form)
        consent_row = QHBoxLayout()
        self.consent = QCheckBox()
        self.consent.setChecked(True)
        self.consent_lbl = label("This person agrees to their face images being stored and used for attendance "
                                 "and exam monitoring.", "hint", wrap=True)
        self.consent_lbl.setCursor(Qt.CursorShape.PointingHandCursor)
        self.consent_lbl.mousePressEvent = lambda _e: self.consent.setChecked(not self.consent.isChecked())
        consent_row.addWidget(self.consent, 0, AL.AlignTop)
        consent_row.addWidget(self.consent_lbl, 1)
        fl.addLayout(consent_row)
        fl.addWidget(label("Photos", "section"))
        self.thumbs = QListWidget()
        self.thumbs.setViewMode(QListView.ViewMode.IconMode)
        self.thumbs.setIconSize(QSize(72, 72))
        self.thumbs.setResizeMode(QListView.ResizeMode.Adjust)
        self.thumbs.setMovement(QListView.Movement.Static)
        self.thumbs.setFixedHeight(104)
        self.progress = QProgressBar()
        self.progress.setRange(0, self.ctx.settings.enroll_samples)
        self.count = label("No photos yet.", "hint")
        self.upload_photo_btn = button("Upload photo from file...", "primary")
        self.upload_photo_btn.setToolTip("Select and upload student image files from your computer")
        self.upload_photo_btn.clicked.connect(self.add_files)
        fl.addWidget(self.thumbs)
        fl.addWidget(self.progress)
        fl.addWidget(self.count)
        fl.addWidget(self.upload_photo_btn)
        fl.addStretch(1)
        self.save_btn = button("Save student", "primary")
        self.clear_btn = button("Clear photos")
        self.save_btn.clicked.connect(self.save)
        self.clear_btn.clicked.connect(self.clear_samples)
        actions = QHBoxLayout()
        actions.addWidget(self.clear_btn)
        actions.addStretch(1)
        actions.addWidget(self.save_btn)
        fl.addLayout(actions)
        body.addWidget(form_panel)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.section.setCompleter(QCompleter(self.ctx.db.sections(), self.section))

    def _sync_settings(self) -> None:
        if self.worker is None:
            self.source.setText(self.ctx.settings.enroll_source)
        self.progress.setMaximum(max(self.ctx.settings.enroll_samples, len(self.samples), 1))

    # ------------------------------------------------------------------ camera
    def toggle_camera(self) -> None:
        if self.worker is not None:
            self.stop_camera()
            return
        s = self.ctx.settings
        cam = webcam_index(self.source.text() or "0")
        if cam is not None and cam in self.ctx.live_sources:
            QMessageBox.information(self, "Camera in use",
                                    f"Webcam {cam} is being used by a running session. Stop the session first, or "
                                    f"enter another camera number, or use 'Add photos from files'.")
            return
        try:
            engine = FaceEngine(s.det_score_threshold)
        except FileNotFoundError as exc:
            if offer_model_download(self, str(exc)):
                QMessageBox.information(self, "Models ready", "The face models are installed. Press Start camera again.")
            return
        self.processor = EnrollProcessor(engine, s)
        self.worker = CameraWorker(parse_source(self.source.text() or "0"), self.processor, 6.0,
                                   s.capture_width, s.capture_height, parent=self)
        self.worker.frame.connect(self.view.set_frame)
        self.worker.overlays.connect(self.view.set_overlays)
        self.worker.result.connect(self._on_result)
        self.worker.status.connect(self._on_status)
        self.worker.start()
        self.cam_btn.setText("Stop camera")
        self.cap_btn.setEnabled(True)
        self.source.setEnabled(False)

    def stop_camera(self) -> None:
        if self.worker is None:
            return
        if self.processor is not None:
            self.processor.stop()
        self.worker.stop()
        if not self.worker.isRunning():
            self.worker.deleteLater()                         # a thread that is somehow still running is never deleted
        self.worker, self.processor = None, None
        self.view.clear()
        self.view.set_placeholder("Camera is off")
        self.cam_btn.setText("Start camera")
        self.cap_btn.setEnabled(False)
        self.source.setEnabled(True)
        self.prompt.setText("")
        self.hint.set_state("info", "The camera is off.")

    def on_leave(self) -> None:
        self.stop_camera()

    @Slot(str)
    def _on_status(self, text: str) -> None:
        if text != "Live":
            self.view.set_placeholder(text)
            self.hint.set_state("warn", text)

    def start_capture(self) -> None:
        if self.processor is None:
            return
        target = max(1, self.ctx.settings.enroll_samples - len(self.samples))
        self.processor.start(target)
        self.cap_btn.setEnabled(False)
        self.hint.set_state("info", "Get ready. Photos are taken automatically, one at a time.")

    @Slot(object)
    def _on_result(self, f: EnrollFrame) -> None:
        if self.processor is None:
            return
        self.prompt.setText(f.prompt)
        self.hint.set_state("ok" if f.ok else "warn", f.hint)
        if f.sample is not None:
            self._add_sample(f.sample)
        if not self.processor.capturing and not self.cap_btn.isEnabled():
            self.cap_btn.setEnabled(True)
            self.prompt.setText("")
            self.hint.set_state("ok", "Capture finished. Check the photos, fill in the details, then save.")

    # ----------------------------------------------------------------- samples
    def _add_sample(self, smp: Sample) -> None:
        self.samples.append(smp)
        icon = QIcon(QPixmap.fromImage(to_qimage(smp.crop, 144)))
        self.thumbs.addItem(QListWidgetItem(icon, str(len(self.samples))))
        self.progress.setMaximum(max(self.ctx.settings.enroll_samples, len(self.samples)))
        self.progress.setValue(len(self.samples))
        self.count.setText(f"{len(self.samples)} photo{'s' if len(self.samples) != 1 else ''} ready.")

    def clear_samples(self) -> None:
        self.samples.clear()
        self.thumbs.clear()
        self.progress.setValue(0)
        self.count.setText("No photos yet.")

    def add_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, "Choose photos of this person", "",
                                                "Images (*.jpg *.jpeg *.png *.bmp *.webp)")
        if not paths:
            return
        try:
            if self._file_engine is None:
                self._file_engine = FaceEngine(self.ctx.settings.det_score_threshold)
        except FileNotFoundError as exc:
            if offer_model_download(self, str(exc)):
                QMessageBox.information(self, "Models ready", "The face models are installed. Choose the photos again.")
            return
        added = skipped = 0
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            for path in paths:
                smp = sample_from_file(self._file_engine, path)
                if smp is None:
                    skipped += 1
                else:
                    self._add_sample(smp)
                    added += 1
        finally:
            QApplication.restoreOverrideCursor()
        text = f"Added {added} photo{'s' if added != 1 else ''}."
        if skipped:
            text += f" {skipped} had no clear face and {'were' if skipped != 1 else 'was'} skipped."
        self.hint.set_state("ok" if added else "warn", text)
        if not added and skipped:
            QMessageBox.warning(self, "No clear face detected",
                                "No face was recognized in the selected file(s).\n"
                                "Please select a clear, front-facing portrait photo.")

    # -------------------------------------------------------------------- save
    def save(self) -> None:
        s, db = self.ctx.settings, self.ctx.db
        reg, name = self.reg.text().strip(), self.name.text().strip()
        if not reg or not name:
            QMessageBox.warning(self, "Details missing", "Enter the registration number and the full name.")
            return
        if not self.consent.isChecked():
            ans = QMessageBox.question(
                self, "Consent needed",
                "Does this person agree to their face images being stored and used for attendance and exam monitoring?\n\n"
                "Click Yes to confirm consent and save the student.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if ans == QMessageBox.StandardButton.Yes:
                self.consent.setChecked(True)
            else:
                return
        if len(self.samples) < 1:
            QMessageBox.warning(self, "Photo needed",
                                "Please add at least 1 photo of the student (via webcam capture or file upload) before saving.")
            return
        existing = db.get_by_reg(reg)
        gallery = Gallery.from_db(db)
        for smp in self.samples:                              # same face under another registration number?
            other_id, _ = gallery.identify(smp.embedding, 0.55, 0.0)
            if other_id is not None and (existing is None or other_id != existing["id"]):
                other = db.get_student(other_id)
                ans = QMessageBox.question(
                    self, "This face is already enrolled",
                    f"These photos look like {other['name']} ({other['reg_no']}). Save them under {reg} anyway?")
                if ans != QMessageBox.StandardButton.Yes:
                    return
                break
        details = dict(reg_no=reg, name=name, role="staff" if self.role.currentIndex() == 1 else "student",
                       section=self.section.text().strip(), department=self.department.text().strip(),
                       course=self.course.text().strip(), year=self.year.text().strip(),
                       email=self.email.text().strip(), phone=self.phone.text().strip(),
                       notes=self.notes.text().strip(), consent_at=time.time())
        if existing is not None:
            ans = QMessageBox.question(
                self, "Registration number already enrolled",
                f"{existing['name']} ({reg}) is already enrolled. Add these photos to that profile "
                f"and update the details?")
            if ans != QMessageBox.StandardButton.Yes:
                return
        created = existing is None
        try:
            if created:
                sid, first_index = db.add_student(**details), 1
            else:
                sid, first_index = existing["id"], len(db.samples(existing["id"])) + 1
                db.update_student(sid, **details)
        except Exception as exc:                              # e.g. the same registration number typed in another case
            QMessageBox.warning(self, "Could not save", f"{exc}")
            return
        try:
            save_samples(db, sid, reg, name, self.samples, start_index=first_index)
        except Exception as exc:                              # disk full, folder not writable, ...
            if created:                                       # never leave a person with no photos behind
                delete_student_files(db.delete_student(sid), sid, reg)
            self.ctx.students_changed.emit()
            QMessageBox.warning(self, "Could not save the photos",
                                f"{exc}\n\n" + ("Nothing was saved." if created else
                                                "Some of the photos may not have been saved."))
            return
        self.ctx.students_changed.emit()
        saved = len(self.samples)
        self.clear_form()
        self.hint.set_state("ok", f"Saved {name} with {saved} photo{'s' if saved != 1 else ''}. You can enroll the next student.")

    def clear_form(self) -> None:
        for w in (self.reg, self.name, self.section, self.department, self.course, self.year, self.email,
                  self.phone, self.notes):
            w.clear()
        self.role.setCurrentIndex(0)
        self.consent.setChecked(True)
        self.clear_samples()
