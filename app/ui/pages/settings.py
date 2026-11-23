"""Settings page. The form is generated from SPEC, so every field in Settings is editable here."""
from __future__ import annotations

from dataclasses import fields, replace

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QDoubleSpinBox, QFormLayout, QHBoxLayout, QLineEdit, QMessageBox,
                               QScrollArea, QSpinBox, QVBoxLayout, QWidget)

from ...config import DATA_DIR, MODELS_DIR, Settings
from ...vision import models
from .. import theme
from ..widgets import button, label, offer_model_download, panel

AL = Qt.AlignmentFlag

# (key, caption, kind, minimum, maximum, step, tooltip)
SPEC = [
    ("Attendance rules", [
        ("class_duration_min", "Default class length (minutes)", "int", 1, 600, 1,
         "Pre-filled when you start a class."),
        ("min_presence_min", "Minimum time in the room (minutes)", "int", 1, 600, 1,
         "A student must be seen in the room this long to count as present."),
        ("gap_tolerance_sec", "Dropout tolerance (seconds)", "int", 10, 900, 10,
         "If the camera loses a student for less than this they still count as present. "
         "Longer gaps are recorded as breaks."),
        ("require_checkin", "Require a face check-in at the gate", "bool", 0, 0, 0,
         "Without it a student with enough time in the room goes to 'needs review'."),
        ("require_checkout", "Require a face check-out at the gate", "bool", 0, 0, 0,
         "Without it a student with enough time in the room goes to 'needs review'."),
        ("checkin_before_min", "Gate opens before class start (minutes)", "int", 0, 120, 1, ""),
        ("checkin_after_min", "Check-in closes after class start (minutes)", "int", 1, 120, 1, ""),
        ("checkout_before_min", "Check-out opens before class end (minutes)", "int", 0, 120, 1, ""),
        ("checkout_after_min", "Check-out closes after class end (minutes)", "int", 0, 240, 1, ""),
    ]),
    ("Gate camera", [
        ("gate_min_face_ratio", "Face size needed at the gate (share of frame width)", "float", 0.05, 0.8, 0.01,
         "Only a face this large counts as 'standing at the gate'. Keeps people in the background out."),
        ("gate_liveness", "Ask for a head turn before accepting", "bool", 0, 0, 0,
         "A basic check against holding up a photo. It is not a full anti-spoofing system."),
        ("gate_liveness_yaw_deg", "Head turn needed (degrees)", "float", 5, 60, 1, ""),
    ]),
    ("Recognition", [
        ("recog_threshold", "Match threshold (cosine similarity)", "float", 0.2, 0.9, 0.01,
         "Higher is stricter. 0.36 is the model's published default; 0.40 adds a safety margin."),
        ("recog_margin", "Margin over the runner-up", "float", 0.0, 0.3, 0.01,
         "The best match must beat the second-best person by this much. Guards against look-alikes."),
        ("det_score_threshold", "Face detector confidence", "float", 0.3, 0.99, 0.01,
         "Lower finds more small faces in a wide classroom shot, with more false detections."),
        ("min_face_px", "Smallest face used for recognition (pixels)", "int", 16, 300, 1,
         "Faces smaller than this are tracked but not identified. Use a higher-resolution camera if many are skipped."),
        ("vote_window", "Votes considered", "int", 1, 20, 1, "Identity is decided by voting over recent matches."),
        ("vote_required", "Votes needed to confirm an identity", "int", 1, 20, 1, ""),
        ("reverify_sec", "Re-check identity every (seconds)", "float", 1, 120, 1, ""),
        ("track_max_age_sec", "Keep a lost face track for (seconds)", "float", 1, 60, 1, ""),
    ]),
    ("Cameras and speed", [
        ("classroom_source", "Classroom camera", "text", 0, 0, 0,
         "Webcam number such as 0, an rtsp:// address, or a video file path."),
        ("gate_source", "Gate camera", "text", 0, 0, 0,
         "'same' uses the classroom camera, 'none' turns the gate off, or enter a second camera."),
        ("enroll_source", "Enrollment camera", "text", 0, 0, 0, ""),
        ("capture_width", "Webcam width (pixels)", "int", 320, 3840, 10, "Applies to webcams only."),
        ("capture_height", "Webcam height (pixels)", "int", 240, 2160, 10, ""),
        ("class_process_fps", "Classroom analysis rate (per second)", "float", 0.2, 15, 0.1,
         "Lower this if the computer struggles; presence is still tracked."),
        ("gate_process_fps", "Gate analysis rate (per second)", "float", 0.5, 30, 0.5, ""),
    ]),
    ("Enrollment", [
        ("enroll_samples", "Photos to capture", "int", 3, 30, 1, ""),
        ("enroll_min_samples", "Minimum photos to save a student", "int", 1, 30, 1, ""),
        ("enroll_min_face_ratio", "Face size needed (share of frame width)", "float", 0.05, 0.8, 0.01, ""),
        ("enroll_blur_min", "Sharpness needed", "float", 5, 500, 5, "Lower accepts blurrier photos."),
        ("enroll_interval_sec", "Seconds between photos", "float", 0.5, 10, 0.1, ""),
    ]),
    ("Exam proctoring", [
        ("yaw_limit_deg", "Head turn counted as looking away (degrees)", "float", 15, 80, 1,
         "Looking down at the paper is never flagged; sideways turns are."),
        ("pitch_up_limit_deg", "Looking up counted as looking away (degrees)", "float", 10, 70, 1, ""),
        ("look_away_sec", "A look-away must last (seconds)", "float", 1, 30, 0.5, ""),
        ("glance_count", "Repeated glancing: number of look-aways", "int", 2, 50, 1, ""),
        ("glance_window_sec", "Repeated glancing: within (seconds)", "int", 20, 1800, 10, ""),
        ("missing_sec", "Alert when an identified face is gone for (seconds)", "int", 5, 600, 5, ""),
        ("unknown_sec", "Alert when an unknown face stays for (seconds)", "int", 3, 300, 1,
         "Enroll invigilators as staff so they are not flagged."),
        ("object_detection", "Detect phones, books and laptops by default", "bool", 0, 0, 0,
         "Needs: pip install ultralytics. Small objects in a wide shot are often missed."),
        ("object_conf", "Object detection confidence", "float", 0.1, 0.95, 0.05, ""),
        ("object_sec", "An object must stay near a student for (seconds)", "float", 1, 30, 0.5, ""),
        ("save_evidence", "Save a snapshot with each alert", "bool", 0, 0, 0, ""),
        ("pitch_down_limit_deg", "Looking down limit (degrees)", "float", 10, 60, 1, ""),
        ("detect_looking_down", "Flag prolonged looking down", "bool", 0, 0, 0, ""),
        ("detect_multiple_faces", "Flag multiple faces in camera", "bool", 0, 0, 0, ""),
        ("detect_talking", "Detect talking and lip movements", "bool", 0, 0, 0, ""),
        ("detect_obstruction", "Detect camera lens obstruction", "bool", 0, 0, 0, ""),
        ("weight_looking_away", "Suspicion weight: Looking away", "int", 1, 100, 1, ""),
        ("weight_repeated_looking", "Suspicion weight: Repeated glancing", "int", 1, 100, 1, ""),
        ("weight_looking_down", "Suspicion weight: Looking down", "int", 1, 100, 1, ""),
        ("weight_talking", "Suspicion weight: Suspected talking", "int", 1, 100, 1, ""),
        ("weight_phone", "Suspicion weight: Phone detected", "int", 1, 100, 1, ""),
        ("weight_notes", "Suspicion weight: Cheat notes / switch", "int", 1, 100, 1, ""),
        ("weight_multiple_faces", "Suspicion weight: Multiple faces", "int", 1, 100, 1, ""),
        ("weight_missing", "Suspicion weight: Missing / Unknown face", "int", 1, 100, 1, ""),
        ("weight_obstruction", "Suspicion weight: Camera obstruction", "int", 1, 100, 1, ""),
    ]),
]


