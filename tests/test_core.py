"""Tests for everything that does not need a camera, the real face models or Qt.

Run from the project root:   python -m unittest discover -s tests -v
"""
import csv
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import Settings, load_settings, save_settings            # noqa: E402
from app.db import Database                                              # noqa: E402
from app.services.attendance import ABSENT, PRESENT, REVIEW, AttendanceEngine, breaks_between  # noqa: E402
from app.services import enrollment as enrollment_mod                     # noqa: E402
from app.services.enrollment import EnrollProcessor, Sample, delete_student_files, save_samples  # noqa: E402
from app.services.exports import (export_attendance_csv, export_events_csv, export_risk_csv,  # noqa: E402
                                  safe_cell)
from app.services.proctor import ProctorEngine, robust_z                 # noqa: E402
from app.vision.gallery import Gallery                                   # noqa: E402
from app.vision.pipeline import VisionPipeline                           # noqa: E402
from app.vision.pose import head_pose, project_model                     # noqa: E402
from app.vision.tracker import Det, IdentityTracker, Track               # noqa: E402
from app.utils import slug                                               # noqa: E402
from app.vision.types import FrameResult, ObjectDet, TrackView           # noqa: E402

W, H = 1280, 720


def unit(seed, dim=128):
    v = np.random.default_rng(seed).normal(size=dim).astype(np.float32)
    return v / np.linalg.norm(v)


def det_row(cx, cy, size, yaw=0.0, pitch=0.0):
    """A detector row (x, y, w, h, 5 landmarks, score) for a face centred at (cx, cy)."""
    depth = W * 63.0 / (size * 0.45)
    lm = project_model(yaw, pitch, W, H, depth_mm=depth, center=(cx, cy))
    return np.concatenate([[cx - size / 2, cy - size / 2, size, size], lm.reshape(-1), [0.95]]).astype(np.float32)


