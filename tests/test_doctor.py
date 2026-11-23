"""scripts/doctor.py, the first-run check. Uses a fake face engine and a generated video file, so it needs
no camera and no models.   Run from the project root:   python -m unittest discover -s tests -v
"""
import contextlib
import importlib.util
import io
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.db import Database                 # noqa: E402
from app.vision.pose import project_model   # noqa: E402


def load_doctor():
    spec = importlib.util.spec_from_file_location("doctor_script", ROOT / "scripts" / "doctor.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fingerprint(seed=7):
    v = np.random.default_rng(seed).normal(size=128).astype(np.float32)
    return v / np.linalg.norm(v)


class FakeEngine:
    """One frontal face, 30% of the frame wide, always the same fingerprint."""
    faces = True

    def __init__(self, *args, **kwargs):
        pass

    def detect(self, frame):
        if not FakeEngine.faces:
            return np.zeros((0, 15), np.float32)
        h, w = frame.shape[:2]
        size = w * 0.3
        lm = project_model(0, 0, w, h, depth_mm=w * 63.0 / (size * 0.45), center=(w / 2, h / 2))
        row = np.concatenate([[w / 2 - size / 2, h / 2 - size / 2, size, size], lm.reshape(-1), [0.95]])
        return row.astype(np.float32).reshape(1, 15)

    def embed(self, frame, row):
        return fingerprint()


class DoctorTests(unittest.TestCase):
    def setUp(self):
        FakeEngine.faces = True
        self.doctor = load_doctor()
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.video = str(self.dir / "clip.avi")
        writer = cv2.VideoWriter(self.video, cv2.VideoWriter_fourcc(*"MJPG"), 10, (640, 480))
        if not writer.isOpened():
            self.skipTest("this OpenCV build cannot write a test video")
        rng = np.random.default_rng(0)
        for _ in range(12):
            writer.write(rng.integers(0, 255, (480, 640, 3), dtype=np.uint8))
        writer.release()

    def tearDown(self):
        self.tmp.cleanup()

    def run_doctor(self, argv, models_missing=(), engine=FakeEngine):
        out = io.StringIO()
        patches = [mock.patch("app.vision.models.missing_models", return_value=list(models_missing)),
                   mock.patch("app.vision.engine.FaceEngine", engine),
                   mock.patch.dict(sys.modules, {"PySide6": types.ModuleType("PySide6")})]
        with contextlib.ExitStack() as stack, contextlib.redirect_stdout(out):
            for p in patches:
                stack.enter_context(p)
            rc = self.doctor.main(argv, db_path=self.dir / "t.db")
        return rc, out.getvalue()

    def test_full_run_recognises_an_enrolled_student(self):
        db = Database(self.dir / "t.db")
        sid = db.add_student(reg_no="R7", name="Asha")
        db.add_sample(sid, "faces/a.jpg", fingerprint(), 50.0)
        db.close()
        rc, text = self.run_doctor([self.video])
        self.assertEqual(rc, 0, text)
        self.assertIn("Found 1 face", text)
        self.assertIn("Head pose of the largest face: yaw +0", text)
        self.assertIn("big enough to count as 'standing at the gate'", text)
        self.assertIn("Recognised as Asha (R7)", text)
        self.assertNotIn("[FAIL]", text)

    def test_unknown_face_and_nobody_enrolled(self):
        rc, text = self.run_doctor([self.video])
        self.assertEqual(rc, 0, text)
        self.assertIn("No one is enrolled yet", text)
        db = Database(self.dir / "t.db")
        sid = db.add_student(reg_no="R1", name="Someone Else")
        db.add_sample(sid, "faces/x.jpg", fingerprint(99), 50.0)
        db.close()
        rc, text = self.run_doctor([self.video])
        self.assertEqual(rc, 0, text)
        self.assertIn("matches no enrolled student", text)

    def test_no_face_is_a_warning_not_a_failure(self):
        FakeEngine.faces = False
        rc, text = self.run_doctor([self.video])
        self.assertEqual(rc, 0, text)
        self.assertIn("[warn] No face found", text)

    def test_missing_models_stop_early_with_the_fix(self):
        rc, text = self.run_doctor([self.video], models_missing=["m.onnx"])
        self.assertEqual(rc, 1)
        self.assertIn("python scripts/download_models.py", text)
        self.assertNotIn("Found", text)

    def test_unreadable_source_fails_with_hints(self):
        rc, text = self.run_doctor([str(self.dir / "does_not_exist.mp4")])
        self.assertEqual(rc, 1)
        self.assertIn("Cannot read frames", text)
        self.assertIn("video file path", text)

    def test_a_broken_detector_is_reported_not_raised(self):
        class Broken(FakeEngine):
            def detect(self, frame):
                raise RuntimeError("model file is corrupt")
        rc, text = self.run_doctor([self.video], engine=Broken)
        self.assertEqual(rc, 1)
        self.assertIn("face detector could not run: model file is corrupt", text)


if __name__ == "__main__":
    unittest.main()
