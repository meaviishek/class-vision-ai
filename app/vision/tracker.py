"""Face tracking across frames. Identity is decided by voting, not by a single match."""
from __future__ import annotations

import math
from collections import Counter, deque
from dataclasses import dataclass
from typing import Deque, Dict, List, Optional, Tuple

import numpy as np

from .types import TrackView


@dataclass
class Det:
    bbox: Tuple[float, float, float, float]   # x, y, w, h in px
    lm: np.ndarray                            # (5, 2)
    score: float
    row: np.ndarray                           # raw detector row (15,), needed for alignment


def iou(a, b) -> float:
    iw = min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0])
    ih = min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1])
    if iw <= 0 or ih <= 0:
        return 0.0
    inter = iw * ih
    return inter / (a[2] * a[3] + b[2] * b[3] - inter)


class Track:
    def __init__(self, tid: int, det: Det, ts: float, window: int, liveness_deg: float):
        self.id = tid
        self.created = ts
        self.votes: Deque[Tuple[Optional[int], float]] = deque(maxlen=window)
        self.n_votes = 0
        self.sid: Optional[int] = None
        self.sid_score = 0.0
        self.last_embed = 0.0
        self.yaw = self.pitch = self.roll = 0.0
        self._pose_ready = False
        self._yaw_hist: Deque[Tuple[float, float]] = deque()
        self.live_ok = False
        self._live_deg = liveness_deg
        self.matched = True
        self.prev_seen = ts
        self.apply(det, ts)

    def apply(self, det: Det, ts: float) -> None:
        self.bbox, self.lm, self.det_score, self.row = det.bbox, det.lm, det.score, det.row
        self.prev_seen = getattr(self, "last_seen", ts)       # when it was detected before this frame
        self.last_seen = ts
        self.matched = True

    def reset_identity(self, ts: float) -> None:
        """Forget who this was. Used when a close-up face reappears after a gap: probably someone new."""
        self.votes.clear()
        self.n_votes, self.sid, self.sid_score, self.last_embed = 0, None, 0.0, 0.0
        self.live_ok = False
        self._yaw_hist.clear()
        self.created = ts

    # -- pose -------------------------------------------------------------
    def set_pose(self, pose: Optional[Tuple[float, float, float]], ts: float) -> None:
        if pose is None:
            return
        if not self._pose_ready:
            self.yaw, self.pitch, self.roll = pose
            self._pose_ready = True
        else:                                     # light smoothing against landmark jitter
            a = 0.5
            self.yaw += a * (pose[0] - self.yaw)
            self.pitch += a * (pose[1] - self.pitch)
            self.roll += a * (pose[2] - self.roll)
        self._yaw_hist.append((ts, self.yaw))
        while self._yaw_hist and ts - self._yaw_hist[0][0] > 6.0:
            self._yaw_hist.popleft()
        if not self.live_ok and len(self._yaw_hist) >= 3:
            ys = [v for _, v in self._yaw_hist]
            if max(ys) - min(ys) >= self._live_deg:
                self.live_ok = True

    # -- identity ---------------------------------------------------------
    def add_vote(self, sid: Optional[int], score: float) -> None:
        self.votes.append((sid, score))
        self.n_votes += 1

    def _mean_score(self, sid: int) -> float:
        scores = [sc for v, sc in self.votes if v == sid]
        return sum(scores) / len(scores) if scores else 0.0

    def resolve(self, required: int) -> Optional[Tuple[Optional[int], Optional[int]]]:
        """Decide who this track is from the recent votes. Returns (old, new) when that changed, else None.

        * A student is adopted when `required` of the recent votes name them and nobody else has as many.
        * Once adopted, the name only moves to someone else if that challenger has `required` votes AND more
          votes than the current student. A couple of stray votes never hand a name over.
        * Two students level on votes is not a decision: the current student keeps the name, and if there is
          none yet the track waits for more evidence.
        * A vote for "nobody" (blur, a face that is not in the gallery) never takes a name away by itself.
          The name is dropped only when a whole window of votes found nobody.
        """
        if not self.votes:
            return None
        counts = Counter(v for v, _ in self.votes if v is not None)
        current = self.sid
        if not counts:
            if current is not None and len(self.votes) >= (self.votes.maxlen or 1):
                self.sid, self.sid_score = None, 0.0
                return current, None
            return None
        if current is not None and current in counts:
            self.sid_score = self._mean_score(current)          # keep the confidence up to date
        top = max(counts.values())
        leaders = [v for v, n in counts.items() if n == top]
        if current in leaders:
            return None                                          # the current student is (jointly) ahead
        if len(leaders) > 1 or top < required:
            return None                                          # a tie between two others, or too few votes
        best = leaders[0]
        self.sid, self.sid_score = best, self._mean_score(best)
        return current, best

    @property
    def mouth_open(self) -> float:
        if not hasattr(self, "lm") or self.lm is None or len(self.lm) < 5:
            return 0.0
        try:
            r_eye, l_eye = self.lm[0], self.lm[1]
            nose = self.lm[2]
            r_mou, l_mou = self.lm[3], self.lm[4]
            ipd = float(np.linalg.norm(r_eye - l_eye))
            if ipd < 1.0:
                return 0.0
            m_center = (r_mou + l_mou) / 2.0
            nose_to_m = float(np.linalg.norm(nose - m_center))
            return nose_to_m / ipd
        except Exception:
            return 0.0

    def view(self, frame_w: int) -> TrackView:
        return TrackView(self.id, tuple(float(v) for v in self.bbox), self.sid, self.sid_score,
                         self.matched, self.bbox[2] / float(frame_w), self.yaw, self.pitch, self.roll,
                         self.last_seen - self.created, self.n_votes, self.live_ok, self.last_seen,
                         mouth_open=self.mouth_open)


class IdentityTracker:
    def __init__(self, max_age: float = 8.0, iou_thr: float = 0.2, vote_window: int = 5,
                 liveness_deg: float = 20.0):
        self.max_age, self.iou_thr = max_age, iou_thr
        self.vote_window, self.liveness_deg = vote_window, liveness_deg
        self.tracks: Dict[int, Track] = {}
        self._next = 1

    def update(self, dets: List[Det], ts: float) -> List[Track]:
        for t in self.tracks.values():
            t.matched = False
        cand = []
        for t in self.tracks.values():
            tcx, tcy = t.bbox[0] + t.bbox[2] / 2, t.bbox[1] + t.bbox[3] / 2
            for j, d in enumerate(dets):
                ov = iou(t.bbox, d.bbox)
                dist = math.hypot(tcx - (d.bbox[0] + d.bbox[2] / 2),
                                  tcy - (d.bbox[1] + d.bbox[3] / 2)) / max(t.bbox[2], d.bbox[2], 1.0)
                if ov >= self.iou_thr or dist <= 0.6:
                    cand.append(((1.0 - ov) + 0.5 * dist, t.id, j))
        cand.sort()
        used_t, used_d = set(), set()
        for _, tid, j in cand:
            if tid in used_t or j in used_d:
                continue
            used_t.add(tid)
            used_d.add(j)
            self.tracks[tid].apply(dets[j], ts)
        for j, d in enumerate(dets):
            if j not in used_d:
                self.tracks[self._next] = Track(self._next, d, ts, self.vote_window, self.liveness_deg)
                self._next += 1
        for tid in [i for i, t in self.tracks.items() if ts - t.last_seen > self.max_age]:
            del self.tracks[tid]
        return list(self.tracks.values())
