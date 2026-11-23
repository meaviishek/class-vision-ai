"""Builds the real main window and pushes data through every page. Needs PySide6 (skipped without it).

Uses the offscreen Qt platform, so it also runs on a machine with no display.
Run from the project root:   python -m unittest discover -s tests -v
"""
import importlib.util
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402

HAVE_QT = importlib.util.find_spec("PySide6") is not None
if HAVE_QT:
    import PySide6
    from PySide6.QtWidgets import QApplication

    from app.config import Settings
    from app.context import AppContext
    from app.services.attendance import AttendanceEngine
    from app.ui import main_window as main_window_mod
    from app.ui.main_window import MainWindow
    from app.ui.pages import settings as settings_page
    from app.ui.theme import apply_theme
    STUB = getattr(PySide6, "__stub__", False)        # True only for the author's dry-run stand-in

S = 1_000_000.0


def unit(seed):
    v = np.random.default_rng(seed).normal(size=128).astype(np.float32)
    return v / np.linalg.norm(v)


@unittest.skipUnless(HAVE_QT, "PySide6 is not installed")
class UiSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        apply_theme(cls.app)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ctx = AppContext(Path(self.tmp.name) / "t.db", Path(self.tmp.name) / "s.json")

    def tearDown(self):
        self.ctx.db.close()
        self.tmp.cleanup()

    def seed(self):
        db = self.ctx.db
        a = db.add_student(reg_no="R1", name="Asha", section="A", consent_at=time.time())
        b = db.add_student(reg_no="R2", name="Ben", section="A")
        db.add_sample(a, "faces/a.jpg", unit(1), 50.0)
        db.add_sample(b, "faces/b.jpg", unit(2), 50.0)
        sid = db.create_session("exam", "Midterm", "A", S, 50, 40)
        db.save_attendance(sid, [
            dict(sid=a, check_in=S + 30, check_out=S + 3000, first_seen=S + 30, last_seen=S + 2990,
                 present_sec=2900.0, status="PRESENT", reason="ok"),
            dict(sid=b, check_in=None, check_out=None, first_seen=None, last_seen=None, present_sec=0.0,
                 status="ABSENT", reason="Not detected")], {a: [[S + 30, S + 1500], [S + 1800, S + 2990]]})
        db.add_event(sid, a, S + 500, "LOOKING_AWAY", 1, "head turned +55 deg", "")
        db.save_risk(sid, [dict(key=f"s{a}", sid=a, name="Asha", score=42.0, level="MEDIUM", away_pct=18.0,
                                glances=4, bursts=1, missing_sec=0, objects=0, flags=0)])
        db.finish_session(sid, S + 3100)
        return a, b, sid

    def test_every_page_opens(self):
        win = MainWindow(self.ctx)
        for key in ("dashboard", "timetable", "class", "exam", "enroll", "students", "reports", "settings", "dashboard"):
            win.go(key)
        win.close()

    def test_every_page_sits_in_a_scroll_area_so_small_screens_can_scroll(self):
        win = MainWindow(self.ctx)
        self.assertEqual(set(win.areas), set(win.pages))
        if not STUB:                                   # the wrapping itself can only be checked with real widgets
            from PySide6.QtWidgets import QScrollArea
            for key, area in win.areas.items():
                self.assertIsInstance(area, QScrollArea)
                self.assertIs(area.widget(), win.pages[key])
                self.assertTrue(area.widgetResizable())
            self.assertLessEqual(win.minimumWidth(), 900)
            self.assertLessEqual(win.minimumHeight(), 560)
        win.close()

    def test_pages_show_data(self):
        a, b, sid = self.seed()
        self.ctx.students_changed.emit()
        self.ctx.sessions_changed.emit()
        win = MainWindow(self.ctx)

        reports = win.pages["reports"]
        reports.refresh()
        reports._load(sid)
        reports.att.selectRow(0)
        reports._on_student_selected()

        live = win.pages["exam"]
        eng = AttendanceEngine(Settings(), S, 50, 40, {a: {"name": "Asha", "reg_no": "R1"},
                                                       b: {"name": "Ben", "reg_no": "R2"}})
        eng.gate(a, S + 20)
        for t in range(0, 1500, 10):
            eng.class_sight(a, S + t)
        live._on_attendance(eng.snapshot(S + 1500))
        live._on_alert(dict(ts=S + 500, type="LOOKING_AWAY", label="Looking away", severity=1, name="Asha",
                            detail="head turned +55 deg", snapshot=""))
        live._on_risk([dict(key="s1", sid=a, name="Asha", score=42.0, level="MEDIUM", away_pct=18.0, glances=4,
                            bursts=1, missing_sec=0, objects=0, flags=0)])
        live._on_tick(eng.timing(S + 1500))
        live._on_gate_msg("ok", "Asha: checked in")
        live._on_gate_msg("info", "ignored while the success message is held")

        if not STUB:                                   # row counts only mean something with real widgets
            self.assertEqual(win.pages["students"].table.rowCount(), 2)
            self.assertEqual(reports.sessions.rowCount(), 1)
            self.assertEqual(reports.att.rowCount(), 2)
            self.assertEqual(reports.alerts.rowCount(), 1)
            self.assertEqual(live.table.rowCount(), 2)
        win.close()

    def test_enroll_page_collects_and_clears_samples(self):
        from app.services.enrollment import Sample
        win = MainWindow(self.ctx)
        page = win.pages["enroll"]
        for i in range(3):
            page._add_sample(Sample(np.full((60, 60, 3), 100 + i, np.uint8), unit(i), 55.0))
        if not STUB:
            self.assertEqual(len(page.samples), 3)
        page.clear_form()
        self.assertEqual(len(page.samples), 0)
        win.close()

    def test_settings_spec_defaults_fit_their_ranges(self):
        defaults = Settings()
        for _, rows in settings_page.SPEC:
            for key, caption, kind, lo, hi, step, tip in rows:
                value = getattr(defaults, key)
                if kind in ("int", "float"):
                    self.assertTrue(lo <= value <= hi, f"{key}={value} outside {lo}..{hi}")

    @unittest.skipIf(HAVE_QT and STUB, "needs real widgets")
    def test_settings_form_round_trips_defaults(self):
        win = MainWindow(self.ctx)
        page = win.pages["settings"]
        page._load(Settings())
        self.assertEqual(page._collect(), Settings())
        win.close()


