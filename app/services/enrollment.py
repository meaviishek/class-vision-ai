"""Enrollment: guided webcam capture with quality checks, saving face samples, rebuilding embeddings."""
from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional, Tuple

import cv2
import numpy as np

from ..config import DATA_DIR, FACES_DIR, Settings
from ..imgio import limit_side, read_image, write_image
from ..utils import VIDEO_OK, VIDEO_WARN, slug
from ..vision.pose import head_pose
from ..vision.types import Overlay

PROMPTS = [
    "Look straight at the camera",
    "Turn your head slightly to your left",
    "Turn your head slightly to your right",
    "Raise your chin a little",
    "Lower your chin a little",
    "Look straight and relax",
    "Smile",
    "Look straight again",
]


@dataclass
class Sample:
    crop: np.ndarray           # BGR face crop with margin, what gets saved to disk
    embedding: np.ndarray
    quality: float             # sharpness (variance of Laplacian on a normalised crop)


@dataclass
class EnrollFrame:
    ok: bool
    hint: str
    prompt: str
    captured: int
    target: int
    sample: Optional[Sample] = None


def crop_with_margin(frame: np.ndarray, bbox: Tuple[float, float, float, float], margin: float) -> np.ndarray:
    h, w = frame.shape[:2]
    x, y, bw, bh = bbox
    x0, y0 = int(max(0, x - margin * bw)), int(max(0, y - margin * bh))
    x1, y1 = int(min(w, x + bw * (1 + margin))), int(min(h, y + bh * (1 + margin)))
    return frame[y0:y1, x0:x1].copy()