class FakeEngine:
    """Stands in for FaceEngine: scripted detections, embedding chosen by the face's column."""

    def __init__(self, embeddings):
        self.embeddings = embeddings          # column index (x // 200) -> embedding
        self.rows = []

    def detect(self, frame):
        return np.asarray(self.rows, np.float32).reshape(-1, 15)

    def embed(self, frame, row):
        return self.embeddings[int(row[0] // 200)]


def tv(tid, sid, yaw=0.0, pitch=0.0, bbox=(100.0, 100.0, 60.0, 60.0), votes=5, age=60.0, visible=True):
    return TrackView(tid, bbox, sid, 0.8, visible, bbox[2] / W, yaw, pitch, 0.0, age, votes, False, 0.0)


def frame_result(ts, tracks, objects=(), changes=()):
    return FrameResult(ts, W, H, list(tracks), list(objects), list(changes), None)


class SettingsTests(unittest.TestCase):
    def test_roundtrip_and_coercion(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "s.json"
            s = Settings()
            s.min_presence_min = 33
            s.gate_liveness = True
            save_settings(s, p)
            loaded = load_settings(p)
            self.assertEqual(loaded.min_presence_min, 33)
            self.assertTrue(loaded.gate_liveness)
            p.write_text('{"class_duration_min": "45", "gate_liveness": "yes", "bogus": 1, "recog_threshold": "x"}')
            loaded = load_settings(p)
            self.assertEqual(loaded.class_duration_min, 45)
            self.assertTrue(loaded.gate_liveness)
            self.assertEqual(loaded.recog_threshold, Settings().recog_threshold)   # bad value -> default

    def test_missing_file_gives_defaults(self):
        self.assertEqual(load_settings(Path("/nonexistent/x.json")), Settings())


class PoseTests(unittest.TestCase):
    def test_signs_and_accuracy(self):
        for yaw in (-40, -20, 0, 20, 40):
            for pitch in (-25, 0, 25):
                est = head_pose(project_model(yaw, pitch, W, H, depth_mm=900, center=(300, 250)), W, H)
                self.assertAlmostEqual(est[0], yaw, delta=1.0)
                self.assertAlmostEqual(est[1], pitch, delta=1.0)


class GalleryTests(unittest.TestCase):
    def test_identify_threshold_and_margin(self):
        a, b = unit(1), unit(2)
        g = Gallery(np.array([1, 1, 2]), np.vstack([a, a * 0.9 + unit(5) * 0.05, b]))
        self.assertEqual(g.identify(a, 0.4, 0.04)[0], 1)
        self.assertEqual(g.identify(b, 0.4, 0.04)[0], 2)
        self.assertIsNone(g.identify(unit(99), 0.4, 0.04)[0])           # stranger
        twin = Gallery(np.array([1, 2]), np.vstack([a, a + unit(7) * 0.01]))
        self.assertIsNone(twin.identify(a, 0.4, 0.04)[0])               # look-alikes are rejected
        self.assertIsNone(Gallery(np.zeros(0), np.zeros((0, 128))).identify(a, 0.4, 0.04)[0])


class TrackerPipelineTests(unittest.TestCase):
    def test_tracker_keeps_ids_through_motion_and_brief_loss(self):
        tr = IdentityTracker(max_age=4.0)
        def det(x): return Det((x, 100, 80, 80), np.zeros((5, 2)), 0.9, np.zeros(15, np.float32))
        t = tr.update([det(100)], 0.0)
        tid = t[0].id
        for i in range(1, 5):
            self.assertEqual(tr.update([det(100 + 8 * i)], i * 0.5)[0].id, tid)
        out = tr.update([], 3.0)                      # lost for a moment
        self.assertFalse(out[0].matched)
        self.assertEqual(tr.update([det(140)], 4.0)[0].id, tid)           # comes back, same track
        self.assertEqual(tr.update([], 20.0), [])                         # expired

    def test_pipeline_identifies_students_and_flags_strangers(self):
        e1, e2, stranger = unit(1), unit(2), unit(3)
        gallery = Gallery(np.array([1, 2]), np.vstack([e1, e2]))
        engine = FakeEngine({0: e1, 1: e2, 2: stranger})
        pipe = VisionPipeline(engine, gallery, Settings())
        frame = np.zeros((H, W, 3), np.uint8)
        res = None
        for i in range(6):
            engine.rows = [det_row(100, 300, 100), det_row(300, 300, 100), det_row(500, 300, 100)]
            res = pipe.process(frame, 100.0 + i * 0.5)
        by_x = {round(t.bbox[0]): t for t in res.tracks}
        self.assertEqual(sorted(t.sid for t in res.tracks if t.sid is not None), [1, 2])
        self.assertEqual([t for t in res.tracks if t.sid is None][0].votes, 3)   # decided: stranger
        self.assertEqual(res.identity_changes, [])
        self.assertEqual(len(by_x), 3)

    def test_profile_faces_are_not_used_for_recognition(self):
        gallery = Gallery(np.array([1]), unit(1).reshape(1, -1))
        engine = FakeEngine({0: unit(1)})
        pipe = VisionPipeline(engine, gallery, Settings())
        for i in range(5):
            engine.rows = [det_row(100, 300, 100, yaw=50)]
            res = pipe.process(np.zeros((H, W, 3), np.uint8), i * 0.5)
        self.assertEqual(res.tracks[0].votes, 0)                          # never voted
        self.assertGreater(res.tracks[0].yaw, 40)


class GateHandoverTests(unittest.TestCase):
    def run_frames(self, pipe, engine, rows, start, count, step=0.5):
        res = None
        for i in range(count):
            engine.rows = rows
            res = pipe.process(np.zeros((H, W, 3), np.uint8), start + i * step)
        return res

    def test_next_student_at_the_gate_does_not_inherit_the_previous_name(self):
        e1, e2 = unit(1), unit(2)
        gallery = Gallery(np.array([1, 2]), np.vstack([e1, e2]))
        engine = FakeEngine({0: e1})
        pipe = VisionPipeline(engine, gallery, Settings())
        close_up = [det_row(100, 300, 200)]                                   # 200 px of 1280 = close to the camera
        res = self.run_frames(pipe, engine, close_up, 100.0, 6)
        self.assertEqual(res.tracks[0].sid, 1)
        tid = res.tracks[0].track_id
        self.run_frames(pipe, engine, [], 103.0, 6)                           # gate empty for ~3 s
        engine.embeddings = {0: e2}                                            # student 2 steps into the same spot
        res = self.run_frames(pipe, engine, close_up, 106.0, 1)
        self.assertEqual(res.tracks[0].track_id, tid)                          # same track object...
        self.assertIsNone(res.tracks[0].sid)                                   # ...but identity was wiped
        res = self.run_frames(pipe, engine, close_up, 106.5, 5)
        self.assertEqual(res.tracks[0].sid, 2)
        self.assertEqual(res.identity_changes, [])                             # a reset is not reported as a swap

    def test_classroom_faces_keep_their_name_through_short_dropouts(self):
        e1 = unit(1)
        gallery = Gallery(np.array([1]), e1.reshape(1, -1))
        engine = FakeEngine({0: e1})
        pipe = VisionPipeline(engine, gallery, Settings())
        small = [det_row(100, 300, 60)]                                       # 60 px: a seat in the room
        res = self.run_frames(pipe, engine, small, 100.0, 6)
        self.assertEqual(res.tracks[0].sid, 1)
        self.run_frames(pipe, engine, [], 103.0, 6)                           # head down for 3 s
        res = self.run_frames(pipe, engine, small, 106.0, 1)
        self.assertEqual(res.tracks[0].sid, 1)                                 # still known straight away

    def test_slow_analysis_rate_does_not_wipe_close_up_identities(self):
        e1 = unit(1)
        gallery = Gallery(np.array([1]), e1.reshape(1, -1))
        engine = FakeEngine({0: e1})
        close_up = [det_row(100, 300, 200)]
        slow = VisionPipeline(engine, gallery, Settings(), fps=0.5)           # one frame every 2 s
        res = self.run_frames(slow, engine, close_up, 100.0, 5, step=2.0)
        self.assertEqual(res.tracks[0].sid, 1)                                 # votes survive between frames
        self.assertEqual(slow.reset_gap, 6.0)
        self.assertEqual(VisionPipeline(engine, gallery, Settings()).reset_gap, 1.5)


class IdentityVotingTests(unittest.TestCase):
    """A few bad frames must neither lose a name nor hand it to someone else."""

    @staticmethod
    def new_track(window=5):
        det = Det((100.0, 100.0, 80.0, 80.0), np.zeros((5, 2)), 0.95, np.zeros(15, np.float32))
        return Track(1, det, 0.0, window, 20.0)

    @staticmethod
    def vote(track, *votes, required=3):
        """Feed votes one at a time, the way the pipeline does. Returns the last change that happened."""
        change = None
        for v in votes:
            sid, score = v if isinstance(v, tuple) else (v, 0.8)
            track.add_vote(sid, score)
            change = track.resolve(required) or change
        return change

    def test_a_student_is_adopted_after_enough_votes(self):
        t = self.new_track()
        self.assertIsNone(self.vote(t, 7, 7))
        self.assertIsNone(t.sid)                                        # two votes are not enough
        self.assertEqual(self.vote(t, 7), (None, 7))
        self.assertEqual(t.sid, 7)

    def test_blurry_frames_do_not_clear_a_confirmed_name(self):
        t = self.new_track()
        self.vote(t, 7, 7, 7)
        self.assertIsNone(self.vote(t, None, None, None, None))        # four unrecognised checks in a row
        self.assertEqual(t.sid, 7)
        self.assertEqual(self.vote(t, None), (7, None))                 # a whole window of nothing: now it goes
        self.assertIsNone(t.sid)
        self.assertEqual(t.sid_score, 0.0)

    def test_two_wrong_votes_do_not_hand_the_name_to_someone_else(self):
        t = self.new_track()
        self.vote(t, 7, 7, 7)
        self.assertIsNone(self.vote(t, 9, 9))
        self.assertEqual(t.sid, 7)

    def test_a_real_swap_needs_enough_votes_and_a_majority(self):
        t = self.new_track()
        self.vote(t, 7, 7, 7)
        self.assertIsNone(self.vote(t, 9, 9))                           # window 7 7 7 9 9
        self.assertEqual(self.vote(t, 9), (7, 9))                       # window 7 7 9 9 9: three votes, more than 7's two
        self.assertEqual(t.sid, 9)

    def test_a_challenger_must_beat_the_current_student(self):
        t = self.new_track(window=4)
        self.vote(t, 7, 7, required=2)
        self.assertEqual(t.sid, 7)
        self.assertIsNone(self.vote(t, 9, 9, required=2))              # window 7 7 9 9: enough votes, but only a tie
        self.assertEqual(t.sid, 7)
        self.assertEqual(self.vote(t, 9, required=2), (7, 9))           # window 7 9 9 9: now clearly ahead
        self.assertEqual(t.sid, 9)

    def test_two_other_students_level_on_votes_do_not_take_the_name(self):
        t = self.new_track(window=8)
        self.vote(t, 7, 7, 7)                                           # 7 is confirmed
        self.assertIsNone(self.vote(t, 9, 9, 9, 4, 4))                  # 7 and 9 are level at three votes
        self.assertEqual(t.sid, 7)
        self.assertIsNone(self.vote(t, 4))                              # window 7 7 9 9 9 4 4 4: 9 and 4 level, 7 has two
        self.assertEqual(t.sid, 7)                                      # two newcomers level with each other: no decision
        self.assertEqual(self.vote(t, 4), (7, 4))                       # window 7 9 9 9 4 4 4 4: 4 is now clearly ahead
        self.assertEqual(t.sid, 4)

    def test_confidence_comes_from_the_confirmed_students_votes_only(self):
        t = self.new_track()
        self.vote(t, (7, 0.9), (7, 0.7), (7, 0.8))
        self.assertAlmostEqual(t.sid_score, 0.8)
        self.vote(t, (None, 0.1), (9, 0.2))                             # a blurry frame and one stray vote
        self.assertEqual(t.sid, 7)
        self.assertAlmostEqual(t.sid_score, 0.8)                        # they do not drag the confidence down
        self.vote(t, (7, 0.6))                                          # window now holds 7's votes 0.7, 0.8, 0.6
        self.assertAlmostEqual(t.sid_score, 0.7)                        # and it follows the newest votes


class PipelineIdentityTests(unittest.TestCase):
    """What the pipeline reports when the person at a seat changes."""

    def setUp(self):
        self.e1, self.e2, self.stranger = unit(1), unit(2), unit(3)
        gallery = Gallery(np.array([1, 2]), np.vstack([self.e1, self.e2]))
        self.engine = FakeEngine({0: self.e1})
        self.pipe = VisionPipeline(self.engine, gallery, Settings())
        self.seat = [det_row(100, 300, 60)]                              # 60 px wide: a seat in the room
        self.t = 0.0

    def frames(self, count):
        """One frame every 8.5 s, so every frame gets a fresh recognition vote (re-check interval is 8 s)."""
        out = []
        for _ in range(count):
            self.engine.rows = self.seat
            out.append(self.pipe.process(np.zeros((H, W, 3), np.uint8), self.t))
            self.t += 8.5
        return out

    def test_a_student_replaced_by_another_is_reported_once(self):
        first = self.frames(3)
        self.assertEqual(first[-1].tracks[0].sid, 1)
        tid = first[-1].tracks[0].track_id
        self.engine.embeddings = {0: self.e2}                            # student 2 sits down in the same seat
        later = self.frames(4)
        changes = [c for res in later for c in res.identity_changes]
        self.assertEqual(changes, [(tid, 1, 2)])                          # reported exactly once
        self.assertEqual(later[-1].tracks[0].sid, 2)

    def test_a_name_that_is_lost_is_not_reported_as_a_swap(self):
        first = self.frames(3)
        self.assertEqual(first[-1].tracks[0].sid, 1)
        self.engine.embeddings = {0: self.stranger}                       # nobody in the gallery matches any more
        later = self.frames(5)
        self.assertEqual(later[2].tracks[0].sid, 1)                       # a few misses keep the name
        self.assertIsNone(later[-1].tracks[0].sid)                        # a whole window of misses drops it
        self.assertEqual([c for res in later for c in res.identity_changes], [])


class PoseOrderTests(unittest.TestCase):
    def test_mirrored_landmark_order_gives_the_same_pose(self):
        lm = project_model(25, -10, W, H, depth_mm=800, center=(500, 300))
        normal = head_pose(lm, W, H)
        mirrored = head_pose(lm[[1, 0, 2, 4, 3]], W, H)
        for a, b in zip(normal, mirrored):
            self.assertAlmostEqual(a, b, delta=0.5)


class EngineScalingTests(unittest.TestCase):
    def make(self, max_side):
        from app.vision.engine import FaceEngine
        eng = FaceEngine.__new__(FaceEngine)                                   # skip loading the real models
        eng.max_side, eng._size, eng.calls = max_side, (320, 320), {}

        class FakeDet:
            def setInputSize(inner, size):
                eng.calls["size"] = size

            def detect(inner, img):
                eng.calls["shape"] = img.shape[:2]
                if eng.calls.get("none"):
                    return 0, None
                row = np.zeros((1, 15), np.float32)
                row[0, :4] = [100, 50, 40, 40]
                row[0, 4:14] = np.arange(10) * 10
                row[0, 14] = 0.9
                return 1, row
        eng._det = FakeDet()
        return eng

    def test_boxes_are_scaled_back_when_the_frame_is_downsized(self):
        eng = self.make(800)
        out = eng.detect(np.zeros((1600, 3200, 3), np.uint8))                  # 3200 x 1600 -> shrunk to 800 x 400
        self.assertEqual(eng.calls["size"], (800, 400))
        self.assertEqual(eng.calls["shape"], (400, 800))
        np.testing.assert_allclose(out[0, :4], [400, 200, 160, 160])
        np.testing.assert_allclose(out[0, 4:14], np.arange(10) * 40)
        self.assertAlmostEqual(float(out[0, 14]), 0.9, places=5)               # score is not scaled

    def test_small_frames_pass_through_and_no_faces_gives_empty(self):
        eng = self.make(1600)
        out = eng.detect(np.zeros((480, 640, 3), np.uint8))
        self.assertEqual(eng.calls["size"], (640, 480))
        np.testing.assert_allclose(out[0, :4], [100, 50, 40, 40])
        eng.calls["none"] = True
        self.assertEqual(eng.detect(np.zeros((480, 640, 3), np.uint8)).shape, (0, 15))


class AttendanceTests(unittest.TestCase):
    S = 1_000_000.0

    def make(self, **kw):
        s = Settings()
        for k, v in kw.items():
            setattr(s, k, v)
        roster = {i: {"name": f"Student {i}", "reg_no": f"R{i:03d}"} for i in range(1, 8)}
        return AttendanceEngine(s, self.S, 50, 40, roster)

    def sight(self, eng, sid, start, end, step=10):
        t = start
        while t <= end:
            eng.class_sight(sid, self.S + t)
            t += step

    def test_scenarios(self):
        eng = self.make()
        # 1: full attendance with check-in and check-out
        self.assertTrue(eng.gate(1, self.S + 60).accepted)
        self.sight(eng, 1, 60, 3000)
        self.assertTrue(eng.gate(1, self.S + 3120).accepted)
        # 2: passes the gate twice but is hardly in the room
        eng.gate(2, self.S + 30)
        self.sight(eng, 2, 60, 360)
        eng.gate(2, self.S + 3060)
        # 3: in class all along but never checks out
        eng.gate(3, self.S + 20)
        self.sight(eng, 3, 0, 3000)
        # 4: leaves for 12 minutes (longer than the dropout tolerance)
        eng.gate(4, self.S + 20)
        self.sight(eng, 4, 0, 1200)
        self.sight(eng, 4, 1920, 3000)
        eng.gate(4, self.S + 3100)
        # 5: never seen
        # 6: seen the whole time, never checks in, checks out
        self.sight(eng, 6, 100, 3000)
        eng.gate(6, self.S + 3050)
        # 7: 60 s dropouts are bridged
        self.sight(eng, 7, 0, 3000, step=60)
        eng.gate(7, self.S + 5)
        eng.gate(7, self.S + 3200)

        now = self.S + 3300
        eng.finalize(now)
        status = {r["sid"]: r for r in eng.attendance_rows(now)}
        self.assertEqual(status[1]["status"], PRESENT)
        self.assertEqual(status[2]["status"], ABSENT)
        self.assertIn("passed the gate", status[2]["reason"])
        self.assertEqual(status[3]["status"], REVIEW)
        self.assertIn("check-out", status[3]["reason"].lower())
        self.assertEqual(status[4]["status"], ABSENT)
        self.assertEqual(status[5]["status"], ABSENT)
        self.assertEqual(status[5]["reason"], "Not detected")
        self.assertEqual(status[6]["status"], REVIEW)
        self.assertIn("check-in", status[6]["reason"].lower())
        self.assertEqual(status[7]["status"], PRESENT)
        # breaks and time-in-class for student 4
        self.assertEqual(len(eng.recs[4].intervals), 2)
        br = breaks_between(eng.recs[4].intervals, self.S, eng.E)
        self.assertEqual(len(br), 1)
        self.assertAlmostEqual(br[0][1] - br[0][0], 720, delta=15)
        self.assertAlmostEqual(status[4]["present_sec"], 2280, delta=30)

    def test_time_outside_class_window_does_not_count(self):
        eng = self.make()
        self.sight(eng, 1, -500, -10)               # waiting in the room before class
        self.sight(eng, 1, 3100, 3600)              # still there after class ended
        self.assertAlmostEqual(eng.recs[1].present_sec(eng.S, eng.E), 0, delta=1)

    def test_gate_windows(self):
        eng = self.make()
        self.assertEqual(eng.gate_window(self.S - 700), None)
        self.assertEqual(eng.gate_window(self.S - 300), "in")
        self.assertEqual(eng.gate_window(self.S + 1500), None)
        self.assertEqual(eng.gate_window(eng.E - 200), "out")
        self.assertEqual(eng.gate_window(eng.E + 1000), None)
        r = eng.gate(1, self.S + 1500)
        self.assertFalse(r.accepted)
        self.assertIn("check-out opens", r.message)
        self.assertTrue(eng.gate(1, self.S + 10).accepted)
        again = eng.gate(1, self.S + 20)
        self.assertFalse(again.accepted)
        self.assertIn("already", again.message)
        self.assertEqual(eng.gate(99, self.S + 10).kind, "unknown")

    def test_short_class_windows_never_overlap(self):
        s = Settings()
        eng = AttendanceEngine(s, self.S, 5, 4, {1: {"name": "A", "reg_no": "1"}})
        self.assertGreaterEqual(eng.out_open, eng.in_close)

    def test_early_finish_scales_requirement(self):
        eng = self.make()
        eng.gate(1, self.S + 30)
        self.sight(eng, 1, 30, 1500)                # 24.5 min seen, class stopped at minute 25
        now = self.S + 1500
        eng.finalize(now)
        row = [r for r in eng.attendance_rows(now) if r["sid"] == 1][0]
        self.assertEqual(row["status"], PRESENT)    # needs 20 of 25 minutes; check-out not yet possible
        row5 = [r for r in eng.attendance_rows(now) if r["sid"] == 5][0]
        self.assertEqual(row5["status"], ABSENT)

    def test_optional_gate_checks(self):
        eng = self.make(require_checkin=False, require_checkout=False)
        self.sight(eng, 1, 0, 3000)
        status = eng.evaluate(eng.recs[1], self.S + 3300)[0]
        self.assertEqual(status, PRESENT)

    def test_live_projection(self):
        eng = self.make()
        self.sight(eng, 1, 0, 600)
        rows = {r["sid"]: r for r in eng.snapshot(self.S + 600)}
        self.assertEqual(rows[1]["projection"], "Can still qualify")
        self.assertEqual(rows[1]["state"], "In class")
        late = {r["sid"]: r for r in eng.snapshot(self.S + 2900)}
        self.assertEqual(late[1]["projection"], "Cannot qualify")
        self.assertEqual(late[1]["state"], "Out")


class ProctorTests(unittest.TestCase):
    T0 = 5_000.0

    def run_frames(self, eng, seconds, make_tracks, step=0.5, objects_fn=None):
        events = []
        t = 0.0
        while t <= seconds:
            objs = objects_fn(t) if objects_fn else []
            events += eng.process(frame_result(self.T0 + t, make_tracks(t), objs))
            t += step
        return events

    def test_looking_away_episode_and_glance_burst(self):
        eng = ProctorEngine(Settings(), {1: "Asha"})
        # six separate 5 s look-aways, 6 s apart
        events = self.run_frames(eng, 70, lambda t: [tv(1, 1, yaw=55 if (t % 11) < 5 else 0)])
        kinds = [e.type for e in events]
        self.assertEqual(kinds.count("LOOKING_AWAY"), 7)
        self.assertEqual(kinds.count("REPEATED_LOOKING"), 1)      # cooldown stops repeats inside the window

    def test_brief_glance_is_ignored(self):
        eng = ProctorEngine(Settings(), {1: "Asha"})
        events = self.run_frames(eng, 30, lambda t: [tv(1, 1, yaw=60 if 10 <= t < 12 else 0)])
        self.assertEqual(events, [])

    def test_looking_down_at_the_paper_is_normal(self):
        eng = ProctorEngine(Settings(), {1: "Asha"})
        events = self.run_frames(eng, 60, lambda t: [tv(1, 1, pitch=-40)])
        self.assertEqual(events, [])

    def test_face_not_visible_and_return(self):
        eng = ProctorEngine(Settings(), {1: "Asha", 2: "Ben"})
        def tracks(t):
            out = [tv(2, 2)]
            if t < 15 or t > 50:
                out.append(tv(1, 1))
            return out
        events = self.run_frames(eng, 60, tracks)
        missing = [e for e in events if e.type == "FACE_NOT_VISIBLE"]
        self.assertEqual(len(missing), 1)
        self.assertEqual(missing[0].sid, 1)
        row = [r for r in eng.summary(self.T0 + 60) if r["sid"] == 1][0]
        self.assertAlmostEqual(row["missing_sec"], 36, delta=3)

    def test_unknown_person_once_and_staff_ignored(self):
        eng = ProctorEngine(Settings(), {1: "Asha", 9: "Invigilator"}, staff_ids={9})
        def tracks(t):
            return [tv(5, None, votes=4, age=t), tv(6, 9, yaw=70), tv(1, 1)]
        events = self.run_frames(eng, 40, tracks)
        self.assertEqual([e.type for e in events], ["UNKNOWN_PERSON"])
        self.assertFalse(any(r["sid"] == 9 for r in eng.summary(self.T0 + 40)))

    def test_undecided_faces_do_not_trigger_unknown(self):
        eng = ProctorEngine(Settings(), {})
        events = self.run_frames(eng, 40, lambda t: [tv(5, None, votes=1, age=t)])
        self.assertEqual(events, [])

    def test_duplicate_identity(self):
        eng = ProctorEngine(Settings(), {1: "Asha"})
        events = self.run_frames(eng, 20, lambda t: [tv(1, 1, bbox=(100, 100, 60, 60)), tv(2, 1, bbox=(600, 100, 60, 60))])
        self.assertEqual([e.type for e in events].count("DUPLICATE_IDENTITY"), 1)
        self.assertIn(1, eng.active)

    def test_identity_change(self):
        eng = ProctorEngine(Settings(), {1: "Asha", 2: "Ben"})
        self.run_frames(eng, 5, lambda t: [tv(1, 1)])
        ev = eng.process(frame_result(self.T0 + 6, [tv(1, 2)], changes=[(1, 1, 2)]))
        self.assertEqual([e.type for e in ev], ["IDENTITY_CHANGE"])
        self.assertIn("Asha", ev[0].detail)

    def test_prohibited_object_needs_persistence_and_proximity(self):
        eng = ProctorEngine(Settings(), {1: "Asha"})
        near = ObjectDet("cell phone", 0.8, (150, 150, 30, 40))
        far = ObjectDet("cell phone", 0.8, (900, 600, 30, 40))
        def objs(t):
            return [near] if (t % 1.0) == 0 and 5 <= t <= 9 else []
        events = self.run_frames(eng, 15, lambda t: [tv(1, 1)], objects_fn=objs)
        self.assertEqual([e.type for e in events], ["PROHIBITED_OBJECT"])
        eng2 = ProctorEngine(Settings(), {1: "Asha"})
        events = self.run_frames(eng2, 15, lambda t: [tv(1, 1)],
                                 objects_fn=lambda t: [far] if t % 1.0 == 0 else [])
        self.assertEqual(events, [])

    def test_peer_relative_scoring(self):
        eng = ProctorEngine(Settings(), {i: f"S{i}" for i in range(1, 11)})
        def tracks(t):
            out = []
            for sid in range(1, 11):
                yaw = 0.0
                if sid == 1 and (t % 16) < 8:
                    yaw = 60.0                              # student 1 looks away half the time
                out.append(tv(sid, sid, yaw=yaw, bbox=(60.0 * sid, 100, 50, 50)))
            return out
        self.run_frames(eng, 180, tracks)
        ranking = eng.summary(self.T0 + 180)
        self.assertEqual(ranking[0]["sid"], 1)
        self.assertIn(ranking[0]["level"], ("MEDIUM", "HIGH"))
        self.assertTrue(all(r["level"] == "LOW" for r in ranking[1:]))

    def test_room_wide_distraction_does_not_flag_anyone(self):
        eng = ProctorEngine(Settings(), {i: f"S{i}" for i in range(1, 11)})
        def tracks(t):
            yaw = 60.0 if 60 <= t < 90 else 0.0               # everyone turns round together
            return [tv(s, s, yaw=yaw, bbox=(60.0 * s, 100, 50, 50)) for s in range(1, 11)]
        self.run_frames(eng, 180, tracks)
        self.assertTrue(all(r["level"] == "LOW" for r in eng.summary(self.T0 + 180)))

    def test_looking_away_alone_never_reaches_high(self):
        eng = ProctorEngine(Settings(), {i: f"S{i}" for i in range(1, 11)})
        def tracks(t):
            out = []
            for sid in range(1, 11):
                yaw = 60.0 if (sid == 1 and (t % 12) < 10) else 0.0       # student 1 almost always looks away
                out.append(tv(sid, sid, yaw=yaw, bbox=(60.0 * sid, 100, 50, 50)))
            return out
        self.run_frames(eng, 240, tracks)
        top = eng.summary(self.T0 + 240)[0]
        self.assertEqual(top["sid"], 1)
        self.assertGreaterEqual(top["bursts"], 1)                           # the extreme case: bursts count too
        self.assertEqual(top["level"], "MEDIUM")
        self.assertLess(top["score"], 60)

    def test_a_phone_alone_is_medium_and_a_phone_plus_heavy_looking_away_is_high(self):
        near = ObjectDet("cell phone", 0.8, (150, 150, 30, 40))
        def phone(t):
            return [near] if (t % 1.0) == 0 and 5 <= t <= 9 else []
        eng = ProctorEngine(Settings(), {1: "Asha"})
        self.run_frames(eng, 90, lambda t: [tv(1, 1)], objects_fn=phone)
        row = eng.summary(self.T0 + 90)[0]
        self.assertEqual((row["objects"], row["level"]), (1, "MEDIUM"))
        eng2 = ProctorEngine(Settings(), {1: "Asha"})
        self.run_frames(eng2, 90, lambda t: [tv(1, 1, yaw=60 if (t % 12) < 10 else 0)], objects_fn=phone)
        self.assertEqual(eng2.summary(self.T0 + 90)[0]["level"], "HIGH")

    def test_an_identity_flag_alone_is_medium(self):
        eng = ProctorEngine(Settings(), {1: "Asha"})
        self.run_frames(eng, 20, lambda t: [tv(1, 1, bbox=(100, 100, 60, 60)), tv(2, 1, bbox=(600, 100, 60, 60))])
        row = eng.summary(self.T0 + 20)[0]
        self.assertEqual((row["flags"], row["level"]), (1, "MEDIUM"))

    def test_robust_z_is_not_inflated_by_zero_mad(self):
        z = robust_z([0.0] * 9 + [0.1])
        self.assertAlmostEqual(float(z[-1]), 0.1 / 0.03, places=3)


class EnrollmentTests(unittest.TestCase):
    def test_guided_capture_waits_for_quality_and_interval(self):
        engine = FakeEngine({0: unit(1), 1: unit(1)})
        proc = EnrollProcessor(engine, Settings())
        rng = np.random.default_rng(0)
        frame = rng.integers(0, 255, (480, 640, 3), dtype=np.uint8)           # textured = sharp
        engine.rows = [det_row(320, 240, 200)]
        proc.process(frame, 0.0)
        proc.start(3)
        t0 = proc._last
        got = []
        for i in range(1, 40):
            out, _ = proc.process(frame, t0 + i * 0.5)
            if out.sample is not None:
                got.append(out.sample)
        self.assertEqual(len(got), 3)
        self.assertFalse(proc.capturing)
        self.assertEqual(got[0].embedding.shape, (128,))

    def test_hints(self):
        engine = FakeEngine({0: unit(1)})
        proc = EnrollProcessor(engine, Settings())
        frame = np.random.default_rng(0).integers(0, 255, (480, 640, 3), dtype=np.uint8)
        engine.rows = []
        self.assertIn("No face", proc.process(frame, 0.0)[0].hint)
        engine.rows = [det_row(320, 240, 60)]
        self.assertIn("closer", proc.process(frame, 0.0)[0].hint)
        engine.rows = [det_row(200, 240, 200), det_row(500, 240, 190)]
        self.assertIn("one person", proc.process(frame, 0.0)[0].hint)
        engine.rows = [det_row(320, 240, 200)]
        blurry = np.full((480, 640, 3), 120, np.uint8)
        self.assertIn("blurry", proc.process(blurry, 0.0)[0].hint)


class DatabaseAndExportTests(unittest.TestCase):
    def test_full_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            db = Database(Path(d) / "t.db")
            a = db.add_student(reg_no="R1", name="Asha", section="A", consent_at=1.0)
            b = db.add_student(reg_no="R2", name="Ben", section="B")
            inv = db.add_student(reg_no="T1", name="Invigilator", role="staff")
            db.add_sample(a, "faces/a1.jpg", unit(1), 50.0)
            db.add_sample(a, "faces/a2.jpg", unit(2), 60.0)
            db.add_sample(b, "faces/b1.jpg", unit(3), 55.0)
            self.assertEqual(db.sections(), ["A", "B"])
            self.assertEqual([r["reg_no"] for r in db.list_students(role="student")], ["R1", "R2"])
            self.assertEqual(db.list_students(q="ash")[0]["samples"], 2)
            ids, embs = db.embeddings({a})
            self.assertEqual(list(ids), [a, a])
            np.testing.assert_allclose(embs[0], unit(1), atol=1e-6)
            self.assertEqual(len(Gallery.from_db(db, {a, b, inv})), 2)
            with self.assertRaises(Exception):
                db.add_student(reg_no="R1", name="Duplicate")                     # reg_no is unique

            sid = db.create_session("class", "Maths", "A", 1000.0, 50, 40, {"x": 1})
            rows = [dict(sid=a, check_in=1010.0, check_out=3900.0, first_seen=1010.0, last_seen=3890.0,
                         present_sec=2850.0, status="PRESENT", reason="ok"),
                    dict(sid=b, check_in=None, check_out=None, first_seen=None, last_seen=None,
                         present_sec=0.0, status="ABSENT", reason="Not detected")]
            db.save_attendance(sid, rows, {a: [[1010.0, 2000.0], [2700.0, 3890.0]]})
            db.set_override(sid, b, "PRESENT", "Medical room visit")
            rows[1]["status"], rows[1]["reason"] = "ABSENT", "recomputed"
            db.save_attendance(sid, rows, {a: [[1010.0, 3890.0]]})                 # re-save keeps the override
            att = {r["reg_no"]: r for r in db.attendance(sid)}
            self.assertEqual(att["R2"]["status"], "PRESENT")
            self.assertEqual(att["R2"]["reason"], "Medical room visit")
            self.assertEqual(db.intervals(sid)[a], [(1010.0, 3890.0)])
            db.add_event(sid, a, 1500.0, "LOOKING_AWAY", 1, "yaw 55", "evidence/1/x.jpg")
            db.save_risk(sid, [dict(key=f"s{a}", sid=a, name="Asha", score=42.0, level="MEDIUM", glances=3)])
            self.assertEqual(db.risk(sid)[0]["glances"], 3)
            db.finish_session(sid, 4000.0)
            listing = db.list_sessions()[0]
            self.assertEqual((listing["n_present"], listing["n_total"], listing["n_alerts"]), (2, 2, 1))

            out = Path(d)
            export_attendance_csv(db, sid, out / "att.csv")
            export_events_csv(db, sid, out / "ev.csv")
            export_risk_csv(db, sid, out / "risk.csv")

            def read(name):
                with open(out / name, encoding="utf-8-sig") as fh:
                    return list(csv.reader(fh))
            lines = read("att.csv")
            self.assertEqual(lines[2][0], "Reg. no")
            self.assertEqual(lines[3][0:3], ["R1", "Asha", "PRESENT"])
            self.assertEqual(len(read("ev.csv")), 2)
            self.assertEqual(read("risk.csv")[1][0], "Asha")

            paths = db.delete_student(a)
            self.assertEqual(sorted(paths), ["faces/a1.jpg", "faces/a2.jpg"])
            self.assertEqual(len(db.attendance(sid)), 1)                         # cascade removed Asha's row
            self.assertEqual(db.stats()["students"], 1)
            db.close()


class InterruptedSessionTests(unittest.TestCase):
    def test_sessions_left_running_are_relabelled_at_startup(self):
        with tempfile.TemporaryDirectory() as d:
            db = Database(Path(d) / "t.db")
            a = db.add_student(reg_no="R1", name="Asha")
            cut_short = db.create_session("class", "Cut short", None, 1000.0, 50, 40)
            fine = db.create_session("class", "Fine", None, 5000.0, 50, 40)
            db.finish_session(fine, 8000.0)
            db.save_attendance(cut_short, [dict(sid=a, check_in=1010.0, check_out=None, first_seen=1010.0,
                                                last_seen=2500.0, present_sec=1490.0, status="REVIEW", reason="x")],
                               {a: [[1010.0, 2500.0]]})
            self.assertEqual(db.mark_interrupted(), 1)
            self.assertEqual(db.get_session(cut_short)["status"], "interrupted")
            self.assertEqual(db.get_session(cut_short)["ended_ts"], 2500.0)       # last time anyone was seen
            self.assertEqual(db.get_session(fine)["status"], "finished")
            self.assertEqual(db.get_session(fine)["ended_ts"], 8000.0)
            self.assertEqual(db.mark_interrupted(), 0)                            # nothing left to relabel
            rows = {r["id"]: r for r in db.list_sessions()}
            self.assertEqual(rows[cut_short]["n_total"], 1)                       # its autosaved rows are kept
            db.close()


class SettingsHardeningTests(unittest.TestCase):
    """A settings file that was edited by hand or damaged must never break the app."""

    def load(self, text):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "s.json"
            p.write_text(text, encoding="utf-8")
            return load_settings(p)

    def test_contradictory_values_are_made_usable(self):
        s = self.load('{"vote_window": 3, "vote_required": 9, "enroll_samples": 4, "enroll_min_samples": 9}')
        self.assertEqual((s.vote_window, s.vote_required), (3, 3))          # 9 votes out of 3 could never be reached
        self.assertEqual((s.enroll_samples, s.enroll_min_samples), (4, 4))
        s = self.load('{"vote_window": 0, "vote_required": 0}')
        self.assertEqual((s.vote_window, s.vote_required), (1, 1))

    def test_odd_json_gives_defaults_instead_of_errors(self):
        self.assertEqual(self.load("[1, 2, 3]"), Settings())
        self.assertEqual(self.load('"just text"'), Settings())
        self.assertEqual(self.load('"class_duration_min"'), Settings())      # a bare string that happens to contain a key
        self.assertEqual(self.load("not json at all {"), Settings())
        self.assertEqual(self.load(""), Settings())
        s = self.load('{"class_duration_min": Infinity, "recog_threshold": NaN, "classroom_source": null}')
        self.assertEqual(s.class_duration_min, Settings().class_duration_min)
        self.assertEqual(s.classroom_source, "0")                            # null is not the text "None"

    def test_a_failed_save_leaves_the_old_file_intact(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "s.json"
            a = Settings()
            a.min_presence_min = 31
            save_settings(a, p)
            b = Settings()
            b.min_presence_min = 22
            with mock.patch("app.config.os.replace", side_effect=OSError("disk full")):
                with self.assertRaises(OSError):
                    save_settings(b, p)
            self.assertEqual(load_settings(p).min_presence_min, 31)          # still the old, complete file
            save_settings(b, p)
            self.assertEqual(load_settings(p).min_presence_min, 22)
            self.assertEqual([f.name for f in Path(d).iterdir()], ["s.json"])   # no temp file left behind


class DataSafetyTests(unittest.TestCase):
    def test_registration_numbers_ignore_case(self):
        with tempfile.TemporaryDirectory() as d:
            db = Database(Path(d) / "t.db")
            db.add_student(reg_no="21cs001", name="Asha")
            with self.assertRaises(sqlite3.IntegrityError):
                db.add_student(reg_no="21CS001", name="Asha again")
            self.assertEqual(db.get_by_reg("21CS001")["name"], "Asha")
            self.assertEqual(db.conn.execute("PRAGMA user_version").fetchone()[0], 1)
            db.close()

    def test_an_older_database_with_case_sensitive_numbers_is_still_found_in_any_case(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "old.db"
            old_schema = [s for s in __import__("app.db", fromlist=["SCHEMA"]).SCHEMA.split(";")
                          if "CREATE TABLE IF NOT EXISTS students" in s][0].replace(" COLLATE NOCASE", "")
            raw = sqlite3.connect(str(path))
            raw.execute(old_schema)
            raw.execute("INSERT INTO students (reg_no, name, created_at) VALUES ('R1', 'Old record', 1.0)")
            raw.commit()
            raw.close()
            db = Database(path)
            self.assertEqual(db.get_by_reg("r1")["name"], "Old record")
            db.close()

    def test_slug_is_safe_and_short(self):
        self.assertEqual(slug("A/B..C"), "A_B_C")
        self.assertEqual(slug("../../etc/passwd"), "etc_passwd")
        self.assertEqual(slug("   "), "student")
        self.assertEqual(slug("\u0930\u093e\u0939\u0941\u0932"), "student")       # a name with no ASCII letters
        long = slug("x" * 300)
        self.assertLessEqual(len(long), 40)
        self.assertFalse(slug("a" * 39 + " b").endswith("_"))

    def make_samples(self, n, base=0):
        return [Sample(np.full((40, 40, 3), 30 + base + i, np.uint8), unit(base + i), 50.0) for i in range(n)]

    def test_saving_photos_never_overwrites_an_existing_one(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            db = Database(root / "t.db")
            sid = db.add_student(reg_no="R1", name="Asha")
            with mock.patch.object(enrollment_mod, "DATA_DIR", root), \
                    mock.patch.object(enrollment_mod, "FACES_DIR", root / "faces"):
                save_samples(db, sid, "R1", "Asha", self.make_samples(3), start_index=1)
                rows = db.samples(sid)
                self.assertEqual(len(rows), 3)
                kept = {r["image_path"]: (root / r["image_path"]).read_bytes() for r in rows}
                # Photo 2 is deleted by the user: 2 photos remain, so "the next number" is 3, which is taken.
                gone = rows[1]
                db.delete_sample(gone["id"])
                (root / gone["image_path"]).unlink()
                save_samples(db, sid, "R1", "Asha", self.make_samples(2, base=10), start_index=len(db.samples(sid)) + 1)
                rows = db.samples(sid)
                paths = [r["image_path"] for r in rows]
                self.assertEqual(len(rows), 4)
                self.assertEqual(len(set(paths)), 4)                         # four different files
                for rel, data in kept.items():                               # the old photos are untouched
                    if rel != gone["image_path"]:
                        self.assertEqual((root / rel).read_bytes(), data)
                self.assertTrue(all((root / p_).exists() for p_ in paths))
            db.close()

    def test_a_photo_that_cannot_be_written_is_an_error_not_a_silent_gap(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            db = Database(root / "t.db")
            sid = db.add_student(reg_no="R1", name="Asha")
            with mock.patch.object(enrollment_mod, "DATA_DIR", root), \
                    mock.patch.object(enrollment_mod, "FACES_DIR", root / "faces"), \
                    mock.patch.object(enrollment_mod, "write_image", return_value=False):
                with self.assertRaises(OSError):
                    save_samples(db, sid, "R1", "Asha", self.make_samples(1))
            self.assertEqual(db.samples(sid), [])                            # nothing half-recorded
            db.close()

    def test_deleting_a_person_removes_the_folder_even_after_the_registration_number_changed(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            faces = root / "faces"
            with mock.patch.object(enrollment_mod, "DATA_DIR", root), mock.patch.object(enrollment_mod, "FACES_DIR", faces):
                folder = faces / "00001_OLDREG"
                folder.mkdir(parents=True)
                (folder / "a.jpg").write_bytes(b"x")
                (folder / "b.jpg").write_bytes(b"y")
                (root / "keep.txt").write_text("not a photo")
                delete_student_files(["faces/00001_OLDREG/a.jpg", "faces/00001_OLDREG/b.jpg"], 1, "NEWREG")
                self.assertFalse(folder.exists())
                self.assertTrue(faces.exists())
                self.assertTrue((root / "keep.txt").exists())
                (root / "keep.txt").unlink()
            # A stray path that points straight into the data folder must never remove the data folder itself,
            # even when deleting that file leaves it empty.
            lonely = root / "data2"
            lonely.mkdir()
            (lonely / "stray.txt").write_text("x")
            with mock.patch.object(enrollment_mod, "DATA_DIR", lonely), \
                    mock.patch.object(enrollment_mod, "FACES_DIR", lonely / "faces"):
                delete_student_files(["stray.txt"], 2, "R2")
            self.assertTrue(lonely.exists())
            self.assertFalse((lonely / "stray.txt").exists())

    def test_exports_do_not_run_names_as_formulas(self):
        self.assertEqual(safe_cell("=1+1"), "'=1+1")
        self.assertEqual(safe_cell("+44 20"), "'+44 20")
        self.assertEqual(safe_cell("-2+3"), "'-2+3")
        self.assertEqual(safe_cell("@SUM(A1)"), "'@SUM(A1)")
        self.assertEqual(safe_cell("\tcmd"), "'\tcmd")
        self.assertEqual(safe_cell("Asha"), "Asha")
        self.assertEqual(safe_cell("21CS001"), "21CS001")
        self.assertEqual(safe_cell("-"), "-")                                # the 'nothing here' mark stays as is
        self.assertEqual(safe_cell(12.5), 12.5)
        self.assertIsNone(safe_cell(None))
        with tempfile.TemporaryDirectory() as d:
            db = Database(Path(d) / "t.db")
            evil = db.add_student(reg_no="=cmd|' /C calc'!A0", name='=HYPERLINK("http://example.com","click")')
            ok = db.add_student(reg_no="R2", name="Ben")
            sid = db.create_session("exam", "=Midterm", None, 1000.0, 50, 40)
            db.save_attendance(sid, [
                dict(sid=evil, check_in=None, check_out=None, first_seen=None, last_seen=None, present_sec=0.0,
                     status="ABSENT", reason="@not a formula"),
                dict(sid=ok, check_in=None, check_out=None, first_seen=None, last_seen=None, present_sec=0.0,
                     status="ABSENT", reason="Not detected")], {})
            db.add_event(sid, evil, 1500.0, "LOOKING_AWAY", 1, "+detail", "")
            db.save_risk(sid, [dict(key="s1", sid=evil, name="-1+1", score=5.0, level="LOW")])
            out = Path(d)
            export_attendance_csv(db, sid, out / "a.csv")
            export_events_csv(db, sid, out / "e.csv")
            export_risk_csv(db, sid, out / "r.csv")
            for name in ("a.csv", "e.csv", "r.csv"):
                with open(out / name, encoding="utf-8-sig", newline="") as fh:
                    for row in csv.reader(fh):
                        for cell in row:
                            self.assertFalse(cell.startswith(("=", "+", "@", "\t", "\r")), (name, cell))
                            self.assertFalse(cell.startswith("-") and cell != "-", (name, cell))
            with open(out / "a.csv", encoding="utf-8-sig", newline="") as fh:
                rows = list(csv.reader(fh))
            self.assertEqual(rows[0][1], "'=Midterm")
            bad = [r for r in rows if r and r[0].startswith("'=cmd")][0]
            self.assertEqual(bad[1], "'=HYPERLINK(\"http://example.com\",\"click\")")
            self.assertIn("Ben", [r[1] for r in rows if len(r) > 1])         # ordinary rows are not touched
            db.close()


class RequirementCannotExceedTheClassTests(unittest.TestCase):
    def test_minimum_longer_than_the_class_means_the_whole_class(self):
        s = Settings()
        s.require_checkin = s.require_checkout = False
        eng = AttendanceEngine(s, 1000.0, 30, 45, {1: {"name": "Asha", "reg_no": "R1"}})
        for t in range(0, 1801, 10):
            eng.class_sight(1, 1000.0 + t)
        eng.finalize(1000.0 + 1800)
        self.assertEqual(eng.evaluate(eng.recs[1], 0)[0], PRESENT)           # 30 of 30 minutes, not "needs 45m"
        self.assertEqual(eng.need, 1800.0)


class ObjectDetectorFailureTests(unittest.TestCase):
    def test_a_broken_detector_is_switched_off_and_the_user_is_told_once(self):
        class Broken:
            def detect(self, frame):
                raise RuntimeError("out of memory")
        engine = FakeEngine({0: unit(1)})
        pipe = VisionPipeline(engine, Gallery(np.array([1]), unit(1).reshape(1, -1)), Settings(), objects=Broken())
        engine.rows = [det_row(100, 300, 100)]
        frame = np.zeros((H, W, 3), np.uint8)
        with self.assertLogs("app.vision.pipeline", level="ERROR"):         # the failure is also written to the log
            res = pipe.process(frame, 100.0)
        self.assertEqual(len(res.notes), 1)
        self.assertIn("out of memory", res.notes[0])
        self.assertIsNone(pipe.objects)
        self.assertEqual(pipe.process(frame, 102.0).notes, [])               # told once, not every frame


if __name__ == "__main__":
    unittest.main()
