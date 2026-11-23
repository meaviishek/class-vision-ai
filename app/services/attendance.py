"""Attendance rules. Pure logic with no camera, database or Qt, so it is easy to test.

Evidence for each student comes from three places:
  * check-in   - close-up face check at the gate while the check-in window is open
  * in-class   - classroom camera sightings, merged into presence intervals (gaps = breaks)
  * check-out  - close-up face check at the gate while the check-out window is open

A student is PRESENT only if the in-class time inside [start, end] reaches the minimum AND the
required gate checks happened. Enough time but a missing gate check = REVIEW (teacher decides).
Gate checks without enough time in the room = ABSENT (catches "show up for the checks only").
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from ..config import Settings
from ..utils import fmt_clock, fmt_dur, fmt_mmss

PRESENT, ABSENT, REVIEW = "PRESENT", "ABSENT", "REVIEW"


def breaks_between(intervals, a: float, b: float) -> List[Tuple[float, float]]:
    """Gaps between consecutive presence intervals, clipped to the class window [a, b]."""
    out = []
    for (_, end0), (start1, _) in zip(intervals, intervals[1:]):
        lo, hi = max(end0, a), min(start1, b)
        if hi > lo:
            out.append((lo, hi))
    return out


@dataclass
class Rec:
    sid: int
    name: str
    reg_no: str
    intervals: List[List[float]] = field(default_factory=list)
    check_in: Optional[float] = None
    check_out: Optional[float] = None

    def sight(self, ts: float, gap: float) -> None:
        """Record a sighting. Sightings closer than `gap` seconds extend the current interval."""
        if self.intervals:
            iv = self.intervals[-1]
            if ts - iv[1] <= gap:
                iv[1] = max(iv[1], ts)
                iv[0] = min(iv[0], ts)
                return
        self.intervals.append([ts, ts])

    @property
    def first_seen(self) -> Optional[float]:
        return self.intervals[0][0] if self.intervals else None

    @property
    def last_seen(self) -> Optional[float]:
        return self.intervals[-1][1] if self.intervals else None

    def present_sec(self, a: float, b: float) -> float:
        return sum(max(0.0, min(e, b) - max(s, a)) for s, e in self.intervals)


@dataclass
class GateResult:
    sid: int
    kind: str            # "in" | "out" | "closed" | "unknown"
    accepted: bool
    message: str
    ts: float


class AttendanceEngine:
    def __init__(self, settings: Settings, start_ts: float, duration_min: float,
                 min_presence_min: float, roster: Dict[int, dict]):
        self.s = settings
        self.S = float(start_ts)
        self.E = self.S + float(duration_min) * 60.0
        # More than the whole class can never be required, however the minimum was typed in.
        self.need = min(float(min_presence_min), float(duration_min)) * 60.0
        self.gap = float(settings.gap_tolerance_sec)
        self.recs: Dict[int, Rec] = {sid: Rec(sid, r["name"], r["reg_no"]) for sid, r in roster.items()}
        self.in_open = self.S - settings.checkin_before_min * 60.0
        self.in_close = self.S + settings.checkin_after_min * 60.0
        self.out_open = max(self.E - settings.checkout_before_min * 60.0, self.in_close)
        self.out_close = self.E + settings.checkout_after_min * 60.0
        self.final_now: Optional[float] = None

    # ------------------------------------------------------------------ timing
    @property
    def auto_end(self) -> float:
        """When the session can close itself (after the check-out window if it is required)."""
        return self.out_close if self.s.require_checkout else self.E

    def gate_window(self, ts: float) -> Optional[str]:
        if self.out_open <= ts <= self.out_close:
            return "out"
        if self.in_open <= ts <= self.in_close:
            return "in"
        return None

    def timing(self, now: float) -> dict:
        if now < self.S:
            phase = f"Waiting: class starts in {fmt_mmss(self.S - now)}"
        elif now <= self.E:
            phase = f"Class running: {fmt_mmss(now - self.S)} elapsed, {fmt_mmss(self.E - now)} left"
        elif now <= self.out_close:
            phase = "Class ended: waiting for check-out"
        else:
            phase = "Finished"
        gate = {"in": "Check-in open", "out": "Check-out open", None: "Gate closed"}[self.gate_window(now)]
        return {"phase": phase, "gate": gate, "start": self.S, "end": self.E}

    def gate_hint(self, ts: float) -> str:
        if ts < self.in_open:
            return f"check-in opens at {fmt_clock(self.in_open, False)}"
        if ts < self.out_open:
            return f"check-out opens at {fmt_clock(self.out_open, False)}"
        return "check-out has closed"

    # ---------------------------------------------------------------- evidence
    def class_sight(self, sid: int, ts: float) -> None:
        rec = self.recs.get(sid)
        if rec is not None:
            rec.sight(ts, self.gap)

    def gate(self, sid: int, ts: float) -> GateResult:
        rec = self.recs.get(sid)
        if rec is None:
            return GateResult(sid, "unknown", False, "Not on this class roster", ts)
        mode = self.gate_window(ts)
        if mode == "in":
            if rec.check_in is None:
                rec.check_in = ts
                return GateResult(sid, "in", True, f"{rec.name}: checked in at {fmt_clock(ts, False)}", ts)
            return GateResult(sid, "in", False,
                              f"{rec.name}: already checked in at {fmt_clock(rec.check_in, False)}", ts)
        if mode == "out":
            if rec.check_out is None:
                rec.check_out = ts
                return GateResult(sid, "out", True, f"{rec.name}: checked out at {fmt_clock(ts, False)}", ts)
            return GateResult(sid, "out", False,
                              f"{rec.name}: already checked out at {fmt_clock(rec.check_out, False)}", ts)
        return GateResult(sid, "closed", False, f"Gate closed ({self.gate_hint(ts)})", ts)

    # -------------------------------------------------------------- evaluation
    def _now(self, now: float) -> float:
        return self.final_now if self.final_now is not None else now

    def evaluate(self, rec: Rec, now: float) -> Tuple[str, str]:
        """Status if the session were closed at `now`. Closing early scales the required minutes
        down in proportion and waives a check-out that was not yet possible."""
        now = self._now(now)
        full = self.E - self.S
        end = min(self.E, now)
        if end <= self.S:
            return ABSENT, "Class has not started"
        need = self.need * ((end - self.S) / full if full > 0 else 1.0)
        present = rec.present_sec(self.S, end)
        if present <= 0 and rec.check_in is None and rec.check_out is None:
            return ABSENT, "Not detected"
        if present + 1e-6 < need:
            msg = f"Seen in class {fmt_dur(present)}, needs {fmt_dur(need)}"
            if rec.check_in is not None and rec.check_out is not None:
                msg += " (passed the gate but was not tracked in the room)"
            return ABSENT, msg
        missing = []
        if self.s.require_checkin and rec.check_in is None:
            missing.append("no check-in")
        if self.s.require_checkout and rec.check_out is None and now >= self.out_open:
            missing.append("no check-out")
        if missing:
            return REVIEW, f"{', '.join(missing).capitalize()} (in class {fmt_dur(present)})"
        return PRESENT, f"In class {fmt_dur(present)} of {fmt_dur(full)}"

    def live_state(self, rec: Rec, now: float) -> str:
        if not rec.intervals:
            return "Not seen"
        return "In class" if now - rec.intervals[-1][1] <= self.gap else "Out"

    def snapshot(self, now: float) -> List[dict]:
        """Rows for the live table."""
        now = self._now(now)
        end = min(self.E, max(now, self.S))
        remaining = max(0.0, self.E - max(now, self.S))
        rows = []
        for rec in sorted(self.recs.values(), key=lambda r: r.reg_no):
            present = rec.present_sec(self.S, end)
            status, reason = self.evaluate(rec, now)
            if present >= self.need:
                proj = "Qualified"
            elif present + remaining >= self.need:
                proj = "Can still qualify"
            else:
                proj = "Cannot qualify"
            rows.append(dict(
                sid=rec.sid, reg_no=rec.reg_no, name=rec.name, state=self.live_state(rec, now),
                status=status, reason=reason, check_in=rec.check_in, check_out=rec.check_out,
                present_sec=present, first_seen=rec.first_seen, last_seen=rec.last_seen,
                projection=proj, intervals=[tuple(iv) for iv in rec.intervals],
                start=self.S, end=self.E))
        return rows

    # ------------------------------------------------------------- persistence
    def attendance_rows(self, now: float) -> List[dict]:
        now = self._now(now)
        end = min(self.E, max(now, self.S))
        out = []
        for rec in self.recs.values():
            status, reason = self.evaluate(rec, now)
            out.append(dict(sid=rec.sid, check_in=rec.check_in, check_out=rec.check_out,
                            first_seen=rec.first_seen, last_seen=rec.last_seen,
                            present_sec=rec.present_sec(self.S, end), status=status, reason=reason))
        return out

    def interval_map(self) -> Dict[int, List[List[float]]]:
        return {sid: [list(iv) for iv in rec.intervals] for sid, rec in self.recs.items() if rec.intervals}

    def finalize(self, now: float) -> None:
        """Freeze results at `now`; later snapshot()/attendance_rows() calls use this moment."""
        self.final_now = now
