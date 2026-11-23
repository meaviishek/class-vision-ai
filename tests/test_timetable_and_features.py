"""Tests for Timetable management, 1-photo enrollment, instruction logging, and SQLite storage."""
from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path

import numpy as np

from app.config import Settings
from app.context import AppContext
from app.db import DEFAULT_TIMETABLE, Database
from app.workers.session import SessionConfig, SessionController


class TimetableDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "test.db"
        self.db = Database(self.db_path)

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_default_timetable_is_seeded_by_default(self):
        slots = self.db.list_timetable()
        self.assertEqual(len(slots), len(DEFAULT_TIMETABLE))
        # Verify specific slots from the timetable image
        mon_slots = self.db.list_timetable(day_of_week="Monday")
        self.assertEqual(len(mon_slots), 7)
        self.assertEqual(mon_slots[0]["subcode"], "PEA306")
        self.assertEqual(mon_slots[0]["room"], "37-603")
        self.assertEqual(mon_slots[0]["section"], "K3P24WX")
        self.assertEqual(mon_slots[1]["subcode"], "CSE471")
        self.assertEqual(mon_slots[5]["subcode"], "CSE408")

    def test_add_and_get_timetable_slot_with_subcode(self):
        slot_id = self.db.add_timetable_entry(
            day_of_week="Monday",
            subcode="CSE408",
            subject="Artificial Intelligence",
            section="K3P24WX",
            teacher="Dr. Sharma",
            room="28-502",
            start_time="15:20",
            end_time="16:10",
            duration_min=50,
            min_presence_min=40,
            camera_source="0",
            notes="Lecture"
        )
        self.assertGreater(slot_id, 0)
        row = self.db.get_timetable_entry(slot_id)
        self.assertIsNotNone(row)
        self.assertEqual(row["day_of_week"], "Monday")
        self.assertEqual(row["subcode"], "CSE408")
        self.assertEqual(row["subject"], "Artificial Intelligence")
        self.assertEqual(row["section"], "K3P24WX")
        self.assertEqual(row["teacher"], "Dr. Sharma")
        self.assertEqual(row["room"], "28-502")
        self.assertEqual(row["start_time"], "15:20")
        self.assertEqual(row["end_time"], "16:10")

    def test_update_and_delete_timetable_slot(self):
        slot_id = self.db.add_timetable_entry(
            day_of_week="Tuesday",
            subcode="CSE472",
            subject="Big Data Analytics",
            section="K3P24WX",
            start_time="10:20",
            end_time="11:10"
        )
        self.db.update_timetable_entry(slot_id, room="37-701", duration_min=60, subcode="CSE472-LAB")
        row = self.db.get_timetable_entry(slot_id)
        self.assertEqual(row["room"], "37-701")
        self.assertEqual(row["duration_min"], 60)
        self.assertEqual(row["subcode"], "CSE472-LAB")

        self.db.delete_timetable_entry(slot_id)
        self.assertIsNone(self.db.get_timetable_entry(slot_id))

    def test_reset_default_timetable(self):
        # Delete one slot
        first_id = self.db.list_timetable()[0]["id"]
        self.db.delete_timetable_entry(first_id)
        self.assertEqual(len(self.db.list_timetable()), len(DEFAULT_TIMETABLE) - 1)

        # Force re-seed
        reseeded = self.db.seed_default_timetable(force=True)
        self.assertEqual(reseeded, len(DEFAULT_TIMETABLE))
        self.assertEqual(len(self.db.list_timetable()), len(DEFAULT_TIMETABLE))


class StudentEnrollmentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "test.db"
        self.db = Database(self.db_path)

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_student_and_single_sample_stored_in_sqlite(self):
        sid = self.db.add_student(
            reg_no="12404519",
            name="Abhishek Kumar",
            role="student",
            section="K3P24WX",
            department="CSE",
            course="CSE",
            year="5",
            email="meaviishek@gmail.com",
            phone="8409031739",
            notes="Enrolled with 1 photo",
            consent_at=time.time()
        )
        self.assertGreater(sid, 0)
        student = self.db.get_student(sid)
        self.assertEqual(student["reg_no"], "12404519")
        self.assertEqual(student["name"], "Abhishek Kumar")
        self.assertIsNotNone(student["consent_at"])

        # Add single face sample
        dummy_emb = np.ones((128,), dtype=np.float32)
        dummy_emb /= np.linalg.norm(dummy_emb)
        samp_id = self.db.add_sample(sid, "faces/test.jpg", dummy_emb, quality=55.0)
        self.assertGreater(samp_id, 0)

        samples = self.db.samples(sid)
        self.assertEqual(len(samples), 1)
        self.assertEqual(samples[0]["image_path"], "faces/test.jpg")


class InstructionLoggingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "test.db"
        self.db = Database(self.db_path)

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_instruction_events_stored_in_sqlite(self):
        sess_id = self.db.create_session("class", "AI Lecture", "K3P24WX", time.time(), 50, 40)
        self.db.add_event(sess_id, None, time.time(), "INSTRUCTION", 1, "Please open Chapter 4", "")
        self.db.add_event(sess_id, None, time.time(), "INSTRUCTION", 1, "Lab assignment started", "")

        events = self.db.events(sess_id)
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]["detail"], "Please open Chapter 4")
        self.assertEqual(events[0]["type"], "INSTRUCTION")
        self.assertEqual(events[1]["detail"], "Lab assignment started")


if __name__ == "__main__":
    unittest.main()
