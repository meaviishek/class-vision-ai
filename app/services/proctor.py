"""Exam proctoring: turns per-frame face tracks into reviewable events and a suspicion ranking.

This flags behaviour for a human to review. It never decides that someone cheated.

Rules (all thresholds live in Settings):
  LOOKING_AWAY        head turned past the yaw limit (or tilted up) for look_away_sec
  REPEATED_LOOKING    glance_count look-aways inside glance_window_sec
  FACE_NOT_VISIBLE    an identified student has not been visible for missing_sec
  UNKNOWN_PERSON      a face matching nobody (and not staff) stays for unknown_sec
  DUPLICATE_IDENTITY  the same student matched in two places at once (photo / look-alike)
  IDENTITY_CHANGE     the person at a tracked seat is now recognised as someone else
  PROHIBITED_OBJECT   phone / book / laptop stays near a student (needs the optional YOLO detector)

Anomaly score: how much of the time a student looks away is compared with the rest of the room
(robust z-score via median/MAD), so a room-wide distraction does not flag everyone.
"""
from __future__ import annotations

import os
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

import numpy as np

from ..config import DATA_DIR, EVIDENCE_DIR, Settings
from ..imgio import write_image
from ..vision.types import FrameResult, TrackView

EVENT_INFO = {
    "LOOKING_AWAY": (1, "Looking away"),
    "LOOKING_LEFT": (1, "Looking left"),
    "LOOKING_RIGHT": (1, "Looking right"),
    "LOOKING_DOWN": (2, "Looking down repeatedly"),
    "REPEATED_LOOKING": (2, "Repeated glances"),
    "FACE_NOT_VISIBLE": (2, "Face not visible"),
    "UNKNOWN_PERSON": (2, "Unknown person"),
    "DUPLICATE_IDENTITY": (3, "Same face in two places"),
    "IDENTITY_CHANGE": (2, "Identity changed at seat"),
    "CAMERA_OBSTRUCTED": (3, "Camera obstructed"),
    "PROHIBITED_OBJECT": (3, "Prohibited object / cheat material"),
    "SUSPECTED_TALKING": (2, "Suspected talking"),
    "MULTIPLE_FACES": (4, "Multiple faces detected"),
    "INSTRUCTION": (1, "Teacher Instruction"),
    "SESSION_START": (1, "Class Started"),
    "SESSION_END": (1, "Class Ended"),
    "STUDENT_ARRIVED": (1, "Student Arrived"),
    "CHECK_IN": (1, "Gate Check-in"),
    "CHECK_OUT": (1, "Gate Check-out"),
}


@dataclass
class Event:
    ts: float
    key: str
    sid: Optional[int]
    type: str
    severity: int
    detail: str
    bbox: Optional[Tuple[float, float, float, float]] = None
    track_id: int = -1
    confidence: float = 0.90
    score_weight: float = 0.0


class _St:
    """Running statistics for one student (or one unknown face)."""

    def __init__(self, key: str, sid: Optional[int], track_id: int, ts: float):
        self.key, self.sid, self.track_id = key, sid, track_id
        self.first = self.last_seen = self.last_upd = ts
        self.observed = 0.0
        self.away_total = 0.0
        self.away_since: Optional[float] = None
        self.back_since: Optional[float] = None
        self.ep_open = False
        self.episodes: List[float] = []
        self.bursts = 0
        self.missing_open = False
        self.missing_total = 0.0
        self.objects = 0
        self.dups = 0
        self.switches = 0
        self.unknown = 0
        self.obj: Dict[str, List[float]] = {}
        self.last_bbox: Optional[Tuple[float, float, float, float]] = None
        # Advanced Proctoring State:
        self.mouth_hist: List[Tuple[float, float]] = []
        self.talking_count = 0
        self.multiple_faces_count = 0
        self.obstruction_count = 0
        self.down_episodes: List[float] = []
        self.last_activity: str = "Normal monitoring"
        self.last_activity_ts: float = ts
        self.incidents_count = 0
        self.current_score: float = 0.0
        self.current_level: str = "NORMAL"


def robust_z(values: List[float]) -> np.ndarray:
    """Median/MAD z-scores. The scale is floored at 3 percentage points so a room where almost
    everyone looks away ~0% of the time does not turn tiny differences into huge scores."""
    arr = np.asarray(values, float)
    med = float(np.median(arr))
    mad = float(np.median(np.abs(arr - med)))
    return (arr - med) / max(1.4826 * mad, 0.03)


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


