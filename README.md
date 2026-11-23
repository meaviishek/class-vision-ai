# ClassVision AI: Enterprise Classroom Attendance & Smart Exam Proctoring System

[![Python Version](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue.svg)](https://www.python.org/)
[![GUI Framework](https://img.shields.io/badge/GUI-PySide6%20%2F%20Qt-green.svg)](https://doc.qt.io/qtforpython-6/)
[![Computer Vision](https://img.shields.io/badge/Vision-OpenCV%20YuNet%20%2B%20SFace-orange.svg)](https://github.com/opencv/opencv_zoo)
[![Object Detection](https://img.shields.io/badge/Detection-YOLOv8-red.svg)](https://github.com/ultralytics/ultralytics)
[![Storage](https://img.shields.io/badge/Database-SQLite3%20WAL-lightgrey.svg)](https://www.sqlite.org/)
[![Test Coverage](https://img.shields.io/badge/tests-98%20passed-brightgreen.svg)]()

> **ClassVision AI** is a production-grade, local-first Computer Vision platform designed for educational institutions. It automates **multi-student classroom attendance**, **university timetable schedule management**, and **real-time AI examination proctoring**.
> 
> All processing and biometric face data remain strictly on your local machine; **no data ever leaves your hardware**.

---

## Table of Contents

1. [Executive Overview](#executive-overview)
2. [System Architecture](#system-architecture)
3. [Key Modules & Features](#key-modules--features)
   - [A. Biometric Enrollment & Quality Gating](#a-biometric-enrollment--quality-gating)
   - [B. University Timetable & Scheduling Engine](#b-university-timetable--scheduling-engine)
   - [C. Automated Classroom Attendance](#c-automated-classroom-attendance)
   - [D. Pedagogical Instruction & Activity Logging](#d-pedagogical-instruction--activity-logging)
   - [E. AI-Powered Smart Exam Proctoring](#e-ai-powered-smart-exam-proctoring)
   - [F. Dynamic 5-Tier Suspicion Scoring Engine](#f-dynamic-5-tier-suspicion-scoring-engine)
   - [G. Student Dossiers & Human-in-the-Loop Review](#g-student-dossiers--human-in-the-loop-review)
   - [H. Enterprise Printable HTML Proctoring Reports](#h-enterprise-printable-html-proctoring-reports)
4. [Technology Stack & Architectural Decisions](#technology-stack--architectural-decisions)
5. [Database Architecture & Schema](#database-architecture--schema)
6. [Project Layout](#project-layout)
7. [Installation & Setup](#installation--setup)
8. [Configuration & Settings Guide](#configuration--settings-guide)
9. [Automated Test Suite](#automated-test-suite)
10. [Biometric Privacy, Ethics & Compliance](#biometric-privacy-ethics--compliance)

---

## Executive Overview

Traditional classroom roll-calls waste 10–15 minutes of lecture time and are vulnerable to proxy attendance. Similarly, online and in-person examinations require multiple human invigilators who suffer from fatigue and visual blind spots.

**ClassVision AI** solves both challenges through non-intrusive edge computer vision:

- **Dual-Camera Attendance**: Verifies students close-up at a gate camera (check-in/check-out) and continuously verifies their presence throughout the class using a wide-angle room camera.
- **Timetable-Synchronized**: Pre-seeded with university course schedules (28 default classes, course codes, lecture halls, and sections) to start monitored sessions in one click.
- **Assistive Exam Proctoring**: Evaluates head pose, lip movement, multiple faces, camera blockage, and prohibited electronic gadgets (mobile phones, laptops, smartwatches, notebooks) in real time.
- **Fair, Non-Accusatory AI**: Flags suspicious events with evidence snapshots and confidence metrics for post-exam review. It **never declares a student guilty automatically**.

---

## System Architecture

```
                                  [ Video Source(s) ]
                     Webcam / USB Camera / RTSP IP Stream / Video File
                                           │
                                           ▼
                                [ CameraWorker Thread ]
                           Frame Sampling & OpenCV Capture
                                           │
                                           ▼
                              [ VisionPipeline Worker ]
    ┌──────────────────────────────────────┴──────────────────────────────────────┐
    │                                                                             │
    ▼                                                                             ▼
[ OpenCV YuNet (ONNX) ]                                                [ YOLOv8 Object Detector ]
Face Detection & 5 Landmarks                                           Phones, Laptops, Books
    │                                                                             │
    ├─────────────────────────────┬─────────────────────────────┐                 │
    ▼                             ▼                             ▼                 │
[ SFace (ONNX) ]           [ SolvePnP Pose ]           [ Lip Oscillation ]        │
128-D Embedding Vector      Yaw, Pitch, Roll           Mouth Openness Ratio       │
    │                             │                             │                 │
    ▼                             │                             │                 │
[ Gallery Matcher ]               │                             │                 │
Cosine Similarity + Voting        │                             │                 │
    │                             │                             │                 │
    └─────────────────────────────┼─────────────────────────────┘                 │
                                  ▼                                               ▼
                        [ TrackView Aggregation ] ────────────────────────────────┘
                                  │
                                  ▼
                     [ SessionController (Main Thread) ]
        ┌─────────────────────────┴─────────────────────────┐
        ▼                                                   ▼
[ AttendanceEngine ]                              [ ProctorEngine ]
• Gate Check-in/Out                              • Looking Away (Left/Right/Up)
• Room Presence Time                             • Suspected Talking Detection
• Presence Intervals                             • Multiple Faces / Unknown Person
• Min-Presence Scaling                           • Camera Obstruction Detection
• Break Duration                                 • Dynamic 5-Tier Suspicion Score
        │                                                   │
        └─────────────────────────┬─────────────────────────┘
                                  ▼
                   [ SQLite Database (WAL Mode) ]
          attendance, events, timetable, students, risk_scores
                                  │
                                  ▼
                       [ PySide6 Presentation ]
   Executive Bar ── Live Grid Cards ── Student Dossier ── HTML Report Export
```

---

## Key Modules & Features

### A. Biometric Enrollment & Quality Gating
- **Flexible Photo Ingestion**: Enroll via guided live webcam capture or direct file upload (JPG, PNG, WebP).
- **1-Photo Enrollment Support**: Enrolls students with as little as 1 clear frontal portrait (`enroll_min_samples = 1`) or up to 8 guided multi-angle samples.
- **Biometric Quality Filters**: Automated blur score calculation (Laplacian variance > 40.0), minimum face resolution (> 36 px), and frame ratio validation (> 22%).
- **Duplicate Identity Protection**: Detects if a newly enrolled face already belongs to another registered student.
- **Explicit Consent Recording**: Records ISO timestamped student consent in SQLite.

### B. University Timetable & Scheduling Engine
- **Pre-Seeded Academic Timetable**: Comes pre-populated with **28 weekly classes** across Monday through Saturday seeded from official university timetable records:
  - Subject Codes: `PEA306` (Aptitude), `CSE471` (Cloud Computing Lab), `PES390` (Soft Skills), `CSE408` (Artificial Intelligence), `CSE472` (Big Data Lab), `INT331` (Web Technologies), `PEAS01`, `PEVS01`.
  - Venues: `37-603`, `28-502`, `37-701`, `33-311`, `33-602`, etc.
- **Smart Weekend Fallback**: On Sundays or days without scheduled classes, the system automatically defaults to Monday rather than displaying an empty screen.
- **Dual Visual Modes**:
  - **Schedule Table**: Filterable by Day and Section with time spans, teacher, room, duration, and minimum required presence.
  - **Weekly Calendar Grid**: A 6-column calendar view (Monday–Saturday) showing visual class cards matching university scheduling portals.
- **Instant Class Initiation**: Single-click button **"Start this class now"** auto-fills title, section, duration, minimum presence, and camera settings directly into the live session monitor.

### C. Automated Classroom Attendance
- **Three-Tier Attendance Verification**:
  1. **Gate Check-In**: High-resolution face capture at the entrance door within an arrival window.
  2. **Continuous Room Tracking**: Wide-angle classroom tracking to monitor continuous presence.
  3. **Gate Check-Out**: Departure check-out when the session concludes.
- **Granular Interval Tracking**: Saves exact `(start_ts, end_ts)` spans in `presence_intervals`. Micro-dropouts under 90s are bridged; genuine departures appear as visible breaks.
- **Attendance Classifications**:
  - `PRESENT`: Met minimum required time in room + completed gate checks.
  - `REVIEW`: Met room time but missed gate check (teacher decides).
  - `ABSENT`: Insufficient time spent in the lecture hall.

### D. Pedagogical Instruction & Activity Logging
- **Real-Time Instruction Logger**: Allows lecturers to log formal pedagogical milestones:
  - Preset quick selections: *"Class commenced according to timetable"*, *"Open textbooks / course slides"*, *"Start practical lab assignment"*, *"Group discussion"*, *"Mid-class interval"*, *"Turn in assignments"*.
  - Custom instruction notes field with instant submission.
- **Automatic Lifecycle Events**: Logs `SESSION_START`, `STUDENT_ARRIVED`, `CHECK_IN`, `CHECK_OUT`, and `SESSION_END` directly into the SQLite `events` table.

---

### E. AI-Powered Smart Exam Proctoring

The exam proctoring engine monitors students in real time and detects suspicious behaviors across multiple vision modalities:

```
┌─────────────────────────┬────────────────────────────────────────────────────────┐
│ Activity Flag           │ Detection Methodology                                  │
├─────────────────────────┼────────────────────────────────────────────────────────┤
│ LOOKING_AWAY            │ Head pose yaw past ±40° or pitch > +30° for >= 3.0s   │
│ LOOKING_LEFT            │ Directional yaw < -40° (repeated or prolonged)         │
│ LOOKING_RIGHT           │ Directional yaw > +40° (repeated or prolonged)         │
│ LOOKING_DOWN            │ Configurable pitch < -25° for suspicious note viewing  │
│ REPEATED_LOOKING        │ 5 or more look-aways within a 120-second sliding window│
│ FACE_NOT_VISIBLE        │ Confirmed student disappears from camera for >= 20s    │
│ UNKNOWN_PERSON          │ Unregistered face detected in camera for >= 10s        │
│ MULTIPLE_FACES          │ 2+ simultaneous faces in single-student webcam feed    │
│ DUPLICATE_IDENTITY      │ Same student embedding matched in two places at once   │
│ IDENTITY_CHANGE         │ Tracked seat position switches identity to another sid │
│ SUSPECTED_TALKING       │ Rapid lip opening/closing oscillation from 5 landmarks │
│ CAMERA_OBSTRUCTED       │ Total frame luminance < 12.0 for >= 3.0 seconds        │
│ PROHIBITED_OBJECT       │ YOLOv8 detects cell phone, laptop, or notes near face  │
└─────────────────────────┴────────────────────────────────────────────────────────┘
```

---

### F. Dynamic 5-Tier Suspicion Scoring Engine

Each student's suspicion score ($0 - 100\%$) is computed dynamically based on detection confidence, severity weights, persistence, and room-relative baseline normalization:

$$\text{Score} = \min\left(100,\, 40 \cdot \text{LookAway}_{\text{norm}} + 15 \cdot \text{Bursts} + 10 \cdot \text{Absence} + 35 \cdot \text{Objects} + 35 \cdot \text{IdentityFlags} + 20 \cdot \text{Acoustic/Lip}\right)$$

#### Suspicion Tiers & UI Visual Styling

| Level | Score Range | Status Color | Visual Container Styling |
|:---|:---:|:---:|:---|
| **Normal** | 0 – 19 | Green (`#16a34a`) | Soft green background, emerald border, normal monitoring badge |
| **Low** | 20 – 39 | Light Yellow (`#ca8a04`) | Light yellow card, amber badge, minor warning status |
| **Medium** | 40 – 59 | Orange (`#ea580c`) | Orange accent, attention indicator |
| **High** | 60 – 79 | Red (`#dc2626`) | Red border, high-priority alert box |
| **Critical** | 80 – 100 | Dark Red (`#7f1d1d`) | Crimson container, critical incident indicator |

- **Room-Relative Normalization ($z$-Score)**: Uses median and Median Absolute Deviation ($\text{MAD}$) across the room. If a sudden noise causes all students to turn around together, the entire room is not falsely penalized.
- **Cool-Down & Decay**: Prevents continuous counting of the same incident on adjacent frames while preserving full incident logs.

---

### G. Student Dossiers & Human-in-the-Loop Review
- **Live Student Monitoring Cards (`StudentCardWidget`)**: Responsive grid of cards displaying the student photo, name, registration number, live score bar, tier badge, face detection status, and last activity.
- **Student Examination Dossier (`StudentDetailDialog`)**: Detailed modal with student metadata, attendance stats, activity breakdowns (away %, glances, missing time, objects), and a full incident history with clickable evidence thumbnails.
- **Invigilator Review Decisions (`AlertReviewDialog`)**: Allows administrators to review any flagged incident, inspect the evidence crop, assign a review decision:
  - `Pending Review`
  - `Confirmed Concern`
  - `False Positive`
  - `Resolved`
  - `Escalated`
  and append custom administrative remarks.

---

### H. Enterprise Printable HTML Proctoring Reports
From the **Reports** page, administrators can click **"Export Proctoring Report (HTML)"** to generate an executive report containing:
- Examination metadata, date, room, and duration.
- Executive summary statistics (Total students, alerts flagged, high-concern count).
- Individual student dossiers with base64-embedded biometric face crops.
- Chronological incident tables with detection confidence %, severity, review status, and remarks.
- Embedded evidence screenshot crops.
- Examiner signature block, optimized for printing to PDF or archiving.

---

## Technology Stack & Architectural Decisions

| Layer | Technology | Architectural Rationale |
|:---|:---|:---|
| **Language** | Python 3.10 – 3.13 | High developer velocity, native C-extension support for OpenCV and NumPy. |
| **UI Framework** | PySide6 (Qt 6) | Hardware-accelerated desktop rendering, robust signal/slot concurrency, native OS feel. |
| **Face Detector** | OpenCV YuNet (ONNX) | Lightweight anchor-based CNN (~350 KB). Detects faces and 5 facial landmarks in < 15ms on CPU. |
| **Face Recognizer**| OpenCV SFace (ONNX) | SphereFace architecture (~38 MB). Generates 128-D unit-normalized embeddings robust to lighting. |
| **Head Pose** | OpenCV SolvePnP | Perspective-n-Point algorithm maps 5 2D landmarks to a 3D canonical face model to compute Euler angles. |
| **Object Detection**| Ultralytics YOLOv8n | Ultra-fast Nano model (~6 MB) detecting mobile phones, laptops, and reference books. |
| **Database** | SQLite3 (WAL Mode) | Zero-configuration, zero-latency local relational database. Write-Ahead Logging allows concurrent reads without locking. |
| **Image IO** | Pillow & NumPy | Memory-efficient in-memory array manipulation and JPEG artifact encoding. |

---

## Database Architecture & Schema

All persistent application data resides in a single SQLite database at `data/classvision.db`:

```sql
-- Students and biometric metadata
CREATE TABLE students (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    reg_no        TEXT NOT NULL COLLATE NOCASE UNIQUE,
    name          TEXT NOT NULL,
    role          TEXT NOT NULL DEFAULT 'student',
    email         TEXT, phone TEXT, department TEXT, course TEXT, section TEXT, year TEXT, notes TEXT,
    consent_at    REAL NOT NULL,
    created_at    REAL NOT NULL
);

-- Stored facial embeddings (128-D binary floats)
CREATE TABLE face_samples (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id    INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    image_path    TEXT NOT NULL,
    embedding     BLOB NOT NULL,
    quality       REAL NOT NULL,
    created_at    REAL NOT NULL
);

-- Weekly university timetable schedule
CREATE TABLE timetable (
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

-- Monitored class / exam sessions
CREATE TABLE sessions (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    kind             TEXT NOT NULL,             -- 'class' | 'exam'
    title            TEXT NOT NULL,
    section          TEXT,
    start_ts         REAL NOT NULL,
    duration_min     INTEGER NOT NULL,
    min_presence_min INTEGER NOT NULL,
    status           TEXT NOT NULL DEFAULT 'running', -- 'running' | 'finished' | 'interrupted'
    ended_ts         REAL,
    config_json      TEXT
);

-- Attendance summary per student per session
CREATE TABLE attendance (
    session_id   INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    student_id   INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    check_in_ts  REAL, check_out_ts REAL,
    first_seen   REAL, last_seen REAL,
    present_sec  REAL NOT NULL DEFAULT 0,
    status       TEXT NOT NULL DEFAULT 'ABSENT', -- 'PRESENT' | 'REVIEW' | 'ABSENT'
    reason       TEXT,
    override     INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (session_id, student_id)
);

-- Discrete presence spans
CREATE TABLE presence_intervals (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    student_id  INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    start_ts    REAL NOT NULL,
    end_ts      REAL NOT NULL
);

-- Behavioral proctoring and lifecycle events
CREATE TABLE events (
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
    review_status TEXT DEFAULT 'Pending Review', -- 'Pending Review' | 'Confirmed Concern' | 'False Positive' | 'Resolved' | 'Escalated'
    admin_remarks TEXT DEFAULT ''
);

-- Suspicion risk profiles
CREATE TABLE risk_scores (
    session_id  INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    key         TEXT NOT NULL,
    student_id  INTEGER,
    label       TEXT,
    score       REAL NOT NULL,
    level       TEXT NOT NULL,
    metrics     TEXT,
    PRIMARY KEY (session_id, key)
);
```

---

## Project Layout

```
classvision_ai/
├── main.py                     # Primary GUI application launcher
├── setup.bat / setup.sh        # One-click virtualenv & dependency bootstrap
├── run.bat / run.sh            # Standard execution script
├── requirements.txt            # Python dependencies
├── scripts/
│   ├── doctor.py               # Hardware, camera, and model diagnostic utility
│   └── download_models.py      # Automated ONNX weights downloader
├── app/
│   ├── config.py               # Global settings dataclass & defaults
│   ├── context.py              # Application lifecycle and signal dispatcher
│   ├── db.py                   # SQLite schema, migrations & CRUD methods
│   ├── imgio.py                # Fast image decoding and encoding
│   ├── utils.py                # Timestamp formatting and math helpers
│   ├── vision/
│   │   ├── engine.py           # FaceEngine (YuNet detector + SFace embedding)
│   │   ├── gallery.py          # Fast cosine similarity search & thresholding
│   │   ├── models.py           # Model verification & mirror fallback logic
│   │   ├── objects.py          # YOLOv8 prohibited gadgets detector wrapper
│   │   ├── pipeline.py         # Multi-stage vision processing worker
│   │   ├── pose.py             # SolvePnP head pose estimation (Yaw/Pitch/Roll)
│   │   ├── tracker.py          # Multi-face IoU tracker & voting manager
│   │   └── types.py            # Immutable data structures (TrackView, Det)
│   ├── services/
│   │   ├── attendance.py       # Attendance rules engine & gate windowing
│   │   ├── enrollment.py       # Biometric quality gate & frame sampler
│   │   ├── exports.py          # CSV data export routines
│   │   └── proctor.py          # Suspicion scoring engine & proctoring rules
│   ├── workers/
│   │   ├── camera.py           # OpenCV threaded video stream reader
│   │   └── session.py          # SessionController orchestrating live sessions
│   └── ui/
│       ├── main_window.py      # Main window shell & navigation sidebar
│       ├── theme.py            # Fusion style tokens, colors & stylesheets
│       ├── widgets.py          # Custom reusable Qt components
│       ├── proctor_dialogs.py  # StudentCardWidget, Dossier & Review dialogs
│       └── pages/
│           ├── dashboard.py    # Metric summary & quick launch links
│           ├── timetable.py    # Schedule table & weekly calendar view
│           ├── live.py         # Real-time monitoring & student cards grid
│           ├── enroll.py       # Student enrollment & webcam capture
│           ├── students.py     # Student records directory & photo manager
│           ├── reports.py      # Session archives, CSV & HTML report export
│           └── settings.py     # System-wide configurable thresholds
├── tests/
│   ├── test_core.py            # Vision pipeline, tracker & math tests
│   ├── test_session_flow.py    # Live session lifecycle integration tests
│   ├── test_ui_smoke.py        # Complete Qt UI smoke suite
│   ├── test_timetable_and_features.py # Timetable, subcodes & 1-photo tests
│   └── test_proctor_enterprise.py     # Advanced proctoring & HTML report tests
└── data/                       # Local runtime directory (DB, photos, evidence)
```

---

## Installation & Setup

### Prerequisites
- **Python**: Version 3.10 to 3.13 installed (ensure *"Add Python to PATH"* is checked on Windows).
- **Webcam**: Built-in laptop camera, USB webcam, or RTSP network IP camera.

### Quick Start (Windows)
Double-click `setup.bat` once. When complete, double-click `run.bat` to launch the application.

### Manual Setup (All Platforms)

1. **Clone & Create Environment**:
   ```bash
   git clone https://github.com/your-org/classvision_ai.git
   cd classvision_ai
   python -m venv .venv
   ```

2. **Activate Environment**:
   - **Windows**: `.venv\Scripts\activate`
   - **macOS / Linux**: `source .venv/bin/activate`

3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Verify Hardware & Models**:
   ```bash
   python scripts/doctor.py
   ```
   *The doctor utility inspects your Python version, cameras, OpenCV backend, and verifies the presence of the ONNX models.*

5. **Launch ClassVision AI**:
   ```bash
   python main.py
   ```

---

## Configuration & Settings Guide

All system parameters are configurable via the **Settings** page in the application or stored as JSON in `data/settings.json`:

```
┌───────────────────────────────┬─────────┬─────────────────────────────────────────────────┐
│ Setting Parameter             │ Default │ Description                                     │
├───────────────────────────────┼─────────┼─────────────────────────────────────────────────┤
│ enroll_min_samples            │ 1       │ Minimum face photos required to enroll a person │
│ enroll_samples                │ 8       │ Target photos captured during guided capture    │
│ recog_threshold               │ 0.40    │ Cosine similarity threshold for face match      │
│ recog_margin                  │ 0.04    │ Margin required over runner-up identity         │
│ det_score_threshold           │ 0.80    │ YuNet face detector confidence threshold        │
│ vote_window / vote_required   │ 5 / 3   │ Votes required over recent frames to confirm id │
│ yaw_limit_deg                 │ 40.0°   │ Head yaw angle considered looking away          │
│ pitch_up_limit_deg            │ 30.0°   │ Head pitch up considered looking away           │
│ look_away_sec                 │ 3.0s    │ Continuous gaze departure required for alert   │
│ glance_count / glance_window  │ 5 / 120s│ Repeated look-aways within window               │
│ missing_sec                   │ 20.0s   │ Duration an identified face can disappear       │
│ unknown_sec                   │ 10.0s   │ Duration an unrecognized face can stay in frame │
│ detect_talking                │ True    │ Real-time lip oscillation speaking detection    │
│ detect_obstruction            │ True    │ Camera lens cover detection                     │
│ detect_multiple_faces         │ False   │ Single-student proctoring multi-person flag     │
│ object_detection              │ False   │ Enable YOLOv8 for phones, laptops, and books    │
│ weight_phone / weight_talking │ 35 / 20 │ Suspicion contribution weights for activities   │
└───────────────────────────────┴─────────┴─────────────────────────────────────────────────┘
```

---

## Automated Test Suite

ClassVision AI maintains **98 automated tests** covering core computer vision algorithms, database migrations, UI pages, and proctoring rules:

```bash
# Run the complete test suite
python -m unittest tests/test_core.py tests/test_session_flow.py tests/test_ui_smoke.py tests/test_timetable_and_features.py tests/test_proctor_enterprise.py
```

### Test Coverage Highlights:
- **`test_core.py`**: Tracker IoU calculation, gallery voting, head pose SolvePnP, robust z-score normalizations.
- **`test_session_flow.py`**: Session start/stop transitions, presence interval bridging, gate check-in/out logic.
- **`test_ui_smoke.py`**: Headless Qt rendering smoke tests across all tabs and dialogs.
- **`test_timetable_and_features.py`**: Database seeding of the 28 classes, subcode assignment, 1-photo enrollment validation.
- **`test_proctor_enterprise.py`**: Lip oscillation talking detection, lens obstruction, 5-tier scoring verification, HTML report compilation.

---

## Biometric Privacy, Ethics & Compliance

Facial geometry and biometric embeddings constitute sensitive personal data under global regulations (GDPR, FERPA, India DPDP Act). **ClassVision AI** was built with privacy-by-design principles:

1. **Local-First Zero-Cloud Execution**: All face detection, feature vector extraction, and database persistence occur strictly on the institution's local computer. No frames, embeddings, or logs are transmitted over the internet.
2. **Recorded Consent**: Students must provide recorded consent prior to biometric enrollment.
3. **Right to Erasure**: Deleting a student profile cleanly purges their database records, face embeddings, and JPEG sample files from disk.
4. **Assistive, Non-Punitive Philosophy**: AI indicators are designed solely to highlight potential irregularities for human invigilator review. The system intentionally avoids issuing automated disciplinary actions.

---

## License

ClassVision AI is licensed under the **MIT License**. OpenCV models (**YuNet** & **SFace**) are distributed under MIT and Apache-2.0 licenses via the [OpenCV Zoo](https://github.com/opencv/opencv_zoo).
#   c l a s s - v i s i o n - a i  
 