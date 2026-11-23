"""A whole class and a whole exam run through the real SessionController, with fake cameras.

No webcam and no face models needed: workers, face engine and pipeline are replaced by fakes, and the
test feeds FrameResult objects straight in on a simulated clock. Needs PySide6 (skipped without it).
Run from the project root:   python -m unittest discover -s tests -v
"""
import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

HAVE_QT = importlib.util.find_spec("PySide6") is not None
if HAVE_QT:
    from PySide6.QtCore import QObject, Signal
    from PySide6.QtGui import QImage
    from PySide6.QtWidgets import QApplication

    from app.config import Settings
    from app.db import Database
    from app.services import proctor as proctor_mod
    from app.utils import VIDEO_BAD
    from app.vision.types import FrameResult, Overlay, TrackView
    from app.workers import camera as camera_mod
    from app.workers import session as session_mod

    class FakeWorker(QObject):
        frame = Signal(QImage)                     # same signature as the real CameraWorker
        result = Signal(object)
        overlays = Signal(object)
        status = Signal(str)

        def __init__(self, source, processor, fps, width, height, preview_width=960, parent=None):
            super().__init__(parent)
            self.source, self.processor = source, processor
            self.started = self.stopped = self.stop_requested = False

        def start(self):
            self.started = True

        def request_stop(self):
            self.stop_requested = True

        def stop(self):
            self.stopped = True

        def isRunning(self):
            return False

    class Clock:
        def __init__(self, now):
            self.now = now

        def time(self):
            return self.now

    class Sig:
        def __init__(self):
            self.count = 0

        def emit(self, *args):
            self.count += 1

        def connect(self, *args):
            pass

W, H, S = 1280, 720, 1_000_000.0


def unit(seed):
    v = np.random.default_rng(seed).normal(size=128).astype(np.float32)
    return v / np.linalg.norm(v)


def gate_frame(ts, sid, ratio=0.3, votes=5, live=True, frame=None):
    size = W * ratio
    t = TrackView(1, (400.0, 200.0, size, size), sid, 0.8, True, ratio, 0, 0, 0, 10.0, votes, live, ts)
    return FrameResult(ts, W, H, [t], frame=frame)


def room_frame(ts, people, frame=None):
    """people: list of (sid, yaw). Small faces, as the classroom camera sees them."""
    tracks = [TrackView(10 + i, (60.0 * (i + 1), 300.0, 50.0, 50.0), sid, 0.8, True, 50.0 / W, yaw, 0, 0, 60.0, 5,
                        False, ts) for i, (sid, yaw) in enumerate(people)]
    return FrameResult(ts, W, H, tracks, frame=frame)