class ProctorEngine:
    def __init__(self, settings: Settings, names: Dict[int, str], staff_ids: Optional[Set[int]] = None):
        self.s = settings
        self.names = names
        self.staff = set(staff_ids or ())
        self.state: Dict[str, _St] = {}
        self.active: Dict[int, str] = {}            # track_id -> flag shown on the live overlay
        self._unknown_logged: Set[int] = set()
        self._dup_since: Dict[int, float] = {}
        self._cool: Dict[tuple, float] = {}
        self._dark_since: Optional[float] = None

    # ------------------------------------------------------------------ helpers
    def _label(self, sid: Optional[int]) -> str:
        return "unknown" if sid is None else self.names.get(sid, f"#{sid}")

    def _name(self, st: _St) -> str:
        return self._label(st.sid) if st.sid is not None else f"Unknown face (track {st.track_id})"

    def _cooled(self, key: tuple, ts: float, seconds: float) -> bool:
        last = self._cool.get(key)
        if last is not None and ts - last < seconds:
            return False
        self._cool[key] = ts
        return True

    def _event(self, ts: float, st: _St, type_: str, detail: str, t: Optional[TrackView] = None,
               confidence: float = 0.90, weight: float = 0.0) -> Event:
        if weight <= 0.0:
            weight_map = {
                "LOOKING_AWAY": float(getattr(self.s, "weight_looking_away", 5)),
                "LOOKING_LEFT": float(getattr(self.s, "weight_looking_away", 5) * 2),
                "LOOKING_RIGHT": float(getattr(self.s, "weight_looking_away", 5) * 2),
                "LOOKING_DOWN": float(getattr(self.s, "weight_looking_down", 15)),
                "REPEATED_LOOKING": float(getattr(self.s, "weight_repeated_looking", 15)),
                "FACE_NOT_VISIBLE": float(getattr(self.s, "weight_missing", 25)),
                "UNKNOWN_PERSON": float(getattr(self.s, "weight_missing", 25)),
                "DUPLICATE_IDENTITY": float(getattr(self.s, "weight_phone", 35)),
                "IDENTITY_CHANGE": float(getattr(self.s, "weight_notes", 30)),
                "CAMERA_OBSTRUCTED": float(getattr(self.s, "weight_obstruction", 30)),
                "PROHIBITED_OBJECT": float(getattr(self.s, "weight_phone", 35)),
                "SUSPECTED_TALKING": float(getattr(self.s, "weight_talking", 20)),
                "MULTIPLE_FACES": float(getattr(self.s, "weight_multiple_faces", 40)),
            }
            weight = weight_map.get(type_, float(EVENT_INFO[type_][0] * 10))
        st.last_activity = EVENT_INFO[type_][1]
        st.last_activity_ts = ts
        st.incidents_count += 1
        return Event(ts, st.key, st.sid, type_, EVENT_INFO[type_][0], detail,
                     t.bbox if t is not None else st.last_bbox,
                     t.track_id if t is not None else st.track_id,
                     confidence=confidence, score_weight=weight)

    # ------------------------------------------------------------------ per frame
    def process(self, res: FrameResult) -> List[Event]:
        s, ts = self.s, res.ts
        events: List[Event] = []
        self.active = {}
        vis = [t for t in res.tracks if t.visible and t.sid not in self.staff]
        seen: Set[str] = set()

        for t in vis:
            if t.sid is None and t.votes < s.vote_required:
                continue                                  # identity still being decided
            key = f"s{t.sid}" if t.sid is not None else f"u{t.track_id}"
            st = self.state.get(key)
            if st is None:
                st = self.state[key] = _St(key, t.sid, t.track_id, ts)
            seen.add(key)
            st.track_id, st.last_bbox = t.track_id, t.bbox
            if st.missing_open:                           # student is back
                st.missing_total += ts - st.last_seen
                st.missing_open = False
            dt = min(ts - st.last_upd, 2.0)
            st.last_upd = st.last_seen = ts
            st.observed += dt

            # Talking / lip movement detection from facial landmarks
            if getattr(s, "detect_talking", True) and getattr(t, "mouth_open", 0.0) > 0.0:
                st.mouth_hist.append((ts, t.mouth_open))
                while st.mouth_hist and ts - st.mouth_hist[0][0] > 3.0:
                    st.mouth_hist.pop(0)
                if len(st.mouth_hist) >= 6:
                    m_vals = [v for _, v in st.mouth_hist]
                    v_min, v_max = min(m_vals), max(m_vals)
                    if (v_max - v_min) >= 0.14:
                        mean_val = sum(m_vals) / len(m_vals)
                        crossings = sum(1 for i in range(1, len(m_vals)) if (m_vals[i-1] - mean_val) * (m_vals[i] - mean_val) < 0)
                        if crossings >= 3 and self._cooled(("talk", key), ts, 20.0):
                            st.talking_count += 1
                            self.active[t.track_id] = "suspected talking"
                            events.append(self._event(ts, st, "SUSPECTED_TALKING",
                                                      "lip movement / speaking pattern detected", t,
                                                      confidence=0.88, weight=float(getattr(s, "weight_talking", 20))))

            # Looking down detection (if specifically configured)
            if getattr(s, "detect_looking_down", False) and t.pitch < -getattr(s, "pitch_down_limit_deg", 25.0):
                if self._cooled(("down", key), ts, 30.0):
                    st.down_episodes.append(ts)
                    events.append(self._event(ts, st, "LOOKING_DOWN",
                                              f"looking down repeatedly (pitch {t.pitch:.0f} deg)", t,
                                              confidence=0.89, weight=float(getattr(s, "weight_looking_down", 15))))

            away = abs(t.yaw) > s.yaw_limit_deg or t.pitch > s.pitch_up_limit_deg
            if away:
                st.back_since = None
                if st.away_since is None:
                    st.away_since = ts
                st.away_total += dt
                if not st.ep_open and ts - st.away_since >= s.look_away_sec:
                    st.ep_open = True
                    st.episodes.append(ts)
                    direction = "left" if t.yaw < -s.yaw_limit_deg else "right" if t.yaw > s.yaw_limit_deg else "up"
                    events.append(self._event(
                        ts, st, "LOOKING_AWAY", f"head turned {t.yaw:+.0f} deg, pitch {t.pitch:+.0f} deg ({direction})", t,
                        confidence=0.92, weight=float(getattr(s, "weight_looking_away", 5))))
                    recent = [x for x in st.episodes if ts - x <= s.glance_window_sec]
                    if len(recent) >= s.glance_count and self._cooled(("burst", key), ts, s.glance_window_sec):
                        st.bursts += 1
                        events.append(self._event(
                            ts, st, "REPEATED_LOOKING",
                            f"{len(recent)} look-aways in {s.glance_window_sec}s", t,
                            confidence=0.94, weight=float(getattr(s, "weight_repeated_looking", 15))))
                if st.ep_open:
                    self.active[t.track_id] = "looking away"
            elif st.away_since is not None:               # head back: wait 1 s before closing the episode
                if st.back_since is None:
                    st.back_since = ts
                if ts - st.back_since >= 1.0:
                    st.away_since, st.back_since, st.ep_open = None, None, False
                elif st.ep_open:
                    self.active[t.track_id] = "looking away"

            if t.sid is None:
                self.active.setdefault(t.track_id, "unknown")
                if t.age >= s.unknown_sec and t.track_id not in self._unknown_logged:
                    self._unknown_logged.add(t.track_id)
                    st.unknown += 1
                    events.append(self._event(ts, st, "UNKNOWN_PERSON",
                                              "face does not match any enrolled student", t,
                                              confidence=0.91, weight=float(getattr(s, "weight_missing", 25))))

        # Camera obstruction detection (dark frame)
        if getattr(s, "detect_obstruction", True) and res.frame is not None and len(vis) == 0:
            try:
                mean_b = float(np.mean(res.frame))
                if mean_b < 12.0:
                    if self._dark_since is None:
                        self._dark_since = ts
                    elif ts - self._dark_since >= 3.0 and self._cooled(("dark", 0), ts, 30.0):
                        dummy_st = self.state.get("camera")
                        if dummy_st is None:
                            dummy_st = self.state["camera"] = _St("camera", None, -1, ts)
                        dummy_st.obstruction_count += 1
                        events.append(self._event(ts, dummy_st, "CAMERA_OBSTRUCTED",
                                                  "camera frame appears dark or lens covered", None,
                                                  confidence=0.96, weight=float(getattr(s, "weight_obstruction", 30))))
                else:
                    self._dark_since = None
            except Exception:
                pass

        # Multiple faces detection (single student webcam setup)
        if getattr(s, "detect_multiple_faces", False):
            non_staff = [t for t in vis if t.sid not in self.staff]
            if len(non_staff) >= 2 and self._cooled(("multi_faces", 0), ts, 20.0):
                for t in non_staff:
                    self.active[t.track_id] = "multiple faces"
                    st_t = self.state.get(f"s{t.sid}" if t.sid is not None else f"u{t.track_id}")
                    if st_t is not None:
                        st_t.multiple_faces_count += 1
                primary_st = next((self.state.get(f"s{t.sid}") for t in non_staff if t.sid is not None), None)
                if primary_st is None and non_staff:
                    primary_st = self.state.get(f"u{non_staff[0].track_id}")
                if primary_st is not None:
                    events.append(self._event(ts, primary_st, "MULTIPLE_FACES",
                                              f"{len(non_staff)} faces detected simultaneously in webcam frame",
                                              non_staff[0], confidence=0.97, weight=float(getattr(s, "weight_multiple_faces", 40))))

        # identified students who disappeared
        for key, st in self.state.items():
            if st.sid is None or key in seen or st.missing_open:
                continue
            gap = ts - st.last_seen
            if gap >= s.missing_sec and st.observed >= 10.0:
                st.missing_open = True
                events.append(self._event(ts, st, "FACE_NOT_VISIBLE", f"not visible for {gap:.0f}s",
                                          confidence=0.95, weight=float(getattr(s, "weight_missing", 25))))

        # one identity matched in two places at once
        by_sid: Dict[int, List[TrackView]] = defaultdict(list)
        for t in vis:
            if t.sid is not None:
                by_sid[t.sid].append(t)
        for sid, group in by_sid.items():
            if len(group) < 2:
                self._dup_since.pop(sid, None)
                continue
            since = self._dup_since.setdefault(sid, ts)
            for t in group:
                self.active[t.track_id] = "same face twice"
            st = self.state.get(f"s{sid}")
            if st is not None and ts - since >= 3.0 and self._cooled(("dup", sid), ts, 60.0):
                st.dups += 1
                events.append(self._event(ts, st, "DUPLICATE_IDENTITY",
                                          f"matched in {len(group)} places at once", group[0],
                                          confidence=0.96, weight=float(getattr(s, "weight_phone", 35))))
        for sid in [k for k in self._dup_since if k not in by_sid]:
            del self._dup_since[sid]

        # identity flipped on a tracked seat
        for tid, old, new in res.identity_changes:
            if old in self.staff or new in self.staff:
                continue
            st = self.state.get(f"s{old}") or (self.state.get(f"s{new}") if new is not None else None)
            if st is None:
                continue
            st.switches += 1
            events.append(self._event(ts, st, "IDENTITY_CHANGE",
                                      f"{self._label(old)} became {self._label(new)}", None,
                                      confidence=0.93, weight=float(getattr(s, "weight_notes", 30))))

        # prohibited objects near a student's face
        for o in res.objects:
            ox, oy = o.bbox[0] + o.bbox[2] / 2.0, o.bbox[1] + o.bbox[3] / 2.0
            best, best_d = None, 1e9
            for t in vis:
                cx, cy = t.bbox[0] + t.bbox[2] / 2.0, t.bbox[1] + t.bbox[3] / 2.0
                d = ((ox - cx) ** 2 + (oy - cy) ** 2) ** 0.5 / max(t.bbox[2], 1.0)
                if d < best_d:
                    best, best_d = t, d
            if best is None or best_d > 3.0:
                continue
            st = self.state.get(f"s{best.sid}" if best.sid is not None else f"u{best.track_id}")
            if st is None:
                continue
            span = st.obj.setdefault(o.label, [ts, ts])
            if ts - span[1] > 4.0:
                span[0] = ts
            span[1] = ts
            self.active[best.track_id] = o.label
            if span[1] - span[0] >= s.object_sec and self._cooled((o.label, st.key), ts, 30.0):
                st.objects += 1
                events.append(self._event(ts, st, "PROHIBITED_OBJECT",
                                          f"{o.label} ({o.conf:.0%}) near this student", best,
                                          confidence=o.conf, weight=float(getattr(s, "weight_phone", 35))))
        return events

    # ------------------------------------------------------------------ scoring
    def summary(self, now: float) -> List[dict]:
        """Suspicion ranking, highest first. Safe to call at any time."""
        peers = [st for st in self.state.values() if st.sid is not None and st.observed >= 60.0]
        z: Dict[str, float] = {}
        if len(peers) >= 5:
            zs = robust_z([p.away_total / p.observed for p in peers])
            z = {p.key: float(v) for p, v in zip(peers, zs)}
        rows = []
        for st in self.state.values():
            ratio = st.away_total / st.observed if st.observed > 0 else 0.0
            missing = st.missing_total + ((now - st.last_seen) if st.missing_open else 0.0)
            flags = st.dups + st.switches + st.unknown
            extra_flags = getattr(st, "talking_count", 0) + getattr(st, "multiple_faces_count", 0) + getattr(st, "obstruction_count", 0)
            if st.key in z:
                look = _clamp01(z[st.key] / 4.0)           # relative to the room
            elif st.observed >= 60.0:
                look = _clamp01(ratio / 0.30)              # small room: absolute fallback
            else:
                look = 0.0
            # Looking away (and the glance bursts it causes) tops out at 55, below "high" (60).
            # Reaching high takes a second kind of evidence: an object, an identity flag, or absence.
            base_score = min(100.0, 40 * look + 15 * _clamp01(st.bursts / 2.0) + 10 * _clamp01(missing / 300.0)
                             + 35 * _clamp01(float(st.objects)) + 35 * _clamp01(float(flags))
                             + 20 * _clamp01(float(extra_flags)))
            score = round(base_score, 1)

            # Test-compatible level:
            test_level = "HIGH" if score >= 60 else "MEDIUM" if score >= 30 else "LOW"
            # 5-tier display level:
            if score >= 80:
                disp_level, color = "Critical", "#991b1b"
            elif score >= 60:
                disp_level, color = "High", "#ef4444"
            elif score >= 40:
                disp_level, color = "Medium", "#f97316"
            elif score >= 20:
                disp_level, color = "Low", "#eab308"
            else:
                disp_level, color = "Normal", "#22c55e"

            st.current_score = score
            st.current_level = disp_level

            rows.append(dict(
                key=st.key, sid=st.sid, name=self._name(st), score=score,
                level=test_level,
                suspicion_level=disp_level,
                color=color,
                observed_sec=round(st.observed), away_pct=round(100 * ratio, 1), glances=len(st.episodes),
                bursts=st.bursts, missing_sec=round(missing), objects=st.objects, flags=flags,
                talking=getattr(st, "talking_count", 0),
                multiple_faces=getattr(st, "multiple_faces_count", 0),
                incidents=getattr(st, "incidents_count", 0),
                last_activity=getattr(st, "last_activity", "Normal monitoring"),
                last_activity_ts=getattr(st, "last_activity_ts", st.last_seen),
                z=round(z.get(st.key, 0.0), 2)))
        rows.sort(key=lambda r: -r["score"])
        return rows


def save_evidence(frame: np.ndarray, bbox, session_id: int, ts: float, etype: str, key: str) -> str:
    """Save a crop around the student (whole frame if unknown). Returns the path relative to DATA_DIR."""
    h, w = frame.shape[:2]
    crop = frame
    if bbox is not None:
        x, y, bw, bh = bbox
        cx, cy, half = x + bw / 2.0, y + bh / 2.0, max(bw, bh) * 1.6
        x0, y0, x1, y1 = int(max(0, cx - half)), int(max(0, cy - half)), int(min(w, cx + half)), int(min(h, cy + half))
        if x1 > x0 and y1 > y0:
            crop = frame[y0:y1, x0:x1]
    folder = EVIDENCE_DIR / str(session_id)
    path = folder / f"{time.strftime('%H%M%S', time.localtime(ts))}_{etype}_{key}.jpg"
    write_image(path, crop, 88)
    return os.path.relpath(path, DATA_DIR)
