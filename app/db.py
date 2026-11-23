"""SQLite storage. Use from the main (UI) thread only; workers never touch the database."""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np

from .config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS students (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    reg_no      TEXT NOT NULL UNIQUE COLLATE NOCASE,   -- "21cs001" and "21CS001" are the same person
    name        TEXT NOT NULL,
    role        TEXT NOT NULL DEFAULT 'student',   -- 'student' | 'staff' (invigilators)
    email       TEXT, phone TEXT, department TEXT, course TEXT, section TEXT, year TEXT, notes TEXT,
    consent_at  REAL,
    created_at  REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS face_samples (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id  INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    image_path  TEXT NOT NULL,
    embedding   BLOB NOT NULL,
    quality     REAL,
    created_at  REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    kind             TEXT NOT NULL,                -- 'class' | 'exam'
    title            TEXT NOT NULL,
    section          TEXT,
    start_ts         REAL NOT NULL,
    duration_min     INTEGER NOT NULL,
    min_presence_min INTEGER NOT NULL,
    status           TEXT NOT NULL DEFAULT 'running',
    ended_ts         REAL,
    config_json      TEXT
);
CREATE TABLE IF NOT EXISTS attendance (
    session_id   INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    student_id   INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    check_in_ts  REAL, check_out_ts REAL,
    first_seen   REAL, last_seen REAL,
    present_sec  REAL NOT NULL DEFAULT 0,
    status       TEXT NOT NULL DEFAULT 'ABSENT',
    reason       TEXT,
    override     INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (session_id, student_id)
);
CREATE TABLE IF NOT EXISTS presence_intervals (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    student_id  INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    start_ts    REAL NOT NULL,
    end_ts      REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_intervals ON presence_intervals(session_id, student_id);
CREATE TABLE IF NOT EXISTS events (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id    INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    student_id    INTEGER REFERENCES students(id) ON DELETE SET NULL,
    ts            REAL NOT NULL,
    type          TEXT NOT NULL,
    severity      INTEGER NOT NULL DEFAULT 1,
    detail        TEXT,
    snapshot      TEXT,
    confidence    REAL DEFAULT 0.90,
    score_weight  REAL DEFAULT 0.0,
    review_status TEXT DEFAULT 'Pending Review',
    admin_remarks TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS ix_events ON events(session_id, ts);
CREATE TABLE IF NOT EXISTS risk_scores (
    session_id  INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    key         TEXT NOT NULL,
    student_id  INTEGER,
    label       TEXT,
    score       REAL NOT NULL,
    level       TEXT NOT NULL,
    metrics     TEXT,
    PRIMARY KEY (session_id, key)
);
CREATE TABLE IF NOT EXISTS timetable (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    day_of_week      TEXT NOT NULL,
    subcode          TEXT,
    subject          TEXT NOT NULL,
    section          TEXT,
    teacher          TEXT,
    room             TEXT,
    start_time       TEXT NOT NULL,
    end_time         TEXT NOT NULL,
    duration_min     INTEGER NOT NULL DEFAULT 50,
    min_presence_min INTEGER NOT NULL DEFAULT 40,
    camera_source    TEXT DEFAULT '0',
    notes            TEXT,
    created_at       REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_timetable_day ON timetable(day_of_week);
"""

SCHEMA_VERSION = 1            # stored in PRAGMA user_version so a later release can tell which layout a file has

STUDENT_FIELDS = ("reg_no", "name", "role", "email", "phone", "department",
                  "course", "section", "year", "notes", "consent_at")
TIMETABLE_FIELDS = ("day_of_week", "subcode", "subject", "section", "teacher", "room",
                    "start_time", "end_time", "duration_min", "min_presence_min",
                    "camera_source", "notes")

DEFAULT_TIMETABLE = [
    # ---- Monday ----
    dict(day_of_week="Monday", subcode="PEA306", subject="Analytical Skills & Aptitude (Tutorial)",
         section="K3P24WX", teacher="Faculty PEA306", room="37-603", start_time="10:20", end_time="11:10",
         duration_min=50, min_presence_min=40, camera_source="0", notes="Tutorial"),
    dict(day_of_week="Monday", subcode="CSE471", subject="Cloud Computing Lab (Practical)",
         section="K3P24WX", teacher="Faculty CSE471", room="37-603", start_time="11:10", end_time="12:00",
         duration_min=50, min_presence_min=40, camera_source="0", notes="Practical"),
    dict(day_of_week="Monday", subcode="CSE471", subject="Cloud Computing Lab (Practical)",
         section="K3P24WX", teacher="Faculty CSE471", room="37-603", start_time="12:00", end_time="12:50",
         duration_min=50, min_presence_min=40, camera_source="0", notes="Practical"),
    dict(day_of_week="Monday", subcode="PES390", subject="Professional Enhancement Skills (Lecture)",
         section="K3P24WX", teacher="Faculty PES390", room="28-502", start_time="13:40", end_time="14:30",
         duration_min=50, min_presence_min=40, camera_source="0", notes="Lecture"),
    dict(day_of_week="Monday", subcode="PEA306", subject="Analytical Skills & Aptitude (Lecture)",
         section="K3P24WX", teacher="Faculty PEA306", room="28-502", start_time="14:30", end_time="15:20",
         duration_min=50, min_presence_min=40, camera_source="0", notes="Lecture"),
    dict(day_of_week="Monday", subcode="CSE408", subject="Artificial Intelligence (Lecture)",
         section="K3P24WX", teacher="Faculty CSE408", room="28-502", start_time="15:20", end_time="16:10",
         duration_min=50, min_presence_min=40, camera_source="0", notes="Lecture"),
    dict(day_of_week="Monday", subcode="CSE408", subject="Artificial Intelligence (Lecture)",
         section="K3P24WX", teacher="Faculty CSE408", room="28-502", start_time="16:10", end_time="17:00",
         duration_min=50, min_presence_min=40, camera_source="0", notes="Lecture"),

    # ---- Tuesday ----
    dict(day_of_week="Tuesday", subcode="CSE472", subject="Big Data Analytics Lab (Practical)",
         section="K3P24WX", teacher="Faculty CSE472", room="37-701", start_time="10:20", end_time="11:10",
         duration_min=50, min_presence_min=40, camera_source="0", notes="Practical"),
    dict(day_of_week="Tuesday", subcode="CSE472", subject="Big Data Analytics Lab (Practical)",
         section="K3P24WX", teacher="Faculty CSE472", room="37-701", start_time="11:10", end_time="12:00",
         duration_min=50, min_presence_min=40, camera_source="0", notes="Practical"),
    dict(day_of_week="Tuesday", subcode="INT331", subject="Web Technologies (Lecture)",
         section="K202411", teacher="Faculty INT331", room="33-311", start_time="12:00", end_time="12:50",
         duration_min=50, min_presence_min=40, camera_source="0", notes="Lecture"),
    dict(day_of_week="Tuesday", subcode="PES390", subject="Professional Enhancement Skills (Tutorial)",
         section="K3P24WX", teacher="Faculty PES390", room="37-605", start_time="13:40", end_time="14:30",
         duration_min=50, min_presence_min=40, camera_source="0", notes="Tutorial"),
    dict(day_of_week="Tuesday", subcode="PES390", subject="Professional Enhancement Skills (Tutorial)",
         section="K3P24WX", teacher="Faculty PES390", room="37-606", start_time="14:30", end_time="15:20",
         duration_min=50, min_presence_min=40, camera_source="0", notes="Tutorial"),
    dict(day_of_week="Tuesday", subcode="MKP01", subject="Makeup Class (14-411)",
         section="K3P24WX", teacher="Faculty Makeup", room="14-411", start_time="17:00", end_time="17:50",
         duration_min=50, min_presence_min=40, camera_source="0", notes="Makeup Class"),

    # ---- Wednesday ----
    dict(day_of_week="Wednesday", subcode="INT331", subject="Web Technologies Lab (Practical)",
         section="K202411", teacher="Faculty INT331", room="33-505X", start_time="12:00", end_time="12:50",
         duration_min=50, min_presence_min=40, camera_source="0", notes="Practical"),
    dict(day_of_week="Wednesday", subcode="PES390", subject="Professional Enhancement Skills (Lecture)",
         section="K3P24WX", teacher="Faculty PES390", room="27-103A", start_time="13:40", end_time="14:30",
         duration_min=50, min_presence_min=40, camera_source="0", notes="Lecture"),
    dict(day_of_week="Wednesday", subcode="CSE471", subject="Cloud Computing (Lecture)",
         section="K3P24WX", teacher="Faculty CSE471", room="27-103A", start_time="14:30", end_time="15:20",
         duration_min=50, min_presence_min=40, camera_source="0", notes="Lecture"),
    dict(day_of_week="Wednesday", subcode="CSE471", subject="Cloud Computing (Lecture)",
         section="K3P24WX", teacher="Faculty CSE471", room="27-103A", start_time="15:20", end_time="16:10",
         duration_min=50, min_presence_min=40, camera_source="0", notes="Lecture"),
    dict(day_of_week="Wednesday", subcode="MKP02", subject="Makeup Class (34-213)",
         section="K3P24WX", teacher="Faculty Makeup", room="34-213", start_time="17:00", end_time="17:50",
         duration_min=50, min_presence_min=40, camera_source="0", notes="Makeup Class"),

    # ---- Thursday ----
    dict(day_of_week="Thursday", subcode="INT331", subject="Web Technologies (Lecture)",
         section="K202411", teacher="Faculty INT331", room="33-410", start_time="12:00", end_time="12:50",
         duration_min=50, min_presence_min=40, camera_source="0", notes="Lecture"),
    dict(day_of_week="Thursday", subcode="PEA306", subject="Analytical Skills & Aptitude (Lecture)",
         section="K3P24WX", teacher="Faculty PEA306", room="37-606", start_time="13:40", end_time="14:30",
         duration_min=50, min_presence_min=40, camera_source="0", notes="Lecture"),
    dict(day_of_week="Thursday", subcode="CSE472", subject="Big Data Analytics (Lecture)",
         section="K3P24WX", teacher="Faculty CSE472", room="25-801", start_time="14:30", end_time="15:20",
         duration_min=50, min_presence_min=40, camera_source="0", notes="Lecture"),
    dict(day_of_week="Thursday", subcode="CSE472", subject="Big Data Analytics (Lecture)",
         section="K3P24WX", teacher="Faculty CSE472", room="25-801", start_time="15:20", end_time="16:10",
         duration_min=50, min_presence_min=40, camera_source="0", notes="Lecture"),
    dict(day_of_week="Thursday", subcode="CSE408", subject="Artificial Intelligence (Lecture)",
         section="K3P24WX", teacher="Faculty CSE408", room="25-405", start_time="16:10", end_time="17:00",
         duration_min=50, min_presence_min=40, camera_source="0", notes="Lecture"),

    # ---- Friday ----
    dict(day_of_week="Friday", subcode="CSE408", subject="Artificial Intelligence Lab (Practical)",
         section="K3P24WX", teacher="Faculty CSE408", room="37-710", start_time="10:20", end_time="11:10",
         duration_min=50, min_presence_min=40, camera_source="0", notes="Practical"),
    dict(day_of_week="Friday", subcode="CSE408", subject="Artificial Intelligence Lab (Practical)",
         section="K3P24WX", teacher="Faculty CSE408", room="37-710", start_time="11:10", end_time="12:00",
         duration_min=50, min_presence_min=40, camera_source="0", notes="Practical"),
    dict(day_of_week="Friday", subcode="INT331", subject="Web Technologies Lab (Practical)",
         section="K202411", teacher="Faculty INT331", room="33-504", start_time="12:00", end_time="12:50",
         duration_min=50, min_presence_min=40, camera_source="0", notes="Practical"),

    # ---- Saturday ----
    dict(day_of_week="Saturday", subcode="PEAS01", subject="Aptitude & Soft Skills (Lecture)",
         section="9R050", teacher="Faculty PEAS01", room="33-602", start_time="09:30", end_time="10:20",
         duration_min=50, min_presence_min=40, camera_source="0", notes="Lecture"),
    dict(day_of_week="Saturday", subcode="PEVS01", subject="Verbal Communication Skills (Lecture)",
         section="9R050", teacher="Faculty PEVS01", room="33-602", start_time="10:20", end_time="11:10",
         duration_min=50, min_presence_min=40, camera_source="0", notes="Lecture"),
]


class Database:
    def __init__(self, path: Path | str = DB_PATH):
        self.conn = sqlite3.connect(str(path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        try:
            self.conn.execute("PRAGMA journal_mode = WAL")
        except sqlite3.DatabaseError:
            pass
        self.conn.executescript(SCHEMA)
        try:
            self.conn.execute("ALTER TABLE timetable ADD COLUMN subcode TEXT")
        except sqlite3.OperationalError:
            pass
        for col_def in [
            "confidence REAL DEFAULT 0.90",
            "score_weight REAL DEFAULT 0.0",
            "review_status TEXT DEFAULT 'Pending Review'",
            "admin_remarks TEXT DEFAULT ''",
        ]:
            try:
                self.conn.execute(f"ALTER TABLE events ADD COLUMN {col_def}")
            except sqlite3.OperationalError:
                pass
        if self.conn.execute("PRAGMA user_version").fetchone()[0] == 0:
            self.conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        if self.conn.execute("SELECT COUNT(*) FROM timetable").fetchone()[0] == 0:
            self.seed_default_timetable()
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    # ---------------------------------------------------------------- students
    def add_student(self, **f) -> int:
        data = {k: f.get(k) for k in STUDENT_FIELDS}
        data["role"] = data["role"] or "student"
        cols = ", ".join(data)
        marks = ", ".join("?" for _ in data)
        with self.conn:
            cur = self.conn.execute(
                f"INSERT INTO students ({cols}, created_at) VALUES ({marks}, ?)",
                (*data.values(), time.time()))
        return int(cur.lastrowid)

    def update_student(self, sid: int, **f) -> None:
        data = {k: v for k, v in f.items() if k in STUDENT_FIELDS}
        if not data:
            return
        sets = ", ".join(f"{k} = ?" for k in data)
        with self.conn:
            self.conn.execute(f"UPDATE students SET {sets} WHERE id = ?", (*data.values(), sid))

    def delete_student(self, sid: int) -> List[str]:
        """Remove a student and all their data. Returns image paths so callers can delete files."""
        paths = [r["image_path"] for r in
                 self.conn.execute("SELECT image_path FROM face_samples WHERE student_id = ?", (sid,))]
        with self.conn:
            self.conn.execute("DELETE FROM students WHERE id = ?", (sid,))
        return paths

    def get_student(self, sid: int) -> Optional[sqlite3.Row]:
        return self.conn.execute("SELECT * FROM students WHERE id = ?", (sid,)).fetchone()

    def get_by_reg(self, reg_no: str) -> Optional[sqlite3.Row]:
        # NOCASE here too, so files created before the column itself was case-insensitive behave the same
        return self.conn.execute("SELECT * FROM students WHERE reg_no = ? COLLATE NOCASE", (reg_no,)).fetchone()

    def list_students(self, q: str = "", section: Optional[str] = None,
                      role: Optional[str] = None) -> List[sqlite3.Row]:
        sql = ("SELECT s.*, (SELECT COUNT(*) FROM face_samples f WHERE f.student_id = s.id) AS samples "
               "FROM students s WHERE 1 = 1")
        params: list = []
        if q:
            sql += " AND (s.name LIKE ? OR s.reg_no LIKE ?)"
            params += [f"%{q}%", f"%{q}%"]
        if section:
            sql += " AND s.section = ?"
            params.append(section)
        if role:
            sql += " AND s.role = ?"
            params.append(role)
        return self.conn.execute(sql + " ORDER BY s.reg_no", params).fetchall()

    def sections(self) -> List[str]:
        rows = self.conn.execute(
            "SELECT DISTINCT section FROM students WHERE role = 'student' "
            "AND section IS NOT NULL AND section != '' ORDER BY section")
        return [r[0] for r in rows]

    # ----------------------------------------------------------------- samples
    def add_sample(self, student_id: int, image_path: str, emb: np.ndarray, quality: float = 0.0) -> int:
        with self.conn:
            cur = self.conn.execute(
                "INSERT INTO face_samples (student_id, image_path, embedding, quality, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (student_id, image_path, np.asarray(emb, np.float32).tobytes(), quality, time.time()))
        return int(cur.lastrowid)

    def samples(self, student_id: int) -> List[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM face_samples WHERE student_id = ? ORDER BY id", (student_id,)).fetchall()

    def delete_sample(self, sample_id: int) -> Optional[str]:
        row = self.conn.execute("SELECT image_path FROM face_samples WHERE id = ?", (sample_id,)).fetchone()
        with self.conn:
            self.conn.execute("DELETE FROM face_samples WHERE id = ?", (sample_id,))
        return row["image_path"] if row else None

    def all_samples(self) -> List[sqlite3.Row]:
        return self.conn.execute("SELECT * FROM face_samples ORDER BY id").fetchall()

    def update_embedding(self, sample_id: int, emb: np.ndarray) -> None:
        with self.conn:
            self.conn.execute("UPDATE face_samples SET embedding = ? WHERE id = ?",
                              (np.asarray(emb, np.float32).tobytes(), sample_id))

    def embeddings(self, student_ids: Optional[Iterable[int]] = None) -> Tuple[np.ndarray, np.ndarray]:
        allowed = set(student_ids) if student_ids is not None else None
        ids, embs = [], []
        for r in self.conn.execute("SELECT student_id, embedding FROM face_samples"):
            if allowed is not None and r["student_id"] not in allowed:
                continue
            ids.append(r["student_id"])
            embs.append(np.frombuffer(r["embedding"], dtype=np.float32))
        if not ids:
            return np.zeros((0,), np.int64), np.zeros((0, 128), np.float32)
        return np.asarray(ids, np.int64), np.vstack(embs)

    # ---------------------------------------------------------------- sessions
    def create_session(self, kind: str, title: str, section: Optional[str], start_ts: float,
                       duration_min: int, min_presence_min: int, config: Optional[dict] = None) -> int:
        with self.conn:
            cur = self.conn.execute(
                "INSERT INTO sessions (kind, title, section, start_ts, duration_min, min_presence_min, config_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (kind, title, section, start_ts, duration_min, min_presence_min,
                 json.dumps(config or {})))
        return int(cur.lastrowid)

    def mark_interrupted(self) -> int:
        """Sessions still marked 'running' when the app starts were cut short (crash, power cut).
        Their last autosaved results are kept; they are re-labelled so they are not shown as live."""
        with self.conn:
            cur = self.conn.execute(
                "UPDATE sessions SET status = 'interrupted', "
                "ended_ts = COALESCE((SELECT MAX(a.last_seen) FROM attendance a WHERE a.session_id = sessions.id), "
                "start_ts) WHERE status = 'running'")
        return int(cur.rowcount)

    def finish_session(self, session_id: int, ended_ts: float) -> None:
        with self.conn:
            self.conn.execute("UPDATE sessions SET status = 'finished', ended_ts = ? WHERE id = ?",
                              (ended_ts, session_id))

    def get_session(self, session_id: int) -> Optional[sqlite3.Row]:
        return self.conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()

    def list_sessions(self, limit: int = 300, kind: Optional[str] = None) -> List[sqlite3.Row]:
        where = "WHERE s.kind = ?" if kind else ""
        sql = ("SELECT s.*, "
               "(SELECT COUNT(*) FROM attendance a WHERE a.session_id = s.id AND a.status = 'PRESENT') AS n_present, "
               "(SELECT COUNT(*) FROM attendance a WHERE a.session_id = s.id) AS n_total, "
               "(SELECT COUNT(*) FROM events e WHERE e.session_id = s.id AND e.severity > 0) AS n_alerts "
               f"FROM sessions s {where} ORDER BY s.start_ts DESC LIMIT ?")
        params = ([kind] if kind else []) + [limit]
        return self.conn.execute(sql, params).fetchall()

    def delete_session(self, session_id: int) -> List[str]:
        paths = [r["snapshot"] for r in self.conn.execute(
            "SELECT snapshot FROM events WHERE session_id = ? AND snapshot IS NOT NULL AND snapshot != ''",
            (session_id,))]
        with self.conn:
            self.conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        return paths

    # -------------------------------------------------------------- attendance
    def save_attendance(self, session_id: int, rows: List[dict],
                        intervals: Dict[int, List[List[float]]]) -> None:
        """Upsert attendance rows; manual overrides keep their status/reason."""
        with self.conn:
            for r in rows:
                self.conn.execute(
                    "INSERT INTO attendance (session_id, student_id, check_in_ts, check_out_ts, first_seen, "
                    "last_seen, present_sec, status, reason) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) "
                    "ON CONFLICT(session_id, student_id) DO UPDATE SET "
                    "check_in_ts = excluded.check_in_ts, check_out_ts = excluded.check_out_ts, "
                    "first_seen = excluded.first_seen, last_seen = excluded.last_seen, "
                    "present_sec = excluded.present_sec, "
                    "status = CASE WHEN attendance.override = 1 THEN attendance.status ELSE excluded.status END, "
                    "reason = CASE WHEN attendance.override = 1 THEN attendance.reason ELSE excluded.reason END",
                    (session_id, r["sid"], r["check_in"], r["check_out"], r["first_seen"],
                     r["last_seen"], r["present_sec"], r["status"], r["reason"]))
            self.conn.execute("DELETE FROM presence_intervals WHERE session_id = ?", (session_id,))
            self.conn.executemany(
                "INSERT INTO presence_intervals (session_id, student_id, start_ts, end_ts) VALUES (?, ?, ?, ?)",
                [(session_id, sid, a, b) for sid, ivs in intervals.items() for a, b in ivs])

    def attendance(self, session_id: int) -> List[sqlite3.Row]:
        return self.conn.execute(
            "SELECT a.*, s.reg_no, s.name FROM attendance a JOIN students s ON s.id = a.student_id "
            "WHERE a.session_id = ? ORDER BY s.reg_no", (session_id,)).fetchall()

    def intervals(self, session_id: int) -> Dict[int, List[Tuple[float, float]]]:
        out: Dict[int, List[Tuple[float, float]]] = {}
        for r in self.conn.execute(
                "SELECT student_id, start_ts, end_ts FROM presence_intervals "
                "WHERE session_id = ? ORDER BY start_ts", (session_id,)):
            out.setdefault(r["student_id"], []).append((r["start_ts"], r["end_ts"]))
        return out

    def set_override(self, session_id: int, student_id: int, status: str, reason: str) -> None:
        with self.conn:
            self.conn.execute(
                "UPDATE attendance SET status = ?, reason = ?, override = 1 "
                "WHERE session_id = ? AND student_id = ?", (status, reason, session_id, student_id))

    # ------------------------------------------------------------------ events
    def add_event(self, session_id: int, student_id: Optional[int], ts: float, type_: str,
                  severity: int, detail: str = "", snapshot: str = "",
                  confidence: float = 0.90, score_weight: float = 0.0,
                  review_status: str = "Pending Review", admin_remarks: str = "") -> int:
        with self.conn:
            cur = self.conn.execute(
                "INSERT INTO events (session_id, student_id, ts, type, severity, detail, snapshot, "
                "confidence, score_weight, review_status, admin_remarks) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (session_id, student_id, ts, type_, severity, detail, snapshot,
                 confidence, score_weight, review_status, admin_remarks))
        return int(cur.lastrowid)

    def update_event_review(self, event_id: int, review_status: str, admin_remarks: str = "") -> None:
        with self.conn:
            self.conn.execute(
                "UPDATE events SET review_status = ?, admin_remarks = ? WHERE id = ?",
                (review_status, admin_remarks, event_id))

    def get_event(self, event_id: int) -> Optional[sqlite3.Row]:
        return self.conn.execute(
            "SELECT e.*, s.name, s.reg_no FROM events e LEFT JOIN students s ON s.id = e.student_id "
            "WHERE e.id = ?", (event_id,)).fetchone()

    def events(self, session_id: int) -> List[sqlite3.Row]:
        return self.conn.execute(
            "SELECT e.*, s.name, s.reg_no FROM events e LEFT JOIN students s ON s.id = e.student_id "
            "WHERE e.session_id = ? ORDER BY e.ts", (session_id,)).fetchall()

    def save_risk(self, session_id: int, rows: List[dict]) -> None:
        with self.conn:
            self.conn.execute("DELETE FROM risk_scores WHERE session_id = ?", (session_id,))
            self.conn.executemany(
                "INSERT INTO risk_scores (session_id, key, student_id, label, score, level, metrics) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                [(session_id, r["key"], r["sid"], r["name"], r["score"], r["level"],
                  json.dumps({k: v for k, v in r.items() if k not in ("key", "sid", "name", "score", "level")}))
                 for r in rows])

    def risk(self, session_id: int) -> List[dict]:
        out = []
        for r in self.conn.execute(
                "SELECT * FROM risk_scores WHERE session_id = ? ORDER BY score DESC", (session_id,)):
            d = json.loads(r["metrics"] or "{}")
            d.update(key=r["key"], sid=r["student_id"], name=r["label"], score=r["score"], level=r["level"])
            out.append(d)
        return out

    # ------------------------------------------------------------------- stats
    def stats(self) -> dict:
        q = self.conn.execute
        return {
            "students": q("SELECT COUNT(*) FROM students WHERE role = 'student'").fetchone()[0],
            "staff": q("SELECT COUNT(*) FROM students WHERE role = 'staff'").fetchone()[0],
            "samples": q("SELECT COUNT(*) FROM face_samples").fetchone()[0],
            "sessions": q("SELECT COUNT(*) FROM sessions").fetchone()[0],
            "alerts": q("SELECT COUNT(*) FROM events WHERE severity > 0").fetchone()[0],
            "timetable": q("SELECT COUNT(*) FROM timetable").fetchone()[0],
        }

    # --------------------------------------------------------------- timetable
    def add_timetable_entry(self, **f) -> int:
        data = {k: f.get(k) for k in TIMETABLE_FIELDS}
        data["duration_min"] = int(data["duration_min"] or 50)
        data["min_presence_min"] = int(data["min_presence_min"] or 40)
        data["camera_source"] = data["camera_source"] or "0"
        cols = ", ".join(data)
        marks = ", ".join("?" for _ in data)
        with self.conn:
            cur = self.conn.execute(
                f"INSERT INTO timetable ({cols}, created_at) VALUES ({marks}, ?)",
                (*data.values(), time.time()))
        return int(cur.lastrowid)

    def update_timetable_entry(self, entry_id: int, **f) -> None:
        data = {k: v for k, v in f.items() if k in TIMETABLE_FIELDS}
        if not data:
            return
        sets = ", ".join(f"{k} = ?" for k in data)
        with self.conn:
            self.conn.execute(f"UPDATE timetable SET {sets} WHERE id = ?", (*data.values(), entry_id))

    def delete_timetable_entry(self, entry_id: int) -> None:
        with self.conn:
            self.conn.execute("DELETE FROM timetable WHERE id = ?", (entry_id,))

    def get_timetable_entry(self, entry_id: int) -> Optional[sqlite3.Row]:
        return self.conn.execute("SELECT * FROM timetable WHERE id = ?", (entry_id,)).fetchone()

    def list_timetable(self, day_of_week: Optional[str] = None,
                       section: Optional[str] = None) -> List[sqlite3.Row]:
        sql = "SELECT * FROM timetable WHERE 1 = 1"
        params: list = []
        if day_of_week and day_of_week.lower() not in ("all days", "all"):
            sql += " AND day_of_week = ? COLLATE NOCASE"
            params.append(day_of_week)
        if section and section.lower() not in ("all sections", "all"):
            sql += " AND section = ? COLLATE NOCASE"
            params.append(section)
        order = """
        CASE UPPER(day_of_week)
            WHEN 'MONDAY' THEN 1
            WHEN 'TUESDAY' THEN 2
            WHEN 'WEDNESDAY' THEN 3
            WHEN 'THURSDAY' THEN 4
            WHEN 'FRIDAY' THEN 5
            WHEN 'SATURDAY' THEN 6
            WHEN 'SUNDAY' THEN 7
            ELSE 8
        END, start_time ASC
        """
        return self.conn.execute(f"{sql} ORDER BY {order}", params).fetchall()

    def get_today_timetable(self, day_name: Optional[str] = None) -> List[sqlite3.Row]:
        if not day_name:
            import datetime
            day_name = datetime.datetime.now().strftime("%A")
        return self.list_timetable(day_of_week=day_name)

    def seed_default_timetable(self, force: bool = False) -> int:
        with self.conn:
            if force:
                self.conn.execute("DELETE FROM timetable")
            count = 0
            for entry in DEFAULT_TIMETABLE:
                cols = ", ".join(entry)
                marks = ", ".join("?" for _ in entry)
                self.conn.execute(
                    f"INSERT INTO timetable ({cols}, created_at) VALUES ({marks}, ?)",
                    (*entry.values(), time.time()))
                count += 1
            return count