def decimals_for(step: float) -> int:
    """Decimal places a spin box needs so that its step, and every default value, shows exactly."""
    return 2 if step < 0.1 else 1


class SettingsPage(QWidget):
    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.inputs = {}
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 20)
        root.setSpacing(12)
        root.addWidget(label("Settings", "title"))
        root.addWidget(label("Rules for attendance, recognition and exams. Changes apply the next time you start a "
                             "session.", "muted", wrap=True))

        status = panel()
        sl = QHBoxLayout(status)
        sl.setContentsMargins(16, 10, 16, 10)
        self.model_text = label("", "metric")
        self.model_btn = button("Download models")
        self.model_btn.clicked.connect(self._download)
        sl.addWidget(label("Face models", "section"))
        sl.addWidget(self.model_text)
        sl.addStretch(1)
        sl.addWidget(self.model_btn)
        root.addWidget(status)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        bl = QVBoxLayout(body)
        bl.setContentsMargins(0, 0, 8, 0)
        bl.setSpacing(14)
        for title, rows in SPEC:
            box = panel()
            lay = QVBoxLayout(box)
            lay.setContentsMargins(16, 12, 16, 14)
            lay.addWidget(label(title, "section"))
            form = QFormLayout()
            form.setLabelAlignment(AL.AlignLeft)
            form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
            for key, caption, kind, lo, hi, step, tip in rows:
                w = self._make_input(kind, lo, hi, step)
                if tip:
                    w.setToolTip(tip)
                self.inputs[key] = (kind, w)
                form.addRow(caption, w)
            lay.addLayout(form)
            bl.addWidget(box)
        bl.addStretch(1)
        scroll.setWidget(body)
        root.addWidget(scroll, 1)

        bar = QHBoxLayout()
        self.path_note = label(f"Face data and settings live in: {DATA_DIR}", "hint")
        reset = button("Restore defaults")
        save = button("Save settings", "primary")
        reset.clicked.connect(lambda: self._load(Settings()))
        save.clicked.connect(self._save)
        bar.addWidget(self.path_note)
        bar.addStretch(1)
        bar.addWidget(reset)
        bar.addWidget(save)
        root.addLayout(bar)
        self._load(ctx.settings)

    @staticmethod
    def _make_input(kind: str, lo, hi, step) -> QWidget:
        if kind == "int":
            w = QSpinBox()
            w.setRange(int(lo), int(hi))
            w.setSingleStep(int(step))
        elif kind == "float":
            w = QDoubleSpinBox()
            w.setDecimals(decimals_for(step))
            w.setRange(float(lo), float(hi))
            w.setSingleStep(float(step))
        elif kind == "bool":
            w = QCheckBox()
        else:
            w = QLineEdit()
        return w

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.refresh_models()

    def refresh_models(self) -> None:
        missing = models.missing_models()
        if missing:
            self.model_text.setText("Missing")
            self.model_text.setStyleSheet(f"color: {theme.RED};")
        else:
            self.model_text.setText(f"Ready ({MODELS_DIR})")
            self.model_text.setStyleSheet(f"color: {theme.GREEN};")
        self.model_btn.setVisible(bool(missing))

    def _download(self) -> None:
        offer_model_download(self, "The face detection and recognition models are not installed.")
        self.refresh_models()

    # ------------------------------------------------------------------- values
    def _load(self, s: Settings) -> None:
        for key, (kind, w) in self.inputs.items():
            value = getattr(s, key)
            if kind == "bool":
                w.setChecked(bool(value))
            elif kind == "text":
                w.setText(str(value))
            else:
                w.setValue(value)

    def _collect(self) -> Settings:
        s = replace(self.ctx.settings)
        for key, (kind, w) in self.inputs.items():
            if kind == "bool":
                setattr(s, key, w.isChecked())
            elif kind == "text":
                setattr(s, key, w.text().strip())
            else:
                setattr(s, key, w.value())
        return s

    def _save(self) -> None:
        s = self._collect()
        problems = []
        if s.vote_required > s.vote_window:
            problems.append("Votes needed to confirm cannot be more than votes considered.")
        if s.min_presence_min > s.class_duration_min:
            problems.append("The minimum time in the room cannot be longer than the class.")
        if s.enroll_min_samples > s.enroll_samples:
            problems.append("The minimum photos to save cannot be more than the photos to capture.")
        if problems:
            QMessageBox.warning(self, "Check these settings", "\n".join(problems))
            return
        self.ctx.update_settings(s)
        QMessageBox.information(self, "Saved", "Settings saved. They apply the next time you start a session.")


assert sorted(k for _, rows in SPEC for k, *_ in rows) == sorted(f.name for f in fields(Settings)), \
    "Every setting must appear exactly once on the settings page"
