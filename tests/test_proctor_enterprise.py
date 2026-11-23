"""Tests for the advanced AI-Powered Smart Exam Proctoring System."""
import os
import tempfile
import unittest
from pathlib import Path

import numpy as np

from app.config import Settings
from app.db import Database
from app.services.proctor import EVENT_INFO, Event, ProctorEngine
from app.ui.proctor_dialogs import generate_proctoring_html_report
from app.vision.types import FrameResult, ObjectDet, TrackView


def unit(val: float = 1.0) -> np.ndarray:
    v = np.zeros(128, np.float32)
    v[0] = val
    return v


def make_track(tid: int, sid=None, yaw=0.0, pitch=0.0, mouth_open=0.0, votes=5):
    return TrackView(
        track_id=tid,
        bbox=(100.0, 100.0, 60.0, 60.0),
        sid=sid,
        score=0.85,
        visible=True,
        face_ratio=0.1,
        yaw=yaw,
        pitch=pitch,
        roll=0.0,
        age=60.0,
        votes=votes,
        live_ok=True,
        last_seen=0.0,
        mouth_open=mouth_open,
    )


class ProctorEnterpriseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.db = Database(self.tmp.name)

    def tearDown(self):
        self.db.close()
        try:
            os.unlink(self.tmp.name)
        except OSError:
            pass

    def test_database_event_review_columns(self):
        sid = self.db.add_student(reg_no="12404519", name="Abhishek Kumar")
        sess_id = self.db.create_session("exam", "AI Midterm", None, 1000.0, 60, 45)

        # Add event with custom confidence and review status
        eid = self.db.add_event(
            session_id=sess_id,
            student_id=sid,
            ts=1050.0,
            type_="PROHIBITED_OBJECT",
            severity=3,
            detail="cell phone (96%) near this student",
            snapshot="evidence/1/phone.jpg",
            confidence=0.96,
            score_weight=35.0,
            review_status="Pending Review",
            admin_remarks="Flagged automatically by YOLO detector",
        )
        self.assertGreater(eid, 0)

        ev = self.db.get_event(eid)
        self.assertIsNotNone(ev)
        self.assertEqual(ev["type"], "PROHIBITED_OBJECT")
        self.assertEqual(ev["confidence"], 0.96)
        self.assertEqual(ev["score_weight"], 35.0)
        self.assertEqual(ev["review_status"], "Pending Review")
        self.assertIn("YOLO", ev["admin_remarks"])

        # Update review status
        self.db.update_event_review(eid, "Confirmed Concern", "Invigilator verified cell phone in hand at 10:17")
        updated = self.db.get_event(eid)
        self.assertEqual(updated["review_status"], "Confirmed Concern")
        self.assertIn("verified cell phone", updated["admin_remarks"])

    def test_proctor_engine_5_tier_scoring(self):
        s = Settings()
        eng = ProctorEngine(s, {1: "Student 1"})

        # Normal activity
        eng.process(FrameResult(100.0, 1280, 720, [make_track(1, 1)]))
        summary = eng.summary(105.0)
        self.assertEqual(len(summary), 1)
        self.assertEqual(summary[0]["suspicion_level"], "Normal")
        self.assertLess(summary[0]["score"], 20.0)
        self.assertEqual(summary[0]["color"], "#22c55e")

    def test_proctor_engine_talking_detection(self):
        s = Settings(detect_talking=True)
        eng = ProctorEngine(s, {1: "Student 1"})

        # Oscillating mouth open/close to simulate speaking
        events = []
        for i in range(20):
            ts = 100.0 + i * 0.2
            mouth_val = 0.35 if (i % 2 == 0) else 0.15
            tr = make_track(1, 1, mouth_open=mouth_val)
            ev = eng.process(FrameResult(ts, 1280, 720, [tr]))
            events.extend(ev)

        talking_events = [e for e in events if e.type == "SUSPECTED_TALKING"]
        self.assertGreaterEqual(len(talking_events), 1)
        self.assertEqual(talking_events[0].severity, 2)
        self.assertEqual(talking_events[0].score_weight, float(s.weight_talking))
        self.assertIn("lip movement", talking_events[0].detail)

    def test_proctor_engine_camera_obstruction_detection(self):
        s = Settings(detect_obstruction=True)
        eng = ProctorEngine(s, {})

        dark_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        events = []
        for i in range(10):
            ts = 200.0 + i * 0.5
            ev = eng.process(FrameResult(ts, 640, 480, [], frame=dark_frame))
            events.extend(ev)

        obstruction_events = [e for e in events if e.type == "CAMERA_OBSTRUCTED"]
        self.assertGreaterEqual(len(obstruction_events), 1)
        self.assertEqual(obstruction_events[0].severity, 3)
        self.assertEqual(obstruction_events[0].score_weight, float(s.weight_obstruction))

    def test_proctor_engine_multiple_faces_when_enabled(self):
        s = Settings(detect_multiple_faces=True)
        eng = ProctorEngine(s, {1: "Student 1", 2: "Student 2"})

        tr1 = make_track(1, 1)
        tr2 = make_track(2, 2)
        events = eng.process(FrameResult(300.0, 1280, 720, [tr1, tr2]))

        multi = [e for e in events if e.type == "MULTIPLE_FACES"]
        self.assertEqual(len(multi), 1)
        self.assertEqual(multi[0].severity, 4)
        self.assertEqual(multi[0].score_weight, float(s.weight_multiple_faces))

    def test_generate_html_report(self):
        sid = self.db.add_student(reg_no="12404519", name="Abhishek Kumar")
        sess_id = self.db.create_session("exam", "End Term Examination", None, 1000.0, 60, 45)
        self.db.save_attendance(sess_id, [
            dict(sid=sid, check_in=1005.0, check_out=1055.0, first_seen=1005.0, last_seen=1055.0,
                 present_sec=3000.0, status="PRESENT", reason="Complete attendance")
        ], {sid: [[1005.0, 1055.0]]})

        self.db.add_event(sess_id, sid, 1020.0, "LOOKING_AWAY", 1, "head turned +55 deg (right)", "")
        self.db.save_risk(sess_id, [
            dict(key=f"s{sid}", sid=sid, name="Abhishek Kumar", score=15.0, level="LOW",
                 suspicion_level="Normal", color="#16a34a", glances=1, missing_sec=0, objects=0, flags=0)
        ])

        report = generate_proctoring_html_report(self.db, sess_id)
        self.assertIn("End Term Examination", report)
        self.assertIn("Abhishek Kumar", report)
        self.assertIn("12404519", report)
        self.assertIn("Looking Away", report)
        self.assertIn("ClassVision AI – Examination Proctoring Report", report)


if __name__ == "__main__":
    unittest.main()
