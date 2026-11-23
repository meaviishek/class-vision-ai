"""CSV exports. Files use UTF-8 with a BOM so Excel shows non-English names correctly."""
from __future__ import annotations

import csv
from pathlib import Path

from ..config import DATA_DIR
from ..utils import fmt_clock, fmt_datetime
from .attendance import breaks_between
from .proctor import EVENT_INFO


def _spans(pairs) -> str:
    return "; ".join(f"{fmt_clock(a, False)}-{fmt_clock(b, False)}" for a, b in pairs)


_FORMULA_START = ("=", "+", "-", "@", "\t", "\r")


def safe_cell(value):
    """Excel and similar programs run text that starts with = + - @ as a formula, so a name typed in as
    '=HYPERLINK(...)' would execute when someone opens the export. A leading apostrophe keeps it plain text.
    Numbers, ordinary text and a lone '-' (our 'nothing here' mark) are left alone."""
    if isinstance(value, str) and value.startswith(_FORMULA_START) and value not in ("-", "+"):
        return "'" + value
    return value


def _row(writer, values) -> None:
    writer.writerow([safe_cell(v) for v in values])


def export_attendance_csv(db, session_id: int, path) -> None:
    sess = db.get_session(session_id)
    start = sess["start_ts"]
    end = start + sess["duration_min"] * 60
    intervals = db.intervals(session_id)
    with open(path, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        _row(w, ["Session", sess["title"], "Type", sess["kind"], "Starts", fmt_datetime(start),
                 "Length (min)", sess["duration_min"], "Minimum presence (min)", sess["min_presence_min"]])
        w.writerow([])
        w.writerow(["Reg. no", "Name", "Status", "Check-in", "Check-out", "Minutes in class", "First seen",
                    "Last seen", "In class (from-to)", "Breaks (from-to)", "Reason"])
        for r in db.attendance(session_id):
            ivs = intervals.get(r["student_id"], [])
            _row(w, [r["reg_no"], r["name"], r["status"], fmt_clock(r["check_in_ts"]),
                     fmt_clock(r["check_out_ts"]), round((r["present_sec"] or 0) / 60.0, 1),
                     fmt_clock(r["first_seen"]), fmt_clock(r["last_seen"]), _spans(ivs),
                     _spans(breaks_between(ivs, start, end)), r["reason"] or ""])


def export_events_csv(db, session_id: int, path) -> None:
    with open(path, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(["Time", "Reg. no", "Name", "Alert", "Severity", "Detail", "Evidence image"])
        for e in db.events(session_id):
            if e["severity"] <= 0:
                continue
            snap = str(Path(DATA_DIR) / e["snapshot"]) if e["snapshot"] else ""
            _row(w, [fmt_clock(e["ts"]), e["reg_no"] or "", e["name"] or "",
                     EVENT_INFO.get(e["type"], (0, e["type"]))[1], e["severity"], e["detail"] or "", snap])


def export_risk_csv(db, session_id: int, path) -> None:
    with open(path, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(["Name", "Level", "Score", "Observed (s)", "Looking away (%)", "Look-aways", "Repeated bursts",
                    "Not visible (s)", "Objects", "Identity flags", "Room z-score"])
        for r in db.risk(session_id):
            _row(w, [r["name"], r["level"], r["score"], r.get("observed_sec", 0), r.get("away_pct", 0),
                     r.get("glances", 0), r.get("bursts", 0), r.get("missing_sec", 0),
                     r.get("objects", 0), r.get("flags", 0), r.get("z", 0)])
