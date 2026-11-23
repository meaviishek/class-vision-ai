"""detect -> track -> recognise -> pose. Runs inside a worker thread; produces FrameResult objects."""
from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

import numpy as np

from ..config import Settings
from ..utils import VIDEO_IDLE, VIDEO_OK, VIDEO_WARN
from .gallery import Gallery
from .pose import head_pose
from .tracker import Det, IdentityTracker
from .types import FrameResult, Overlay

log = logging.getLogger(__name__)


class VisionPipeline:
    MIN_DET_PX = 20             # ignore detections smaller than this (still tracked above this)
    MAX_EMBEDS = 16             # recognition budget per processed frame
    UNKNOWN_RECHECK_SEC = 2.0   # unrecognised faces get another look this often
    CLOSEUP_RECHECK_SEC = 1.0   # close-up (gate) faces are re-checked quickly so hand-overs are caught
    CLOSEUP_RESET_SEC = 1.5     # a close-up face that vanishes for this long and returns is treated as new

    def __init__(self, engine, gallery: Gallery, settings: Settings, objects=None, fps: float = 2.0):
        self.engine, self.gallery, self.s, self.objects = engine, gallery, settings, objects
        self.tracker = IdentityTracker(settings.track_max_age_sec, vote_window=settings.vote_window,
                                       liveness_deg=settings.gate_liveness_yaw_deg)
        self._last_obj = 0.0
        # A close-up face counts as "someone new" after being gone this long. It is never shorter than
        # three frames, so a slow analysis rate cannot wipe every close-up identity between two frames.
        self.reset_gap = max(self.CLOSEUP_RESET_SEC, 3.0 / max(float(fps), 0.1))

    def _can_vote(self, t) -> bool:
        """Only large, roughly frontal faces produce reliable embeddings."""
        return (t.bbox[2] >= self.s.min_face_px and t.det_score >= 0.7
                and abs(t.yaw) <= 30 and abs(t.pitch) <= 35)

    def process(self, frame: np.ndarray, ts: float) -> FrameResult:
        h, w = frame.shape[:2]
        dets: List[Det] = []
        for r in self.engine.detect(frame):
            if r[2] < self.MIN_DET_PX:
                continue
            dets.append(Det((float(r[0]), float(r[1]), float(r[2]), float(r[3])),
                            r[4:14].reshape(5, 2).copy(), float(r[14]), r.copy()))
        tracks = self.tracker.update(dets, ts)

        due = []
        for t in tracks:
            if not t.matched:
                continue
            closeup = t.bbox[2] / w >= self.s.gate_min_face_ratio
            if closeup and ts - t.prev_seen > self.reset_gap:
                t.reset_identity(ts)               # next student stepping up to the gate must not inherit a name
            t.set_pose(head_pose(t.lm, w, h), ts)
            if not self._can_vote(t):
                continue
            undecided = t.sid is None and t.n_votes < self.s.vote_required
            if closeup:
                interval = self.CLOSEUP_RECHECK_SEC
            else:
                interval = self.s.reverify_sec if t.sid is not None else self.UNKNOWN_RECHECK_SEC
            if undecided or ts - t.last_embed >= interval:
                due.append(t)
        due.sort(key=lambda t: t.last_embed)

        changes: List[Tuple[int, Optional[int], Optional[int]]] = []
        for t in due[: self.MAX_EMBEDS]:
            emb = self.engine.embed(frame, t.row)
            sid, score = self.gallery.identify(emb, self.s.recog_threshold, self.s.recog_margin)
            t.last_embed = ts
            t.add_vote(sid, score)
            change = t.resolve(self.s.vote_required)
            if change is not None and change[0] is not None and change[1] is not None:
                changes.append((t.id, change[0], change[1]))      # a real swap; a lost name is not one

        objs, notes = [], []
        if self.objects is not None and ts - self._last_obj >= 1.0:
            self._last_obj = ts
            try:
                objs = self.objects.detect(frame)
            except Exception as exc:  # keep the session alive if the optional detector breaks
                log.exception("Object detection failed; turning it off for this session")
                self.objects = None
                notes.append(f"Phone, book and laptop detection stopped: {exc}")
        return FrameResult(ts, w, h, [t.view(w) for t in tracks], objs, changes, frame, notes)


class SessionProcessor:
    """Adapter for CameraWorker: runs the pipeline and builds the boxes shown on the preview."""

    def __init__(self, pipeline: VisionPipeline, mode: str, names: Dict[int, str], settings: Settings):
        self.pipeline, self.mode, self.names, self.s = pipeline, mode, names, settings

    def process(self, frame: np.ndarray, ts: float):
        res = self.pipeline.process(frame, ts)
        return res, self._overlays(res)

    def _overlays(self, res: FrameResult) -> List[Overlay]:
        vis = [t for t in res.tracks if t.visible]
        main = max(vis, key=lambda t: t.bbox[2]) if (self.mode == "gate" and vis) else None
        out: List[Overlay] = []
        for t in vis:
            x, y, bw, bh = t.bbox
            box = dict(x=x / res.width, y=y / res.height, w=bw / res.width, h=bh / res.height, tid=t.track_id)
            if self.mode == "gate" and t is not main:
                out.append(Overlay(color=VIDEO_IDLE, **box))
            elif t.sid is not None:
                out.append(Overlay(label=self.names.get(t.sid, f"#{t.sid}"), color=VIDEO_OK, **box))
            elif t.votes >= self.s.vote_required and t.age >= 6.0:
                out.append(Overlay(label="Unknown", color=VIDEO_WARN, **box))
            else:
                out.append(Overlay(color=VIDEO_IDLE, **box))
        return out
