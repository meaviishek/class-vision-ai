"""Face detector + recogniser. One instance per thread (OpenCV DNN objects are not thread-safe)."""
from __future__ import annotations

import cv2
import numpy as np

from . import models


class FaceEngine:
    """YuNet finds faces (box, 5 landmarks, score); SFace turns an aligned face into a 128-d vector."""

    def __init__(self, score_threshold: float = 0.8, nms_threshold: float = 0.3,
                 top_k: int = 2000, max_side: int = 1600):
        missing = models.missing_models()
        if missing:
            raise FileNotFoundError(
                "Face models are missing: " + ", ".join(missing) +
                ". Download them from Settings, or run: python scripts/download_models.py")
        self.max_side = max_side
        make_det = getattr(cv2.FaceDetectorYN, "create", None) or cv2.FaceDetectorYN_create
        make_rec = getattr(cv2.FaceRecognizerSF, "create", None) or cv2.FaceRecognizerSF_create
        self._size = (320, 320)
        self._det = make_det(str(models.DETECTOR), "", self._size, score_threshold, nms_threshold, top_k)
        self._rec = make_rec(str(models.RECOGNIZER), "")

    def detect(self, frame: np.ndarray, score_threshold: Optional[float] = None) -> np.ndarray:
        """Return an (N, 15) float32 array in original-frame pixels:
        x, y, w, h, 5 x (landmark x, y) [right eye, left eye, nose, right mouth, left mouth], score."""
        h, w = frame.shape[:2]
        scale, img = 1.0, frame
        if max(h, w) > self.max_side:
            scale = self.max_side / float(max(h, w))
            img = cv2.resize(frame, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
        ih, iw = img.shape[:2]
        if (iw, ih) != self._size:
            self._det.setInputSize((iw, ih))
            self._size = (iw, ih)
        old_thresh = None
        if score_threshold is not None and hasattr(self._det, "getScoreThreshold") and hasattr(self._det, "setScoreThreshold"):
            old_thresh = float(self._det.getScoreThreshold())
            self._det.setScoreThreshold(float(score_threshold))
        try:
            _, faces = self._det.detect(img)
        finally:
            if old_thresh is not None:
                self._det.setScoreThreshold(old_thresh)
        if faces is None or len(faces) == 0:
            return np.zeros((0, 15), np.float32)
        faces = np.asarray(faces, np.float32).copy()
        if scale != 1.0:
            faces[:, :14] /= scale
        return faces

    def embed(self, frame: np.ndarray, face_row: np.ndarray) -> np.ndarray:
        """L2-normalised 128-d embedding for one detected face (row from detect())."""
        row = np.ascontiguousarray(face_row, dtype=np.float32).reshape(1, -1)      # OpenCV reads a 1 x 15 row
        aligned = self._rec.alignCrop(frame, row)
        vec = np.asarray(self._rec.feature(aligned), np.float32).reshape(-1)
        n = float(np.linalg.norm(vec))
        return vec / n if n > 0 else vec