@unittest.skipUnless(HAVE_QT, "PySide6 is not installed")
class SessionFlowTests(unittest.TestCase):
    def setUp(self):
        self.app = QApplication.instance() or QApplication([])
        self.tmp = tempfile.TemporaryDirectory()
        tmp = Path(self.tmp.name)
        self.db = Database(tmp / "t.db")
        self.ids = []
        for i in range(1, 5):
            sid = self.db.add_student(reg_no=f"R{i:03d}", name=f"Student {i}", section="A")
            self.db.add_sample(sid, f"faces/{i}.jpg", unit(i), 50.0)
            self.ids.append(sid)
        self.ctx = SimpleNamespace(db=self.db, settings=Settings(), sessions_changed=Sig(), students_changed=Sig(),
                                   live_sources=set())
        self.clock = Clock(S - 120)
        self.pipeline_fps = []
        self.saved = (session_mod.CameraWorker, session_mod.FaceEngine, session_mod.VisionPipeline,
                      session_mod.SessionProcessor, session_mod.time, proctor_mod.EVIDENCE_DIR, proctor_mod.DATA_DIR)

        def make_pipeline(engine, gallery, s, objects=None, fps=2.0):
            self.pipeline_fps.append(fps)
            return SimpleNamespace(gallery=gallery)

        session_mod.CameraWorker = FakeWorker
        session_mod.FaceEngine = lambda *a, **k: object()
        session_mod.VisionPipeline = make_pipeline
        session_mod.SessionProcessor = lambda pipeline, mode, names, s: SimpleNamespace(mode=mode, pipeline=pipeline)
        session_mod.time = self.clock
        proctor_mod.DATA_DIR, proctor_mod.EVIDENCE_DIR = tmp, tmp / "evidence"

    def tearDown(self):
        (session_mod.CameraWorker, session_mod.FaceEngine, session_mod.VisionPipeline, session_mod.SessionProcessor,
         session_mod.time, proctor_mod.EVIDENCE_DIR, proctor_mod.DATA_DIR) = self.saved
        self.db.close()
        self.tmp.cleanup()

    def at(self, ctrl, t, frame_result):
        self.clock.now = S + t
        ctrl._on_result("class", frame_result)

    def test_class_session_end_to_end(self):
        s1, s2, s3, s4 = self.ids
        ctrl = session_mod.SessionController(self.ctx, "class")
        gate_msgs, finished, tick_info = [], [], []
        ctrl.gate_msg.connect(lambda kind, text: gate_msgs.append((kind, text)))
        ctrl.finished.connect(finished.append)
        ctrl.tick.connect(tick_info.append)
        cfg = session_mod.SessionConfig("class", "Maths", "", S, 50, 40, "0", "same")
        sid = ctrl.start(cfg)
        self.assertTrue(ctrl.running)
        self.assertEqual(list(ctrl._workers), ["class"])
        self.assertTrue(ctrl._workers["class"].started)
        self.assertEqual(ctrl._workers["class"].processor.mode, "both")      # one camera does both jobs

        # --- gate before class: unknown face, then proper check-ins
        self.at(ctrl, -100, gate_frame(S - 100, None, votes=1))
        self.assertEqual(gate_msgs[-1][0], "info")
        self.at(ctrl, -99, gate_frame(S - 99, None, votes=4))
        self.assertEqual(gate_msgs[-1][0], "bad")
        self.at(ctrl, -90, gate_frame(S - 90, s1, ratio=0.05))               # too far away: ignored
        self.assertEqual(ctrl.att.recs[s1].check_in, None)
        for k, who in enumerate((s1, s2, s3, s4)):
            self.at(ctrl, -80 + 10 * k, gate_frame(S - 80 + 10 * k, who))
            self.assertEqual(gate_msgs[-1][0], "ok")
        self.at(ctrl, -30, gate_frame(S - 30, s1))                            # second pass is not a new check-in
        self.assertEqual(gate_msgs[-1][0], "info")
        self.assertIn("already", gate_msgs[-1][1])

        # --- the class itself, one classroom frame every 10 s
        for t in range(0, 3001, 10):
            people = [(s1, 0.0), (s3, 0.0)]
            if t <= 300:
                people.append((s2, 0.0))                                     # student 2 leaves after 5 minutes
            if t <= 1200 or t >= 1920:
                people.append((s4, 0.0))                                     # student 4 steps out for 12 minutes
            self.at(ctrl, t, room_frame(S + t, people))
            if t % 60 == 0:
                ctrl._on_tick()
        self.assertTrue(any("Class running" in i["phase"] for i in tick_info))

        # --- gate after class
        self.at(ctrl, 3000 - 100, gate_frame(S + 2900, s1))                   # check-out window is open
        self.assertIn("checked out", gate_msgs[-1][1])
        self.at(ctrl, 3050, gate_frame(S + 3050, s2))
        self.at(ctrl, 3060, gate_frame(S + 3060, s4))

        self.clock.now = S + 3100
        ctrl.stop()
        self.assertFalse(ctrl.running)
        self.assertEqual(finished, [sid])
        self.assertTrue(ctrl._workers == {})

        rows = {r["reg_no"]: r for r in self.db.attendance(sid)}
        self.assertEqual(rows["R001"]["status"], "PRESENT")
        self.assertEqual(rows["R002"]["status"], "ABSENT")                    # passed the gate, hardly in the room
        self.assertIn("passed the gate", rows["R002"]["reason"])
        self.assertEqual(rows["R003"]["status"], "REVIEW")                    # in class all along, no check-out
        self.assertEqual(rows["R004"]["status"], "ABSENT")                    # 38 of 40 minutes
        self.assertEqual(len(self.db.intervals(sid)[s4]), 2)                  # in, break, back in
        self.assertEqual(self.db.get_session(sid)["status"], "finished")
        self.assertGreaterEqual(self.ctx.sessions_changed.count, 2)

    def test_session_closes_itself_after_the_checkout_window(self):
        ctrl = session_mod.SessionController(self.ctx, "class")
        finished = []
        ctrl.finished.connect(finished.append)
        sid = ctrl.start(session_mod.SessionConfig("class", "Short", "A", S, 5, 4, "0", "same"))
        self.clock.now = S + 200
        ctrl._on_tick()
        self.assertTrue(ctrl.running)
        self.clock.now = S + 5 * 60 + 15 * 60 + 5                            # past the check-out window
        ctrl._on_tick()
        self.assertFalse(ctrl.running)
        self.assertEqual(finished, [sid])

    def test_start_validation_messages(self):
        ctrl = session_mod.SessionController(self.ctx, "class")
        with self.assertRaises(ValueError) as cm:
            ctrl.start(session_mod.SessionConfig("class", "X", "no-such-section", S, 50, 40, "0", "none"))
        self.assertIn("No students", str(cm.exception))
        empty = Database(Path(self.tmp.name) / "e.db")
        empty.add_student(reg_no="Z1", name="No photos", section="A")
        ctx2 = SimpleNamespace(db=empty, settings=Settings(), sessions_changed=Sig(), students_changed=Sig(),
                               live_sources=set())
        with self.assertRaises(ValueError) as cm:
            session_mod.SessionController(ctx2, "class").start(
                session_mod.SessionConfig("class", "X", "", S, 50, 40, "0", "none"))
        self.assertIn("face samples", str(cm.exception))
        empty.close()

    def test_separate_gate_camera_gets_its_own_worker(self):
        ctrl = session_mod.SessionController(self.ctx, "class")
        ctrl.start(session_mod.SessionConfig("class", "Two cams", "", S, 50, 40, "0", "1"))
        self.assertEqual(sorted(ctrl._workers), ["class", "gate"])
        self.assertEqual(ctrl._workers["class"].processor.mode, "class")
        self.assertEqual(ctrl._workers["gate"].processor.mode, "gate")
        self.assertEqual(sorted(self.pipeline_fps), [2.0, 5.0])               # each pipeline knows its camera's rate
        self.clock.now = S - 30
        ctrl._on_result("gate", gate_frame(S - 30, self.ids[0]))
        self.assertEqual(ctrl.att.recs[self.ids[0]].check_in, S - 30)
        ctrl.stop()

    def test_exam_session_records_alerts_with_evidence(self):
        s1, s2 = self.ids[0], self.ids[1]
        ctrl = session_mod.SessionController(self.ctx, "exam")
        alerts, overlays_out = [], []
        ctrl.alert.connect(alerts.append)
        ctrl.overlays.connect(lambda role, ov: overlays_out.append(ov))
        sid = ctrl.start(session_mod.SessionConfig("exam", "Midterm", "", S, 60, 50, "0", "none"))
        self.assertIsNotNone(ctrl.proctor)
        blank = np.zeros((H, W, 3), np.uint8)
        for k in range(0, 61):                                                # 30 s at 2 fps
            t = k * 0.5
            self.at(ctrl, t, room_frame(S + t, [(s1, 60.0 if t >= 5 else 0.0), (s2, 0.0)], frame=blank))
        self.assertEqual([a["type"] for a in alerts], ["LOOKING_AWAY"])
        self.assertEqual(alerts[0]["name"], "Student 1")
        self.assertTrue(alerts[0]["snapshot"])
        self.assertTrue((Path(self.tmp.name) / alerts[0]["snapshot"]).exists())
        # the flagged face is recoloured on the live overlay
        ctrl._on_overlays("class", [Overlay(0.1, 0.1, 0.1, 0.1, label="Student 1", tid=10),
                                    Overlay(0.3, 0.1, 0.1, 0.1, label="Student 2", tid=11)])
        recoloured = overlays_out[-1]
        self.assertEqual(recoloured[0].color, VIDEO_BAD)
        self.assertNotEqual(recoloured[1].color, VIDEO_BAD)
        self.clock.now = S + 40
        ctrl.stop()
        events = self.db.events(sid)
        self.assertEqual([e["type"] for e in events], ["LOOKING_AWAY"])
        self.assertEqual(events[0]["reg_no"], "R001")
        self.assertTrue(self.db.risk(sid))

    # ------------------------------------------------------------------ exam window
    def test_exam_is_only_watched_between_its_start_and_end(self):
        s1, s2 = self.ids[0], self.ids[1]
        ctrl = session_mod.SessionController(self.ctx, "exam")
        alerts = []
        ctrl.alert.connect(alerts.append)
        sid = ctrl.start(session_mod.SessionConfig("exam", "Midterm", "", S, 60, 50, "0", "none"))
        E = S + 60 * 60
        # Before the start: student 1 stares sideways for a minute. Nobody is being watched yet.
        for k in range(60):
            self.at(ctrl, -60 + k, room_frame(S - 60 + k, [(s1, 60.0), (s2, 0.0)]))
        self.assertEqual(alerts, [])
        self.assertEqual(ctrl.proctor.state, {})
        # During the exam: student 2 is there until 3295 s, then leaves; student 1 stays.
        for t in range(0, 3300, 5):
            self.at(ctrl, t, room_frame(S + t, [(s1, 0.0), (s2, 0.0)]))
        for t in range(3300, 3600, 5):
            self.at(ctrl, t, room_frame(S + t, [(s1, 0.0)]))
        self.assertEqual([a["type"] for a in alerts], ["FACE_NOT_VISIBLE"])          # raised inside the exam
        # After the end everybody packs up and leaves. None of that is recorded.
        n = len(alerts)
        for t in range(3600, 4400, 5):
            self.at(ctrl, t, room_frame(S + t, []))
        self.assertEqual(len(alerts), n)
        self.assertEqual(ctrl.proctor.active, {})
        self.clock.now = S + 4500                                                    # stopped 15 minutes late
        ctrl.stop()
        rows = {r["name"]: r for r in self.db.risk(sid)}
        # Student 2 was away from 3295 s to the end of the exam (305 s), not until the stop button was pressed.
        self.assertAlmostEqual(rows["Student 2"]["missing_sec"], E - (S + 3295), delta=1)

    def test_flags_are_cleared_when_the_exam_is_over(self):
        s1 = self.ids[0]
        ctrl = session_mod.SessionController(self.ctx, "exam")
        ctrl.start(session_mod.SessionConfig("exam", "Short", "", S, 1, 1, "0", "none"))
        for k in range(0, 60):                                                       # looks away inside the minute
            self.at(ctrl, k, room_frame(S + k, [(s1, 60.0)]))
        self.assertTrue(ctrl.proctor.active)
        self.at(ctrl, 61, room_frame(S + 61, [(s1, 60.0)]))                          # a frame after the end
        self.assertEqual(ctrl.proctor.active, {})
        ctrl.stop()

    # ------------------------------------------------------------------ gate off
    def test_without_a_gate_camera_presence_alone_decides(self):
        s1 = self.ids[0]
        ctrl = session_mod.SessionController(self.ctx, "class")
        ticks = []
        ctrl.tick.connect(ticks.append)
        sid = ctrl.start(session_mod.SessionConfig("class", "No gate", "", S, 50, 40, "0", "none"))
        self.assertEqual(ticks[-1]["gate"], "Gate off")
        for t in range(0, 3001, 10):
            self.at(ctrl, t, room_frame(S + t, [(s1, 0.0)]))
        self.clock.now = S + 3005
        ctrl._on_tick()                                       # class over; no check-out window to wait for
        self.assertFalse(ctrl.running)
        rows = {r["reg_no"]: r for r in self.db.attendance(sid)}
        self.assertEqual(rows["R001"]["status"], "PRESENT")   # not "needs review: no check-in"
        self.assertEqual(rows["R002"]["status"], "ABSENT")
        self.assertTrue(self.ctx.settings.require_checkin)    # the saved settings were not changed
        self.assertTrue(self.ctx.settings.require_checkout)

    # ------------------------------------------------------------------ cameras
    def test_a_webcam_already_in_use_is_refused(self):
        first = session_mod.SessionController(self.ctx, "class")
        first.start(session_mod.SessionConfig("class", "A", "", S, 50, 40, "0", "none"))
        self.assertEqual(self.ctx.live_sources, {0})
        second = session_mod.SessionController(self.ctx, "exam")
        with self.assertRaises(ValueError) as cm:
            second.start(session_mod.SessionConfig("exam", "B", "", S, 50, 40, "0", "none"))
        self.assertIn("Webcam 0", str(cm.exception))
        self.assertFalse(second.running)
        self.assertEqual(self.ctx.live_sources, {0})          # the refused start claimed nothing
        first.stop()
        self.assertEqual(self.ctx.live_sources, set())
        second.start(session_mod.SessionConfig("exam", "B", "", S, 50, 40, "0", "none"))   # free again
        second.stop()
        self.assertEqual(self.ctx.live_sources, set())

    def test_class_and_gate_cannot_share_one_webcam_but_files_and_streams_can(self):
        ctrl = session_mod.SessionController(self.ctx, "class")
        with self.assertRaises(ValueError) as cm:
            ctrl.start(session_mod.SessionConfig("class", "C", "", S, 50, 40, "0", "0"))
        self.assertIn("same webcam", str(cm.exception))
        self.assertEqual(self.ctx.live_sources, set())
        ctrl.start(session_mod.SessionConfig("class", "C", "", S, 50, 40, "clip.mp4", "clip.mp4"))
        self.assertEqual(self.ctx.live_sources, set())        # a video file is not exclusive
        ctrl.stop()
        ctrl.start(session_mod.SessionConfig("class", "C", "", S, 50, 40, "0", "1"))
        self.assertEqual(self.ctx.live_sources, {0, 1})
        ctrl.stop()
        self.assertEqual(self.ctx.live_sources, set())

    def test_all_cameras_are_asked_to_stop_before_any_is_waited_for(self):
        ctrl = session_mod.SessionController(self.ctx, "class")
        ctrl.start(session_mod.SessionConfig("class", "Two", "", S, 50, 40, "0", "1"))
        workers = list(ctrl._workers.values())
        ctrl.stop()
        self.assertTrue(all(w.stop_requested and w.stopped for w in workers))

    # ------------------------------------------------------------------ notices
    def test_a_missing_object_detector_is_reported_not_silent(self):
        def broken(**kwargs):
            raise RuntimeError("Object detection needs the 'ultralytics' package")
        saved = session_mod.ObjectDetector
        session_mod.ObjectDetector = broken
        self.addCleanup(setattr, session_mod, "ObjectDetector", saved)
        ctrl = session_mod.SessionController(self.ctx, "exam")
        ctrl.start(session_mod.SessionConfig("exam", "Midterm", "", S, 60, 50, "0", "none", objects=True))
        self.assertEqual(len(ctrl.notices), 1)
        self.assertIn("detection is off", ctrl.notices[0])
        self.assertIn("ultralytics", ctrl.notices[0])
        ctrl.stop()
        ctrl.start(session_mod.SessionConfig("exam", "Again", "", S, 60, 50, "0", "none", objects=False))
        self.assertEqual(ctrl.notices, [])                    # cleared for the next session
        ctrl.stop()

    def test_notes_from_a_camera_frame_reach_the_status_line(self):
        ctrl = session_mod.SessionController(self.ctx, "exam")
        statuses = []
        ctrl.status.connect(lambda role, text: statuses.append((role, text)))
        ctrl.start(session_mod.SessionConfig("exam", "Midterm", "", S, 60, 50, "0", "none"))
        fr = room_frame(S + 1, [(self.ids[0], 0.0)])
        fr.notes.append("Phone, book and laptop detection stopped: out of memory")
        self.at(ctrl, 1, fr)
        self.assertEqual(statuses[-1], ("class", "Phone, book and laptop detection stopped: out of memory"))
        ctrl.stop()


