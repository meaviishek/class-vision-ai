"""Paths and user-editable settings (persisted as JSON in data/settings.json)."""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, fields
from pathlib import Path

APP_NAME = "ClassVision"

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
MODELS_DIR = BASE_DIR / "models"
FACES_DIR = DATA_DIR / "faces"
EVIDENCE_DIR = DATA_DIR / "evidence"
EXPORT_DIR = DATA_DIR / "exports"
DB_PATH = DATA_DIR / "classvision.db"
SETTINGS_PATH = DATA_DIR / "settings.json"


def ensure_dirs() -> None:
    for d in (DATA_DIR, MODELS_DIR, FACES_DIR, EVIDENCE_DIR, EXPORT_DIR):
        d.mkdir(parents=True, exist_ok=True)


@dataclass
class Settings:
    # ---- Attendance rules -------------------------------------------------
    class_duration_min: int = 50        # default class length
    min_presence_min: int = 40          # minutes a student must be seen in the room
    gap_tolerance_sec: int = 90         # dropouts shorter than this still count as present
    require_checkin: bool = True        # close-up face check at the start
    require_checkout: bool = True       # close-up face check at the end
    checkin_before_min: int = 10        # gate opens this long before the class starts
    checkin_after_min: int = 10         # ...and closes this long after it starts
    checkout_before_min: int = 5        # check-out opens this long before the class ends
    checkout_after_min: int = 15        # ...and closes this long after it ends

    # ---- Gate (close-up check-in / check-out) ----------------------------
    gate_min_face_ratio: float = 0.14   # face width / frame width needed to count as "at the gate"
    gate_liveness: bool = False         # ask for a small head turn (basic anti-photo check)
    gate_liveness_yaw_deg: float = 20.0

    # ---- Recognition ------------------------------------------------------
    recog_threshold: float = 0.40       # cosine similarity needed to accept a match
    recog_margin: float = 0.04          # best match must beat the runner-up by this much
    det_score_threshold: float = 0.80   # face detector confidence
    min_face_px: int = 36               # smallest face (px wide) used for recognition
    vote_window: int = 5                # identity is decided by voting over recent matches
    vote_required: int = 3
    reverify_sec: float = 8.0           # re-check confirmed identities this often
    track_max_age_sec: float = 8.0      # keep a face track alive this long without detections

    # ---- Cameras / processing --------------------------------------------
    classroom_source: str = "0"         # webcam index, rtsp:// URL or video file
    gate_source: str = "same"           # "same", "none" or a separate source
    enroll_source: str = "0"
    capture_width: int = 1280
    capture_height: int = 720
    class_process_fps: float = 2.0
    gate_process_fps: float = 5.0

    # ---- Enrollment -------------------------------------------------------
    enroll_samples: int = 8
    enroll_min_samples: int = 1
    enroll_min_face_ratio: float = 0.22
    enroll_blur_min: float = 40.0
    enroll_interval_sec: float = 1.5

    # ---- Exam proctoring --------------------------------------------------
    yaw_limit_deg: float = 40.0         # head turned further than this counts as looking away
    pitch_up_limit_deg: float = 30.0
    pitch_down_limit_deg: float = 25.0
    look_away_sec: float = 3.0          # ...for at least this long
    glance_count: int = 5               # this many look-aways ...
    glance_window_sec: int = 120        # ... inside this window = repeated glancing
    missing_sec: int = 20               # identified student not visible for this long
    unknown_sec: int = 10               # unrecognised face present for this long
    object_detection: bool = False      # phones / books / laptops (needs ultralytics)
    object_conf: float = 0.45
    object_sec: float = 2.0
    save_evidence: bool = True
    detect_looking_down: bool = False   # looking down at exam paper is normally allowed
    detect_multiple_faces: bool = False # flag when >=2 faces are detected in single-student webcam
    detect_talking: bool = True         # detect rapid lip movements / speaking behavior
    detect_obstruction: bool = True     # detect camera lens obstruction
    weight_looking_away: int = 5
    weight_repeated_looking: int = 15
    weight_looking_down: int = 15
    weight_talking: int = 20
    weight_phone: int = 35
    weight_notes: int = 30
    weight_multiple_faces: int = 40
    weight_missing: int = 25
    weight_obstruction: int = 30


def _coerce(value, default):
    if value is None:
        return default
    try:
        if isinstance(default, bool):
            if isinstance(value, str):
                return value.strip().lower() in ("1", "true", "yes", "on")
            return bool(value)
        if isinstance(default, int):
            return int(float(value))
        if isinstance(default, float):
            return float(value)
        return str(value)
    except (TypeError, ValueError, OverflowError):            # OverflowError: int(float("inf"))
        return default


def load_settings(path: Path = SETTINGS_PATH) -> Settings:
    s = Settings()
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return s
    if not isinstance(raw, dict):
        return s
    for f in fields(Settings):
        if f.name in raw:
            setattr(s, f.name, _coerce(raw[f.name], getattr(s, f.name)))
    # A hand-edited file can contradict itself. These two would silently stop recognition or saving.
    s.vote_window = max(1, s.vote_window)
    s.vote_required = max(1, min(s.vote_required, s.vote_window))
    s.enroll_samples = max(1, s.enroll_samples)
    s.enroll_min_samples = max(1, min(s.enroll_min_samples, s.enroll_samples))
    return s


def save_settings(s: Settings, path: Path = SETTINGS_PATH) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(asdict(s), indent=2), encoding="utf-8")
    os.replace(tmp, path)                                     # a crash mid-save can never leave half a file
