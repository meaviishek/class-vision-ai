"""Optional prohibited-object detection. Needs `pip install ultralytics`; the weights (about 6 MB) are
downloaded into the models/ folder the first time it is used."""
from __future__ import annotations

from typing import List

from ..config import MODELS_DIR
from .types import ObjectDet

DEFAULT_WEIGHTS = MODELS_DIR / "yolov8n.pt"


class ObjectDetector:
    # COCO class ids: 63 laptop, 67 cell phone, 73 book
    LABELS = {63: "laptop", 67: "cell phone", 73: "book"}

    def __init__(self, conf: float = 0.45, weights: str = "", imgsz: int = 960):
        try:
            from ultralytics import YOLO
        except ImportError as exc:  # pragma: no cover - depends on the user's environment
            raise RuntimeError("Object detection needs the 'ultralytics' package: pip install ultralytics") from exc
        # A full path, so the download lands in models/ and not in whatever folder the app was started from.
        self.model = YOLO(weights or str(DEFAULT_WEIGHTS))
        self.conf, self.imgsz = conf, imgsz

    def detect(self, frame) -> List[ObjectDet]:
        res = self.model.predict(frame, conf=self.conf, imgsz=self.imgsz,
                                 classes=list(self.LABELS), verbose=False)[0]
        out: List[ObjectDet] = []
        for b in res.boxes:
            x1, y1, x2, y2 = (float(v) for v in b.xyxy[0].tolist())
            out.append(ObjectDet(self.LABELS.get(int(b.cls[0]), "object"), float(b.conf[0]),
                                 (x1, y1, x2 - x1, y2 - y1)))
        return out