def sharpness(bgr_crop: np.ndarray) -> float:
    if bgr_crop.size == 0:
        return 0.0
    gray = cv2.cvtColor(cv2.resize(bgr_crop, (160, 160)), cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


class EnrollProcessor:
    """Runs in the camera thread. Shows hints until the face is good, then auto-captures samples."""

    def __init__(self, engine, settings: Settings):
        self.engine, self.s = engine, settings
        self.capturing = False
        self.target = settings.enroll_samples
        self.captured = 0
        self._last = 0.0

    def start(self, target: Optional[int] = None) -> None:
        self.target = int(target or self.s.enroll_samples)
        self.captured = 0
        self._last = time.time()          # first sample after one interval, so people can get ready
        self.capturing = True

    def stop(self) -> None:
        self.capturing = False

    def process(self, frame: np.ndarray, ts: float):
        h, w = frame.shape[:2]
        prompt = PROMPTS[self.captured % len(PROMPTS)] if self.capturing else ""
        rows = self.engine.detect(frame)
        if len(rows) == 0:
            return EnrollFrame(False, "No face found. Face the camera.", prompt, self.captured, self.target), []
        rows = sorted(rows, key=lambda r: -float(r[2] * r[3]))
        main = rows[0]
        x, y, bw, bh = (float(v) for v in main[:4])
        hint, sharp = "", 0.0
        if len(rows) > 1 and rows[1][2] * rows[1][3] > 0.35 * bw * bh:
            hint = "Only one person should be in the frame."
        elif bw / w < self.s.enroll_min_face_ratio:
            hint = "Move closer to the camera."
        elif bw / w > 0.75:
            hint = "Move back a little."
        else:
            tight = crop_with_margin(frame, (x, y, bw, bh), 0.0)
            sharp = sharpness(tight)
            bright = float(cv2.cvtColor(tight, cv2.COLOR_BGR2GRAY).mean()) if tight.size else 0.0
            pose = head_pose(main[4:14].reshape(5, 2), w, h)
            if sharp < self.s.enroll_blur_min:
                hint = "Hold still: the image is blurry."
            elif bright < 55 or bright > 210:
                hint = "Adjust the lighting: too dark or too bright."
            elif pose is not None and (abs(pose[0]) > 35 or abs(pose[1]) > 30):
                hint = "Turn your face a little less."
        ok = not hint

        sample = None
        if self.capturing and ok and ts - self._last >= self.s.enroll_interval_sec:
            sample = Sample(limit_side(crop_with_margin(frame, (x, y, bw, bh), 0.5), 480),
                            self.engine.embed(frame, main), sharp)
            self._last = ts
            self.captured += 1
            if self.captured >= self.target:
                self.capturing = False
        overlay = Overlay(x / w, y / h, bw / w, bh / h, label="" if ok else hint,
                          color=VIDEO_OK if ok else VIDEO_WARN)
        message = hint or ("Hold still" if self.capturing else "Face looks good")
        return EnrollFrame(ok, message, prompt, self.captured, self.target, sample), [overlay]


def sample_from_file(engine, path) -> Optional[Sample]:
    """Build a sample from a photo on disk (largest face). None if no usable face is found."""
    img = read_image(path)
    if img is None:
        return None
    rows = engine.detect(img)
    if len(rows) == 0:
        # Fallback to lower confidence threshold for user-uploaded profile photos
        rows = engine.detect(img, score_threshold=0.40)
    if len(rows) == 0:
        # Second fallback for challenging lighting / angles
        rows = engine.detect(img, score_threshold=0.25)
    if len(rows) == 0:
        return None
    main = max(rows, key=lambda r: float(r[2] * r[3]))
    x, y, bw, bh = (float(v) for v in main[:4])
    crop = crop_with_margin(img, (x, y, bw, bh), 0.5)
    return Sample(limit_side(crop, 480), engine.embed(img, main), sharpness(crop_with_margin(img, (x, y, bw, bh), 0.0)))


def student_folder(student_id: int, reg_no: str) -> Path:
    return FACES_DIR / f"{student_id:05d}_{slug(reg_no)}"


def save_samples(db, student_id: int, reg_no: str, name: str, samples: List[Sample], start_index: int = 1) -> int:
    """Write each face crop as <name>_<regno>_<n>.jpg and store its embedding in the database.

    An existing photo is never overwritten: if a number is taken (say a photo was deleted earlier and the
    count no longer matches the file names) the next free number is used."""
    folder = student_folder(student_id, reg_no)
    base = f"{slug(name)}_{slug(reg_no)}"
    n = max(1, start_index)
    for smp in samples:
        while (folder / f"{base}_{n:02d}.jpg").exists():
            n += 1
        path = folder / f"{base}_{n:02d}.jpg"
        if not write_image(path, smp.crop, 92):
            raise OSError(f"Could not write the photo {path.name}")
        db.add_sample(student_id, os.path.relpath(path, DATA_DIR), smp.embedding, smp.quality)
        n += 1
    return len(samples)


def delete_student_files(paths: List[str], student_id: int, reg_no: str) -> None:
    """Delete the photo files, then the person's folder if that leaves it empty (also when the
    registration number was edited after enrollment, so the folder name no longer matches it)."""
    folders = {student_folder(student_id, reg_no)}
    for rel in paths:
        target = DATA_DIR / rel
        folders.add(target.parent)
        try:
            target.unlink()
        except OSError:
            pass
    for folder in folders:
        if folder.parent == FACES_DIR:                        # only ever remove a person's own folder
            try:
                folder.rmdir()                                # refuses unless it is empty
            except OSError:
                pass


def rebuild_embeddings(db, engine, progress: Optional[Callable[[int, int], None]] = None) -> Tuple[int, int]:
    """Recompute every stored embedding from the saved face images (use after changing models)."""
    rows = db.all_samples()
    ok = bad = 0
    for i, r in enumerate(rows, start=1):
        img = read_image(DATA_DIR / r["image_path"])
        done = False
        if img is not None:
            faces = engine.detect(img)
            if len(faces):
                main = max(faces, key=lambda f: float(f[2] * f[3]))
                db.update_embedding(r["id"], engine.embed(img, main))
                done = True
        ok += int(done)
        bad += int(not done)
        if progress:
            progress(i, len(rows))
    return ok, bad