@unittest.skipUnless(HAVE_QT, "PySide6 is not installed")
class CameraWorkerTests(unittest.TestCase):
    """The camera thread must never die silently, and the app must be able to tell a webcam from a stream."""

    def setUp(self):
        self.app = QApplication.instance() or QApplication([])

    def test_only_local_webcams_count_as_webcams(self):
        self.assertEqual(camera_mod.webcam_index("0"), 0)
        self.assertEqual(camera_mod.webcam_index(" 2 "), 2)
        self.assertEqual(camera_mod.webcam_index(1), 1)
        for text in ("rtsp://camera/stream", "http://host/video.mjpg", "clip.mp4", "", "-1", "1.5"):
            self.assertIsNone(camera_mod.webcam_index(text), text)

    def test_odd_digit_characters_are_text_not_a_webcam_number(self):
        # '²'.isdigit() is True but int('²') raises, so these used to crash the start of a session
        for text in ("²", "٣", "1²"):
            self.assertEqual(camera_mod.parse_source(text), text)
            self.assertIsNone(camera_mod.webcam_index(text))
        self.assertEqual(camera_mod.parse_source(" 12 "), 12)

    def test_a_crash_inside_the_camera_thread_is_reported_not_lost(self):
        worker = camera_mod.CameraWorker(0, None, 2.0, 640, 480)
        said = []
        worker.status.connect(lambda text: said.append(text))
        with mock.patch.object(camera_mod.CameraWorker, "_run", side_effect=RuntimeError("boom")):
            with self.assertLogs("app.workers.camera", level="ERROR"):
                worker.run()                                   # must not raise
        self.assertEqual(said, ["Camera stopped: boom"])

    def test_a_source_that_raises_when_opened_is_retried_and_can_still_be_stopped(self):
        worker = camera_mod.CameraWorker("rtsp://bad", None, 2.0, 640, 480)
        said, calls = [], []
        worker.status.connect(lambda text: said.append(text))

        def failing_open(src, width, height):
            calls.append(src)
            worker.request_stop()                              # the user presses Stop right after the first failure
            raise ValueError("malformed URL")

        with mock.patch.object(camera_mod, "open_capture", failing_open):
            worker.run()
        self.assertEqual(calls, ["rtsp://bad"])
        self.assertEqual(said[0], "Cannot open camera 'rtsp://bad'. Retrying...")
        self.assertEqual(said[-1], "Stopped")


if __name__ == "__main__":
    unittest.main()
