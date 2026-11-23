"""SessionController: runs one class or exam session on behalf of the UI.

Cameras run in worker threads and only emit signals. Everything that touches the rules engines or
the database happens here, in the main thread, so no locking is needed.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, replace
from typing import Dict, List, Optional

from PySide6.QtCore import QObject, QTimer, Signal, Slot
from PySide6.QtGui import QImage

from ..services.attendance import AttendanceEngine
from ..services.proctor import EVENT_INFO, Event, ProctorEngine, save_evidence
from ..utils import VIDEO_BAD
from ..vision.engine import FaceEngine
from ..vision.gallery import Gallery
from ..vision.objects import ObjectDetector
from ..vision.pipeline import SessionProcessor, VisionPipeline
from .camera import CameraWorker, parse_source, webcam_index

log = logging.getLogger(__name__)


@dataclass
class SessionConfig:
    kind: str                  # "class" | "exam"
    title: str
    section: str               # "" = everyone
    start_ts: float
    duration_min: int
    min_presence_min: int
    class_source: str
    gate_source: str           # "same" | "none" | a camera source of its own
    objects: bool = False      # exam only: detect phones / books / laptops


class _Relay(QObject):
    """Lives in the main thread; receives one camera's signals and tags them with its role."""

    def __init__(self, ctrl: "SessionController", role: str):
        super().__init__(ctrl)
        self.ctrl, self.role = ctrl, role

    @Slot(object)
    def on_result(self, payload):
        self.ctrl._on_result(self.role, payload)

    @Slot(object)
    def on_overlays(self, overlays):
        self.ctrl._on_overlays(self.role, overlays)

    @Slot(QImage)
    def on_frame(self, img):
        self.ctrl.frame.emit(self.role, img)

    @Slot(str)
    def on_status(self, text):
        self.ctrl.status.emit(self.role, text)