class FakeGeometry:
    def __init__(self, width, height):
        self._w, self._h = width, height

    def width(self):
        return self._w

    def height(self):
        return self._h


class FakeScreen:
    """Just enough of a QScreen for first_window_size()."""

    def __init__(self, width, height):
        self._geometry = FakeGeometry(width, height)

    def availableGeometry(self):
        return self._geometry


def fake_application(screen):
    class FakeApp:
        @staticmethod
        def primaryScreen():
            return screen
    return FakeApp


@unittest.skipUnless(HAVE_QT, "PySide6 is not installed")
class WindowSizeTests(unittest.TestCase):
    """The first window size must fit the screen it opens on, and never fall below the smallest usable size."""

    def size_on(self, screen):
        with mock.patch.object(main_window_mod, "QGuiApplication", fake_application(screen)):
            return main_window_mod.first_window_size()

    def test_big_screens_get_the_full_size(self):
        self.assertEqual(self.size_on(FakeScreen(3840, 2160)), (1440, 900))
        self.assertEqual(self.size_on(None), (1440, 900))                    # no screen information at all

    def test_a_laptop_screen_gets_a_window_that_fits(self):
        w, h = self.size_on(FakeScreen(1366, 728))                           # 1366x768 minus the task bar
        self.assertEqual((w, h), (1311, 684))
        self.assertLessEqual(w, 1366)
        self.assertLessEqual(h, 728)

    def test_a_tiny_screen_never_goes_below_the_smallest_usable_size(self):
        self.assertEqual(self.size_on(FakeScreen(800, 600)), (900, 564))


if __name__ == "__main__":
    unittest.main()