class SessionController(QObject):
    frame = Signal(str, QImage)        # role ("class" | "gate"), preview image
    overlays = Signal(str, object)     # role, list of Overlay
    attendance = Signal(object)        # list of row dicts for the live table
    gate_msg = Signal(str, str)        # kind ("ok" | "info" | "warn" | "bad"), text
    alert = Signal(object)             # dict describing a proctoring event
    risk = Signal(object)              # suspicion ranking (list of dicts)
    tick = Signal(object)              # dict with timing / phase info once a second
    status = Signal(str, str)          # role, camera status text
    finished = Signal(int)             # session id

    def __init__(self, ctx, kind: str, parent=None):
        super().__init__(parent)
        self.ctx, self.kind = ctx, kind
        self.running = False
        self.session_id: Optional[int] = None
        self.att: Optional[AttendanceEngine] = None
        self.proctor: Optional[ProctorEngine] = None
        self.names: Dict[int, str] = {}
        self.notices: List[str] = []       # things to tell the user once the session has started
        self._same_gate = False
        self._gate_off = False
        self._devices: List[int] = []      # webcam numbers this session holds open
        self._workers: Dict[str, CameraWorker] = {}
        self._relays: Dict[str, _Relay] = {}
        self._ticks = 0
        self._seen_sids: set = set()
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._on_tick)

    # --------------------------------------------------------------- logging
    def log_instruction(self, text: str, type_: str = "INSTRUCTION", sid: Optional[int] = None, severity: int = 1) -> None:
        if not self.running or not self.session_id:
            return
        now = time.time()
        self.ctx.db.add_event(self.session_id, sid, now, type_, severity, text, "")
        who = self.names.get(sid) if sid is not None else "Instructor / System"
        label = EVENT_INFO.get(type_, (1, type_.replace("_", " ").title()))[1]
        self.alert.emit(dict(ts=now, type=type_, label=label, severity=severity,
                             name=who, detail=text, snapshot=""))

    # --------------------------------------------------------------- lifecycle
    def start(self, cfg: SessionConfig) -> int:
        """Start cameras and rules. Raises ValueError / FileNotFoundError with a message for the user."""
        if self.running:
            raise RuntimeError("A session is already running.")
        s, db = self.ctx.settings, self.ctx.db
        roster_rows = db.list_students(section=cfg.section or None, role="student")
        if not roster_rows:
            raise ValueError("No students are enrolled for this selection. Enroll students first.")
        staff_rows = db.list_students(role="staff")
        roster = {r["id"]: {"name": r["name"], "reg_no": r["reg_no"]} for r in roster_rows}
        gallery = Gallery.from_db(db, set(roster) | {r["id"] for r in staff_rows})
        if len(gallery) == 0:
            raise ValueError("None of the selected students have face samples yet.")
        names = {r["id"]: r["name"] for r in (*roster_rows, *staff_rows)}

        gate_src = (cfg.gate_source or "none").strip()
        gate_off = gate_src.lower() in ("none", "")
        same_gate = gate_src.lower() == "same"
        specs = [("class", cfg.class_source, "both" if same_gate else "class", s.class_process_fps)]
        if not gate_off and not same_gate:
            specs.append(("gate", gate_src, "gate", s.gate_process_fps))
        devices = self._check_cameras([src for _, src, _, _ in specs])

        # With no gate camera nobody can check in or out, so those checks cannot be required: without this
        # every student would end up as "needs review". (A copy: the saved settings are not touched.)
        att_settings = replace(s, require_checkin=False, require_checkout=False) if gate_off else s
        att = AttendanceEngine(att_settings, cfg.start_ts, cfg.duration_min, cfg.min_presence_min, roster)
        proctor = ProctorEngine(s, names, {r["id"] for r in staff_rows}) if cfg.kind == "exam" else None

        engines = {role: FaceEngine(s.det_score_threshold) for role, *_ in specs}   # fails first if models are missing
        self.notices = []
        detector = None
        if cfg.kind == "exam" and cfg.objects:
            try:
                detector = ObjectDetector(conf=s.object_conf)
            except Exception as exc:                       # optional feature: carry on without it
                log.warning("Object detection unavailable: %s", exc)
                self.notices.append(f"Phone, book and laptop detection is off: {exc}\n"
                                    f"The exam is monitored without it.")
        workers: Dict[str, CameraWorker] = {}
        for role, src, mode, fps in specs:
            pipeline = VisionPipeline(engines[role], gallery, s,
                                      objects=detector if role == "class" else None, fps=fps)
            processor = SessionProcessor(pipeline, mode, names, s)
            workers[role] = CameraWorker(parse_source(src), processor, fps, s.capture_width,
                                         s.capture_height, parent=self)

        self.session_id = db.create_session(
            cfg.kind, cfg.title, cfg.section or None, cfg.start_ts, cfg.duration_min, cfg.min_presence_min,
            {"class_source": cfg.class_source, "gate_source": cfg.gate_source, "objects": cfg.objects})
        self.att, self.proctor, self.names = att, proctor, names
        self._same_gate, self._gate_off = same_gate, gate_off
        self._devices = devices
        self.ctx.live_sources.update(devices)
        self._workers, self._relays = workers, {}
        for role, w in workers.items():
            relay = _Relay(self, role)
            self._relays[role] = relay
            w.result.connect(relay.on_result)
            w.overlays.connect(relay.on_overlays)
            w.frame.connect(relay.on_frame)
            w.status.connect(relay.on_status)
        self.running, self._ticks = True, 0
        self._seen_sids = set()
        for w in workers.values():
            w.start()
        self._timer.start()
        self._on_tick()
        if self.kind == "class":
            self.log_instruction(f"Class session started: {cfg.title} (Section: {cfg.section or 'All'})", type_="SESSION_START")
        self.ctx.sessions_changed.emit()
        return self.session_id

    def _check_cameras(self, sources) -> List[int]:
        """Webcam numbers this session is about to open. Refuses one that is already in use."""
        devices = [d for d in (webcam_index(src) for src in sources) if d is not None]
        if len(set(devices)) != len(devices):
            raise ValueError("The classroom camera and the gate camera are the same webcam. "
                             "Set the gate camera to 'same', or choose two different cameras.")
        for d in devices:
            if d in self.ctx.live_sources:
                raise ValueError(f"Webcam {d} is already in use by another session. "
                                 f"Stop that session first, or choose a different camera.")
        return devices

    def stop(self) -> None:
        """Stop cameras, freeze results at this moment, save everything."""
        if not self.running:
            return
        self.running = False
        self._timer.stop()
        workers = list(self._workers.values())
        for w in workers:
            w.request_stop()                              # let every camera wind down at the same time...
        for w in workers:
            w.stop()                                      # ...then wait for each one
            if not w.isRunning():
                w.deleteLater()                           # do not pile up one dead thread object per session
        self.ctx.live_sources.difference_update(self._devices)
        self._devices = []
        now = time.time()
        if self.kind == "class":
            self.log_instruction("Class capture stopped. Final attendance and logs saved in SQLite.", type_="SESSION_END")
        self.att.finalize(now)
        self._checkpoint(now)
        if self.proctor is not None:
            self.ctx.db.save_risk(self.session_id, self.proctor.summary(min(now, self.att.E)))
        self.ctx.db.finish_session(self.session_id, now)
        self.attendance.emit(self.att.snapshot(now))
        self._workers, self._relays = {}, {}
        self.ctx.sessions_changed.emit()
        self.finished.emit(self.session_id)

    # ------------------------------------------------------------ camera input
    def _on_result(self, role: str, res) -> None:
        if not self.running:
            return
        for note in res.notes:                              # e.g. the object detector switched itself off
            self.status.emit(role, note)
        if role == "class":
            for sid in {t.sid for t in res.tracks if t.visible and t.sid is not None}:
                first_time = sid not in self._seen_sids
                self.att.class_sight(sid, res.ts)
                if first_time:
                    self._seen_sids.add(sid)
                    if self.kind == "class":
                        st_name = self.names.get(sid, f"Student #{sid}")
                        self.log_instruction(f"{st_name} detected and present in classroom", type_="STUDENT_ARRIVED", sid=sid)
            if self.proctor is not None:
                if self.att.S <= res.ts <= self.att.E:      # only the exam itself is watched, not the
                    for ev in self.proctor.process(res):    # settling in before it or the leaving after it
                        self._record_event(ev, res)
                else:
                    self.proctor.active = {}                # no stale red boxes on the preview
        if role == "gate" or (role == "class" and self._same_gate):
            self._gate(res, dedicated=(role == "gate"))

    def _on_overlays(self, role: str, overlays: list) -> None:
        if self.proctor is not None and role == "class" and self.proctor.active:
            flagged = self.proctor.active
            overlays = [replace(o, color=VIDEO_BAD, sub=flagged[o.tid]) if o.tid in flagged else o
                        for o in overlays]
        self.overlays.emit(role, overlays)

    def _gate(self, res, dedicated: bool) -> None:
        s = self.ctx.settings
        mode = self.att.gate_window(res.ts)
        if not dedicated and mode is None:
            return                                          # shared camera: stay quiet while the gate is closed
        visible = [t for t in res.tracks if t.visible]
        if not visible:
            if dedicated:
                self.gate_msg.emit("info", "Waiting for a student to step up to the camera")
            return
        t = max(visible, key=lambda v: v.bbox[2])
        if t.face_ratio < s.gate_min_face_ratio:
            if dedicated:
                self.gate_msg.emit("info", "Step closer to the camera")
            return
        if mode is None:
            self.gate_msg.emit("warn", f"Gate closed: {self.att.gate_hint(res.ts)}")
            return
        if t.sid is None:
            if t.votes >= s.vote_required:
                self.gate_msg.emit("bad", "Face not recognised. Ask your teacher to check your enrollment.")
            else:
                self.gate_msg.emit("info", "Hold still, recognising...")
            return
        if s.gate_liveness and not t.live_ok:
            self.gate_msg.emit("info", "Slowly turn your head left, then right")
            return
        result = self.att.gate(t.sid, res.ts)
        if result.kind == "unknown":
            self.gate_msg.emit("bad", f"{self.names.get(t.sid, 'This person')} is not on this class roster")
            return
        self.gate_msg.emit("ok" if result.accepted else "info", result.message)
        if result.accepted:
            self._checkpoint(res.ts)
            if self.kind == "class":
                event_type = "CHECK_IN" if "check-in" in result.message.lower() else "CHECK_OUT"
                st_name = self.names.get(t.sid, f"Student #{t.sid}")
                self.log_instruction(f"{st_name}: {result.message}", type_=event_type, sid=t.sid)

    def _record_event(self, ev: Event, res) -> None:
        snapshot = ""
        if self.ctx.settings.save_evidence and res.frame is not None:
            try:
                snapshot = save_evidence(res.frame, ev.bbox, self.session_id, ev.ts, ev.type, ev.key)
            except Exception:
                log.exception("Could not save the evidence image")
        conf = getattr(ev, "confidence", 0.90)
        weight = getattr(ev, "score_weight", float(ev.severity * 10))
        eid = self.ctx.db.add_event(self.session_id, ev.sid, ev.ts, ev.type, ev.severity, ev.detail, snapshot,
                                    confidence=conf, score_weight=weight, review_status="Pending Review")
        who = self.names.get(ev.sid) if ev.sid is not None else f"Unknown face (track {ev.track_id})"
        self.alert.emit(dict(id=eid, ts=ev.ts, type=ev.type, label=EVENT_INFO.get(ev.type, (1, ev.type))[1],
                             severity=ev.severity, name=who or f"#{ev.sid}", detail=ev.detail,
                             snapshot=snapshot, confidence=conf, score_weight=weight,
                             review_status="Pending Review", admin_remarks=""))

    # ------------------------------------------------------------------ timing
    def _checkpoint(self, now: float) -> None:
        self.ctx.db.save_attendance(self.session_id, self.att.attendance_rows(now), self.att.interval_map())

    def _on_tick(self) -> None:
        if not self.running:
            return
        now = time.time()
        self._ticks += 1
        info = self.att.timing(now)
        if self._gate_off:
            info["gate"] = "Gate off"
        self.tick.emit(info)
        self.attendance.emit(self.att.snapshot(now))
        if self.proctor is not None and self._ticks % 3 == 0:
            self.risk.emit(self.proctor.summary(min(now, self.att.E)))
        if self._ticks % 30 == 0:
            self._checkpoint(now)
        if now >= self.att.auto_end:
            self.stop()
