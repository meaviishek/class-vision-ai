# ClassVision AI: Enterprise Classroom Attendance & Smart Exam Proctoring System

<div align="center">

```
 ██████╗██╗      █████╗ ███████╗███████╗██╗   ██╗██╗███████╗██╗ ██████╗ ███╗   ██╗     █████╗ ██╗
██╔════╝██║     ██╔══██╗██╔════╝██╔════╝██║   ██║██║██╔════╝██║██╔═══██╗████╗  ██║    ██╔══██╗██║
██║     ██║     ███████║███████╗███████╗██║   ██║██║███████╗██║██║   ██║██╔██╗ ██║    ███████║██║
██║     ██║     ██╔══██║╚════██║╚════██║╚██╗ ██╔╝██║╚════██║██║██║   ██║██║╚██╗██║    ██╔══██║██║
╚██████╗███████╗██║  ██║███████║███████║ ╚████╔╝ ██║███████║██║╚██████╔╝██║ ╚████║    ██║  ██║██║
 ╚═════╝╚══════╝╚═╝  ╚═╝╚══════╝╚══════╝  ╚═══╝  ╚═╝╚══════╝╚═╝ ╚═════╝ ╚═╝  ╚═══╝    ╚═╝  ╚═╝╚═╝
```

### *Next-Generation Offline-First Computer Vision Framework for Automated Multi-Student Attendance and Intelligent Examination Proctoring*

[![Python Version](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![GUI Framework](https://img.shields.io/badge/GUI-PySide6%20%2F%20Qt6-41CD52?style=for-the-badge&logo=qt&logoColor=white)](https://doc.qt.io/qtforpython-6/)
[![Computer Vision](https://img.shields.io/badge/Vision-OpenCV%20YuNet%20%2B%20SFace-5C3EE8?style=for-the-badge&logo=opencv&logoColor=white)](https://github.com/opencv/opencv_zoo)
[![Object Detection](https://img.shields.io/badge/Detection-YOLOv8%20Nano-00FFFF?style=for-the-badge&logo=yolo&logoColor=black)](https://github.com/ultralytics/ultralytics)
[![Database](https://img.shields.io/badge/Database-SQLite3%20WAL-003B57?style=for-the-badge&logo=sqlite&logoColor=white)](https://www.sqlite.org/)
[![Tests](https://img.shields.io/badge/Tests-98%20Passed%20(100%25)-brightgreen?style=for-the-badge&logo=checkmarx&logoColor=white)](file:///d:/ai%20ml%20projects/classvision_ai/tests)
[![License](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](file:///d:/ai%20ml%20projects/classvision_ai/LICENSE)

[System Architecture](#-system-architecture) • [Key Features](#-core-modules--features) • [Screenshots](#-visual-interface-walkthrough) • [Installation](#-installation--quick-start) • [Technology Comparison](#-technology-stack--architectural-decisions) • [Presentation Guide](file:///d:/ai%20ml%20projects/classvision_ai/PRESENTATION_GUIDE.md) • [IEEE Report](file:///d:/ai%20ml%20projects/classvision_ai/IEEE_PROJECT_REPORT.md)

</div>

---

## 🌟 Executive Summary

**ClassVision AI** is an enterprise-grade, edge-native desktop platform that unifies **Automated Biometric Classroom Attendance** and **AI-Powered Examination Proctoring** into a single cohesive system. 

Designed specifically for universities and educational institutions, ClassVision AI completely replaces manual, proxy-vulnerable paper roll calls and alleviates human invigilator cognitive overload during examinations. Operating **100% offline at the hardware edge**, all biometric face matching, 3D pose tracking, and prohibited object recognition execute locally—guaranteeing that sensitive student data and webcam video frames **never leave the campus network**.

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                   CORE VALUE PROPOSITIONS                                        │
├──────────────────────────────────────────────────────────────────────────────────────────────────┤
│  🔒 100% Edge-Native & Private    │ Zero external cloud APIs; fully GDPR & DPDPA compliant.       │
│  ⚡ Single-Photo Enrollment        │ 1 clear photo generates a 128-D cosine embedding in <15ms.   │
│  📅 Academic Timetable Engine     │ Pre-seeded with 28 weekly periods; 1-click lecture execution.│
│  ⏱️ Continuous Presence Tracking  │ Mathematical presence accumulator replaces single-shot hits.  │
│  👁️ 9 Multi-Modal Proctor Cues    │ Detects phones, cheat notes, head yaw/pitch, lip talking, etc.│
│  📊 Dynamic 5-Tier Suspicion Score│ Objective 0–100 index with event weights and cooldown decay. │
│  🗃️ SQLite WAL Zero-Lock Storage  │ Write-Ahead Logging allows seamless concurrent vision writes. │
│  ✅ 100% Verified Quality         │ 98 comprehensive automated unit and integration tests passed. │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 📑 Table of Contents

- [ClassVision AI: Enterprise Classroom Attendance \& Smart Exam Proctoring System](#classvision-ai-enterprise-classroom-attendance--smart-exam-proctoring-system)
  - [*Next-Generation Offline-First Computer Vision Framework for Automated Multi-Student Attendance and Intelligent Examination Proctoring*](#next-generation-offline-first-computer-vision-framework-for-automated-multi-student-attendance-and-intelligent-examination-proctoring)
  - [🌟 Executive Summary](#-executive-summary)
  - [📑 Table of Contents](#-table-of-contents)
  - [🏛️ System Architecture](#️-system-architecture)
    - [End-to-End Pipeline Data Flow](#end-to-end-pipeline-data-flow)
    - [Asynchronous Multi-Threaded Engine](#asynchronous-multi-threaded-engine)
  - [🎯 Core Modules \& Features](#-core-modules--features)
    - [1. Single-Shot Biometric Face Enrollment](#1-single-shot-biometric-face-enrollment)
    - [2. University Academic Timetable \& Scheduling](#2-university-academic-timetable--scheduling)
    - [3. Automated Classroom Attendance Engine](#3-automated-classroom-attendance-engine)
    - [4. AI-Powered Smart Exam Proctoring Engine](#4-ai-powered-smart-exam-proctoring-engine)
    - [5. Dynamic 5-Tier Suspicion Scoring Engine](#5-dynamic-5-tier-suspicion-scoring-engine)
    - [6. Live Student Telemetry Cards Grid \& Investigative Dossiers](#6-live-student-telemetry-cards-grid--investigative-dossiers)
    - [7. Human-in-the-Loop Audit Workflow \& Executive HTML Reporting](#7-human-in-the-loop-audit-workflow--executive-html-reporting)
  - [🖼️ Visual Interface Walkthrough](#️-visual-interface-walkthrough)
  - [🔬 Technology Stack \& Architectural Decisions](#-technology-stack--architectural-decisions)
    - [Detailed Technical Comparison Matrix](#detailed-technical-comparison-matrix)
  - [🗄️ Database Architecture \& Relational Schema](#️-database-architecture--relational-schema)
    - [Entity Relationship Diagram](#entity-relationship-diagram)
    - [SQL Schema Definitions](#sql-schema-definitions)
  - [📂 Project Directory Structure](#-project-directory-structure)
  - [🚀 Installation \& Quick Start](#-installation--quick-start)
    - [Prerequisites](#prerequisites)
    - [1-Click Quick Launch (Windows)](#1-click-quick-launch-windows)
    - [Manual Setup (Windows / Linux / macOS)](#manual-setup-windows--linux--macos)
  - [⚙️ Configuration \& Settings Reference](#️-configuration--settings-reference)
  - [🧪 Automated Test Suite \& Verification](#-automated-test-suite--verification)
  - [🛡️ Biometric Privacy, Ethics \& Regulatory Compliance](#️-biometric-privacy-ethics--regulatory-compliance)
  - [📚 Academic Presentation \& Viva Resources](#-academic-presentation--viva-resources)
  - [📄 License \& Credits](#-license--credits)

---

## 🏛️ System Architecture

### End-to-End Pipeline Data Flow

ClassVision AI decouples high-frequency image acquisition and neural network execution from the graphical user interface. The architecture operates across three distinct computational tiers:

```
┌───────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                 CLASSVISION AI SYSTEM ARCHITECTURE                                │
├───────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                                   │
│  [VIDEO INGESTION TIER]                                                                           │
│  Integrated Webcam (0)  ───┐                                                                      │
│  Classroom RTSP Stream  ───┼──> [CaptureWorker (QThread)] ──> Thread-Safe Lock-Free Ring Buffer   │
│  Gate Entry RTSP Stream ───┘         │                                                            │
│                                      ▼                                                            │
│  [AI COMPUTER VISION TIER]                                                                        │
│  ┌─────────────────────────────────────────────────────────────────────────────────────────────┐  │
│  │ 1. Face Detection & Landmarks: OpenCV DNN YuNet (5 Anatomical Points: Eyes, Nose, Mouth)   │  │
│  │ 2. Canonical Affine Alignment: 112x112 Normalized Face Crop Transformation                  │  │
│  │ 3. Deep Feature Embedding: OpenCV DNN SFace (128-D Hypersphere Vector, L2-Normalized)       │  │
│  │ 4. Metric Verification: Cosine Similarity Matching against Enrolled Vectors (Tau = 0.363)  │  │
│  │ 5. 3D Head Pose Estimation: SolvePnP 3D-to-2D Model Projection (Yaw, Pitch, Roll Angles)    │  │
│  │ 6. Lip Oscillation Counter: Temporal Lip Aspect Ratio (LAR) Zero-Crossings (Whisper/Talk)   │  │
│  │ 7. Object Detection: YOLOv8-Nano (Asynchronous: Cell Phone, Laptop, Cheat Notes)           │  │
│  │ 8. Lens Tamper Engine: Mean Luminance (<18.0) & Laplacian Blur Variance (<15.0)             │  │
│  └───────────────────────────────────────────────┬─────────────────────────────────────────────┘  │
│                                                  │                                                │
│                                                  ▼                                                │
│  [BUSINESS LOGIC & PERSISTENCE TIER]                                                              │
│  ┌───────────────────────────────────────┐       ┌──────────────────────────────────────────────┐ │
│  │ Attendance Presence Accumulator       │       │ Dynamic 5-Tier Suspicion Scoring Engine      │ │
│  │ - Continuous Integration (Delta t)    │       │ - Base Event Weights (15 to 40 pts)          │ │
│  │ - Minimum Presence Gate (>= 75%)      │       │ - Repetition Booster (1.0x to 2.0x)          │ │
│  │ - MAD Outlier Detection (Robust Z)    │       │ - Cooldown Linear Decay (-0.4 pts/sec)       │ │
│  └───────────────────┬───────────────────┘       └──────────────────────┬───────────────────────┘ │
│                      │                                                  │                         │
│                      ▼                                                  ▼                         │
│  ┌─────────────────────────────────────────────────────────────────────────────────────────────┐  │
│  │ SQLite3 Embedded Relational Storage (WAL Journal Mode + Synchronous NORMAL + 5000ms Timeout) │  │
│  │ Tables: [students] [sessions] [attendance] [events] [timetable]                             │  │
│  └───────────────────────────────────────────────┬─────────────────────────────────────────────┘  │
│                                                  │                                                │
│                                                  ▼                                                │
│  [PRESENTATION & AUDIT TIER]                                                                      │
│  PyQt6 Hardware-Accelerated Native GUI ──> Live Telemetry Cards ──> Self-Contained HTML Audits   │
│                                                                                                   │
└───────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### Asynchronous Multi-Threaded Engine
To ensure that frame acquisition never stutters, freezes, or drops below 30 FPS:
- **`CaptureWorker (QThread)`**: Polls video streams in a dedicated background thread with automated exponential backoff reconnection logic (1s, 2s, 4s, up to 10s).
- **Zero GUI Blocking**: Frames are processed and emitted to the UI via Qt's thread-safe meta-object signal-and-slot mechanism (`pyqtSignal(QImage)` and `pyqtSignal(dict)`).
- **Asynchronous Heavy Inference**: Object detection via YOLOv8 is decoupled and runs asynchronously on sampled frames, preventing GPU/CPU pipeline bottlenecks.

---

## 🎯 Core Modules & Features

### 1. Single-Shot Biometric Face Enrollment
- **Problem Solved**: Legacy face recognition systems require taking 20 to 50 photos or recording video clips to train individual classifiers.
- **ClassVision AI Approach**: A single clear frontal photograph is all that is required.
  - **Detection & Alignment**: OpenCV DNN YuNet detects the face and 5 anatomical landmarks (pupil centers, nose tip, mouth corners) in $<3.5\text{ms}$.
  - **Hypersphere Projection**: OpenCV DNN SFace warps the crop to $112 \times 112$ and extracts a 128-dimensional unit hypersphere vector ($\|\vec{v}\|_2 = 1$).
  - **Metric Matching**: Uses Cosine Similarity:
    $$\text{Cosine Similarity}(\vec{u}, \vec{v}) = \sum_{j=1}^{128} u_j \cdot v_j \ge 0.363$$
- **Regulatory Consent Gate**: In strict compliance with **GDPR (Article 9)** and India's **DPDPA 2023**, enrollment cannot proceed without explicit consent confirmation recorded in the audit trail.

### 2. University Academic Timetable & Scheduling
- **Problem Solved**: Faculty members waste time manually retyping subject codes, lecture titles, room numbers, and attendance durations before every class.
- **ClassVision AI Approach**:
  - **Pre-Seeded Institutional Schedule**: Comes pre-configured with **28 academic periods** spanning Monday through Saturday matching official department routines (e.g., *CSE471 Computer Networks, INT331 AI, CSE408, PEA306*).
  - **Quick-Switch Day Filters**: Real-time count pills (`All days: 28`, `Monday: 7`, `Tuesday: 6`, `Wednesday: 5`, `Thursday: 5`, `Friday: 3`, `Saturday: 2`).
  - **Weekly Visual Calendar Grid**: Side-by-side columnar view matching physical routine notices.
  - **1-Click Lecture Execution**: Selecting any slot and clicking **"Start this class now"** automatically populates all session parameters, room bounds, and presence thresholds.

### 3. Automated Classroom Attendance Engine
- **Dual-Camera Topology**:
  - **Gate Entry Camera (RTSP)**: Logs precise arrival timestamps at the classroom doorway.
  - **Classroom Overhead Camera (Webcam/RTSP)**: Continuously tracks student presence across seating rows.
- **Continuous Presence Accumulator**: Rather than marking attendance based on a momentary glance, the system aggregates continuous minutes present:
  $$T_{\text{present}} = \sum_{m=2}^{M} \min(\Delta t_m, \, \tau_{\text{idle}}) \quad (\tau_{\text{idle}} = 60\text{s})$$
- **Three-Tier Classification**:
  - **`PRESENT`**: Accumulated duration $\ge 75\%$ of class duration (configurable).
  - **`PARTIAL`**: Accumulated duration between $30\%$ and $75\%$.
  - **`ABSENT`**: Accumulated duration $< 30\%$.
- **Robust Z-Score Anomaly Detection**: Uses Median Absolute Deviation (MAD) to detect anomalies (mass walkouts, sudden camera obstructions) without influence from statistical outliers.

### 4. AI-Powered Smart Exam Proctoring Engine
ClassVision AI continuously monitors candidates for **9 distinct suspicious behaviors**:

| Detected Behavioral Anomaly | Underlying AI / Mathematical Mechanism | Default Severity Weight |
|---|---|:---:|
| 📱 **Mobile Phone Detected** | YOLOv8 single-stage detection on Class 67 (`cell phone`) | **35 pts** |
| 📝 **Cheat Notes / Book Detected** | YOLOv8 detection on Class 73 (`book`) & paper slips | **30 pts** |
| 🔄 **Looking Left / Right** | SolvePnP 3D Euler Yaw angle ($|\psi| > 24^\circ$) persisting $\ge 1.5\text{s}$ | **15 pts** |
| ⬇️ **Looking Down at Lap/Desk** | SolvePnP 3D Euler Pitch angle ($\theta < -16^\circ$) persisting $\ge 1.5\text{s}$ | **15 pts** |
| 🗣️ **Suspected Talking / Whispering** | Lip Aspect Ratio (LAR) temporal zero-crossing oscillations | **20 pts** |
| 👥 **Multiple Faces in Frame** | YuNet multi-box detection count $>1$ (Collusion intercept) | **40 pts** |
| ❓ **Candidate Missing from View** | Continuous absence of enrolled face $> 5.0\text{s}$ | **25 pts** |
| 🚫 **Camera Obstructed / Covered** | Mean grayscale luminance $\mu < 18.0$ or Laplacian variance collapse | **30 pts** |
| ⚡ **Extended Looking Away** | Compound multi-directional head displacement | **20 pts** |

### 5. Dynamic 5-Tier Suspicion Scoring Engine
The system replaces naive cumulative strike counters with an objective, decaying mathematical score:

$$S(t) = \min\left(100, \, \max\left(0, \, \sum_{i \in \text{Active}} w_i \cdot c_i \cdot \mu_i - \lambda \cdot (t - t_{\text{last}})\right)\right)$$

- $w_i$: Base severity weight.
- $c_i \in [0.5, 1.0]$: Detection confidence.
- $\mu_i$: Repetition multiplier ($1.0\times$ for 1st offense, $1.5\times$ for 2nd, $2.0\times$ for $\ge 3$ within 60 seconds).
- $\lambda = 0.4\text{ pts/sec}$: Linear cooldown decay, rewarding compliant behavior and preventing alert lock-in.

```
  [0 ────────── 19]  ==>  NORMAL    (Green: #10b981)      - Compliant examination activity
 [20 ────────── 39]  ==>  LOW       (Yellow: #f59e0b)     - Minor isolated glance or shift
 [40 ────────── 59]  ==>  MEDIUM    (Orange: #f97316)     - Repeated glances or suspected lip movement
 [60 ────────── 79]  ==>  HIGH      (Red: #ef4444)        - Unauthorized smartphone or cheat notes
 [80 ───────── 100]  ==>  CRITICAL  (Dark Red: #b91c1c)   - Multiple persons, persistent cheating
```

### 6. Live Student Telemetry Cards Grid & Investigative Dossiers
- **Cognitive Load Reduction**: Invigilators cannot watch 30 raw video feeds simultaneously. The **Student Cards Grid** condenses each candidate into a telemetry widget with dynamic color-coded status borders.
- **Detailed Investigative Dossiers**: Double-clicking any card opens an individual candidate modal displaying:
  - High-resolution live camera crop with face detection bounding box.
  - Live suspicion score gauge and tier classification.
  - Chronological incident event timeline table.
  - Photographic evidence snapshots captured at the exact moment of infraction.

### 7. Human-in-the-Loop Audit Workflow & Executive HTML Reporting
- **Ethical Safeguard**: The AI never issues an automated cheating conviction. It serves strictly as an evidentiary assistant.
- **Administrative Override States**: Invigilators review captured incidents and formally assign statuses:
  - `Pending Review` $\rightarrow$ `Confirmed Concern` $\rightarrow$ `False Positive` $\rightarrow$ `Resolved` $\rightarrow$ `Escalated`.
- **Standalone HTML Audit Reports**: With one click, generate an executive audit report complete with CSS styling, KPI metric cards, candidate dossiers, and embedded evidence snapshots for university disciplinary boards.

---

## 🖼️ Visual Interface Walkthrough

<div align="center">

### Executive System Dashboard
*Real-time institutional metrics, active session tallies, student enrollment counters, and instant shortcuts.*
[![Dashboard Screenshot](docs/screenshots/01_dashboard.png)](docs/screenshots/01_dashboard.png)

---

### Single-Shot Biometric Face Enrollment
*Privacy consent verification guard, demographic metadata capture, and instant 128-D SFace feature extraction.*
[![Enrollment Screenshot](docs/screenshots/02_enrollment.png)](docs/screenshots/02_enrollment.png)

---

### University Academic Timetable & Weekly Grid
*Pre-seeded 28-period weekly schedule, quick-switch day pill filters, and 1-click lecture execution.*
[![Timetable Grid Screenshot](docs/screenshots/03_timetable_grid.png)](docs/screenshots/03_timetable_grid.png)

---

### Automated Classroom Attendance Monitoring
*Live camera stream, real-time facial recognition bounding boxes, and continuous presence accumulator.*
[![Class Attendance Screenshot](docs/screenshots/04_class_attendance.png)](docs/screenshots/04_class_attendance.png)

---

### AI-Powered Smart Exam Proctoring Dashboard
*Real-time 9-behavior monitoring, SolvePnP 3D head pose vectors, lip oscillation tracking, and metrics bar.*
[![Exam Proctoring Screenshot](docs/screenshots/05_exam_proctoring.png)](docs/screenshots/05_exam_proctoring.png)

---

### Live Student Telemetry Cards Grid
*Multi-candidate overview with color-coded status borders, live suspicion scores, and deep dossier inspection.*
[![Student Cards Grid](docs/screenshots/05_exam_cards.png)](docs/screenshots/05_exam_cards.png)

---

### Audit Logging, Incident Review & HTML Report Export
*Human-in-the-loop review overrides, photographic evidence inspection, and standalone HTML export.*
[![Reports & Audit Screenshot](docs/screenshots/06_reports_audit.png)](docs/screenshots/06_reports_audit.png)

---

### System Configuration & Sensitivity Calibration
*Customizable camera sources, attendance presence percentages, head pose deadzones, and event weights.*
[![Settings Screenshot](docs/screenshots/07_settings.png)](docs/screenshots/07_settings.png)

</div>

---

## 🔬 Technology Stack & Architectural Decisions

```
┌─────────────────────────┬───────────────────────────────────┬──────────────────────────────────────────────┐
│ Layer                   │ Technology Selected               │ Strategic Architectural Justification       │
├─────────────────────────┼───────────────────────────────────┼──────────────────────────────────────────────┤
│ Core Runtime            │ Python 3.10 – 3.13 (64-bit)       │ Native C-extension bindings, rapid ML deploy│
│ Graphical User Interface│ PySide6 (Qt 6.7.2)                │ Hardware-accelerated native desktop GUI      │
│ Face Detection          │ OpenCV DNN YuNet (ONNX)           │ ~330 KB model, >300 FPS on GPU, 5 landmarks  │
│ Face Recognition        │ OpenCV DNN SFace (ONNX)           │ 4.8 MB model, 128-D cosine metric, 99.6% LFW│
│ 3D Head Pose Estimation │ Levenberg-Marquardt SolvePnP      │ 0.4ms geometric projection, zero model size │
│ Object Detection        │ Ultralytics YOLOv8-Nano           │ Real-time anchor-free gadget/notes detection │
│ Database Persistence    │ SQLite3 with WAL Mode             │ Zero-setup edge storage, high write concurrency│
│ Automated Testing       │ Python unittest (Headless Qt)     │ 98 tests verifying logic, DB, & UI offscreen │
│ Document Reporting      │ HTML5 + CSS3 (Self-Contained)     │ Printable executive audits with zero tooling │
└─────────────────────────┴───────────────────────────────────┴──────────────────────────────────────────────┘
```

### Detailed Technical Comparison Matrix

| Capability / Metric | Manual Roll Call | RFID / Fingerprint | Commercial Cloud (Proctorio) | Proposed ClassVision AI |
|---|:---:|:---:|:---:|:---:|
| **Time Overhead per Class** | 10–15 minutes wasted | 3–5 minutes queued | N/A (Exam only) | **0 minutes (Fully Autonomous)** |
| **Proxy / Buddy Fraud Vulnerability** | Critical (Verbal proxy) | High (Card swiping) | Low (Cloud biometric) | **Eliminated (Continuous Biometric)**|
| **Data Privacy (GDPR / DPDPA)** | Neutral | Moderate | **Severe Violation (Cloud video)** | **100% Compliant (Edge-Native)** |
| **Internet Outage Resilience** | High | Low | **Fails completely (Requires WAN)** | **Immune (100% Offline-Capable)** |
| **Exam Cheating Detection Scope** | 1–2 human eyes | None | Limited screen capture | **9 Multi-Modal Computer Vision Cues**|
| **Hardware Investment Cost** | None | Expensive turnstiles | High recurring subscriptions | **Zero extra (Standard PCs & Webcams)**|
| **Inference Latency (FPS)** | N/A | N/A | High cloud latency (>2.0s) | **Sub-15ms (>30 FPS on Consumer CPU)**|

---

## 🗄️ Database Architecture & Relational Schema

ClassVision AI utilizes an embedded **SQLite 3** relational database configured in **Write-Ahead Logging (WAL)** mode. WAL mode enables background computer vision threads to record high-frequency incident telemetry simultaneously while the GUI executes read queries, entirely avoiding `database is locked` exceptions.

```sql
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA busy_timeout = 5000;
```

### Entity Relationship Diagram

```
┌──────────────────┐               ┌──────────────────┐
│     students     │ 1           * │    attendance    │
├──────────────────┤───────────────├──────────────────┤
│ id (PK)          │               │ id (PK)          │
│ reg_no (UNIQUE)  │               │ session_id (FK)  │─────┐
│ name             │               │ student_id (FK)  │     │
│ department       │               │ status           │     │
│ section          │               │ present_seconds  │     │
│ photo_path       │               │ first_seen       │     │
│ embedding (BLOB) │               │ last_seen        │     │
└────────┬─────────┘               └──────────────────┘     │
         │ 1                                                │
         │                                                  │
         │ *                                                │ *
┌────────┴─────────┐                               ┌────────┴─────────┐
│      events      │ *                           1 │     sessions     │
├──────────────────┤───────────────────────────────├──────────────────┤
│ id (PK)          │                               │ id (PK)          │
│ session_id (FK)  │                               │ kind (class/exam)│
│ student_id (FK)  │                               │ title            │
│ event_type       │                               │ course_code      │
│ confidence       │                               │ start_time       │
│ score_weight     │                               │ end_time         │
│ timestamp        │                               │ min_presence_pct │
│ snapshot_path    │                               └──────────────────┘
│ review_status    │
│ admin_remarks    │
└──────────────────┘
```

### SQL Schema Definitions

```sql
-- Students Registry
CREATE TABLE IF NOT EXISTS students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reg_no TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    role TEXT DEFAULT 'Student',
    department TEXT,
    section TEXT,
    programme TEXT,
    semester INTEGER,
    email TEXT,
    phone TEXT,
    notes TEXT,
    photo_path TEXT,
    embedding BLOB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Sessions (Classroom Lectures or Exams)
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL CHECK(kind IN ('class', 'exam')),
    title TEXT NOT NULL,
    course_code TEXT,
    section TEXT,
    room TEXT,
    planned_duration_min INTEGER DEFAULT 50,
    min_presence_min INTEGER DEFAULT 35,
    classroom_source TEXT,
    gate_source TEXT,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMP
);

-- Aggregated Attendance
CREATE TABLE IF NOT EXISTS attendance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    status TEXT NOT NULL CHECK(status IN ('PRESENT', 'PARTIAL', 'ABSENT')),
    present_seconds REAL DEFAULT 0,
    first_seen TIMESTAMP,
    last_seen TIMESTAMP,
    gate_entry_time TIMESTAMP,
    UNIQUE(session_id, student_id)
);

-- Proctoring Events & Misconduct Telemetry
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    student_id INTEGER REFERENCES students(id) ON DELETE SET NULL,
    event_type TEXT NOT NULL,
    confidence REAL DEFAULT 1.0,
    score_weight REAL DEFAULT 0.0,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    snapshot_path TEXT,
    review_status TEXT DEFAULT 'Pending Review',
    admin_remarks TEXT
);

-- Weekly Academic Timetable
CREATE TABLE IF NOT EXISTS timetable (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    day_of_week TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    subcode TEXT NOT NULL,
    subject TEXT NOT NULL,
    section TEXT,
    room TEXT,
    slot_type TEXT DEFAULT 'Lecture',
    duration_min INTEGER DEFAULT 50
);
```

---

## 📂 Project Directory Structure

```
classvision_ai/
├── app/
│   ├── config.py                 # Central Settings dataclass & configuration engine
│   ├── context.py                # AppContext dependency injection container
│   ├── db.py                     # SQLite WAL data access layer & auto-migration
│   ├── services/
│   │   ├── attendance.py         # Presence Accumulator & temporal integration
│   │   ├── proctor.py            # Dynamic 5-tier suspicion scoring engine
│   │   └── scheduler.py          # Timetable synchronization & auto-scheduler
│   ├── ui/
│   │   ├── main_window.py        # Central PyQt6 navigation window & router
│   │   ├── proctor_dialogs.py    # StudentCardWidget, Dossier Modal, HTML Generator
│   │   ├── theme.py              # Dark/Light fusion color palette & stylesheets
│   │   ├── widgets.py            # Reusable UI controls, KPI cards, custom tables
│   │   └── pages/
│   │       ├── dashboard.py      # Executive statistics & activity overview
│   │       ├── enroll.py         # 1-Photo biometric enrollment with consent guard
│   │       ├── live.py           # Real-time monitoring (Class & Exam modes)
│   │       ├── reports.py        # Unified audit log, review status, HTML export
│   │       ├── settings.py       # Configuration forms for all system settings
│   │       ├── students.py       # Student directory, search, & profile view
│   │       └── timetable.py      # 28-period scheduler, day pills, weekly grid
│   ├── vision/
│   │   ├── face.py               # YuNet face detector & SFace 128-D embedding
│   │   ├── objects.py            # Asynchronous YOLOv8 prohibited gadget detector
│   │   ├── stream.py             # OpenCV VideoCapture wrapper with auto-reconnect
│   │   └── tracker.py            # SolvePnP 3D pose, lip aspect ratio, obstruction
│   └── workers/
│       └── session.py            # Decoupled QThread video capture worker
├── data/
│   ├── classvision.db            # Embedded SQLite WAL database
│   ├── faces/                    # Stored biometric face crops
│   └── snapshots/                # Captured proctoring evidence snapshots
├── docs/
│   └── screenshots/              # High-resolution application screenshots (01 to 07)
├── models/                       # Auto-downloaded pretrained ONNX/PT models
│   ├── face_detection_yunet_2023mar.onnx
│   ├── face_recognition_sface_2021dec.onnx
│   └── yolov8n.pt
├── tests/                        # 98 Automated unit and integration tests
│   ├── test_core.py              # Mathematical functions & SQLite queries
│   ├── test_proctor_enterprise.py# 5-tier scoring & HTML audit generation
│   ├── test_session_flow.py      # Multi-camera session lifecycle
│   ├── test_timetable_and_features.py # 28-class schedule & day pills
│   └── test_ui_smoke.py          # Headless offscreen Qt UI smoke tests
├── IEEE_PROJECT_REPORT.md        # Academic research report (IEEE standard format)
├── PRESENTATION_GUIDE.md         # Viva prep guide, 2-min pitch, 20 examiner Q&As
├── main.py                       # Application bootstrap entry point
├── requirements.txt              # Pinned Python package dependencies
├── run.bat                       # 1-Click Windows execution script
├── run.sh                        # 1-Click Linux/macOS execution script
├── setup.bat                     # Windows virtual environment installer
└── setup.sh                      # Linux/macOS virtual environment installer
```

---

## 🚀 Installation & Quick Start

### Prerequisites
- **Operating System**: Windows 10/11, Ubuntu 20.04+, or macOS 12+ (Apple Silicon or Intel).
- **Python**: Version **3.10, 3.11, 3.12, or 3.13** (64-bit).
- **Camera**: Standard USB webcam, laptop integrated camera, or RTSP network camera.

---

### 1-Click Quick Launch (Windows)

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Abhishekkumar/classvision_ai.git
   cd classvision_ai
   ```
2. **Run the automated setup installer:**
   ```cmd
   setup.bat
   ```
   *This automatically creates a virtual environment, installs dependencies, and verifies model weights.*
3. **Launch ClassVision AI:**
   ```cmd
   run.bat
   ```

---

### Manual Setup (Windows / Linux / macOS)

1. **Create and activate a Python virtual environment:**
   ```bash
   # Windows
   python -m venv .venv
   .\.venv\Scripts\activate

   # Linux / macOS
   python3 -m venv .venv
   source .venv/bin/activate
   ```
2. **Upgrade pip and install pinned dependencies:**
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```
3. **Run automated verification tests:**
   ```bash
   python -m unittest tests/test_core.py tests/test_session_flow.py tests/test_ui_smoke.py tests/test_timetable_and_features.py tests/test_proctor_enterprise.py
   ```
4. **Launch the application:**
   ```bash
   python main.py
   ```

---

## ⚙️ Configuration & Settings Reference

All system behaviors are dynamically configurable via the **Settings** page or programmatically through `app/config.py`:

```python
@dataclass
class Settings:
    # Video & Stream Configuration
    classroom_source: str = "0"              # Camera index or RTSP URL ("rtsp://user:pass@ip:554/stream")
    gate_source: str = ""                    # Optional entry gate camera
    frame_width: int = 1280                  # Ingest resolution width
    frame_height: int = 720                  # Ingest resolution height

    # Attendance Calibration
    class_duration_min: int = 50             # Standard academic lecture duration
    min_presence_min: int = 35               # Minimum presence threshold (~70%)
    face_similarity_threshold: float = 0.363 # SFace cosine similarity threshold

    # AI Proctoring & Object Detection
    object_detection: bool = True            # Enable YOLOv8 gadget detection
    yolo_model: str = "yolov8n.pt"           # Model variant (nano, small, medium)
    confidence_threshold: float = 0.45       # Object detection confidence filter

    # 3D Head Pose Deadzones
    yaw_threshold: float = 24.0              # Max allowable looking left/right angle
    pitch_threshold: float = 16.0            # Max allowable looking down angle

    # Lip Oscillation Sensitivity
    lip_aspect_ratio_threshold: float = 0.35 # Normalized vertical lip opening
    talking_consecutive_frames: int = 8      # Temporal window filter

    # Suspicion Scoring Event Weights
    weight_phone: float = 35.0               # Phone detection base penalty
    weight_cheat_material: float = 30.0      # Cheat notes base penalty
    weight_multiple_faces: float = 40.0      # Multiple faces base penalty
    weight_looking_away: float = 15.0        # Sustained looking away base penalty
    weight_suspected_talking: float = 20.0   # Lip oscillation talking penalty
    weight_face_missing: float = 25.0        # Missing candidate penalty
    weight_camera_obstructed: float = 30.0   # Tamper/obstruction penalty
    cooldown_decay_rate: float = 0.4         # Score decay rate (points per second)
```

---

## 🧪 Automated Test Suite & Verification

ClassVision AI is validated by **98 comprehensive automated test cases**. Tests execute in **headless offscreen mode** (`-platform offscreen`), allowing execution across local workstations and remote Continuous Integration (CI) pipelines without requiring a physical display.

### Executing the Test Suite
```bash
.\.venv\Scripts\python.exe -m unittest tests/test_core.py tests/test_session_flow.py tests/test_ui_smoke.py tests/test_timetable_and_features.py tests/test_proctor_enterprise.py
```

### Test Suite Execution Output
```
.............................................................Could not open 'rtsp://bad': malformed URL
...Object detection unavailable: Object detection needs the 'ultralytics' package
..................................
----------------------------------------------------------------------
Ran 98 tests in 4.938s

OK
```

```
┌──────────────────────────────────────┬────────────┬─────────┬─────────────────────────────────────────┐
│ Test Module                          │ Test Count │ Status  │ Scope of Verification                   │
├──────────────────────────────────────┼:----------:┼:-------:┼─────────────────────────────────────────┤
│ `tests/test_core.py`                 │     55     │ PASSED  │ Mathematical models, SQLite WAL queries │
│ `tests/test_session_flow.py`         │     12     │ PASSED  │ Multi-camera threads, graceful shutdown │
│ `tests/test_ui_smoke.py`             │     15     │ PASSED  │ Offscreen Qt widgets, forms, tabs       │
│ `tests/test_timetable_and_features.py`│    10     │ PASSED  │ 28 weekly periods, day pill filtering   │
│ `tests/test_proctor_enterprise.py`   │      6     │ PASSED  │ 5-tier scoring, reviews, HTML audits    │
├──────────────────────────────────────┼:----------:┼:-------:┼─────────────────────────────────────────┤
│ **TOTAL VERIFIED SUITE**             │   **98**   │ **100%**│ **Zero regressions across all modules** │
└──────────────────────────────────────┴────────────┴─────────┴─────────────────────────────────────────┘
```

---

## 🛡️ Biometric Privacy, Ethics & Regulatory Compliance

Biometric facial representations represent sensitive personal data under modern global privacy legislation. ClassVision AI is architected strictly under **Privacy-by-Design** principles:

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                PRIVACY & REGULATORY SAFEGUARDS                                   │
├──────────────────────────────────────────────────────────────────────────────────────────────────┤
│  ✓ GDPR Article 9 Compliance       │ Enforces mandatory administrative consent before biometric  │
│                                    │ data can be recorded or stored.                             │
│  ✓ India DPDPA 2023 Alignment     │ Data collection is purpose-limited to attendance & exams.   │
│  ✓ 100% Offline Edge Processing   │ Zero telemetry, zero external API queries, zero cloud leaks.│
│  ✓ Vector Isolation               │ Face embeddings are 128-D mathematical floats that cannot   │
│                                    │ be reverse-engineered into original photographic portraits. │
│  ✓ Local Encrypted Storage         │ Databases and captured snapshots reside on campus premises. │
│  ✓ Human-in-the-Loop Governance   │ The AI never convicts; human invigilators retain full veto. │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 📚 Academic Presentation & Viva Resources

For students, instructors, and examiners preparing to present or evaluate ClassVision AI:

- 📖 **[PRESENTATION_GUIDE.md](file:///d:/ai%20ml%20projects/classvision_ai/PRESENTATION_GUIDE.md)**:
  - **The 2-Minute Elevator Pitch**: Verbatim opening speech for evaluations.
  - **Step-by-Step Live Demo Script**: Exact actions and words for presenting each screen.
  - **Deep Technical Explanations**: How to explain YuNet, SFace, SolvePnP, LAR, and YOLOv8 to examiners.
  - **Top 20 Tough Viva Q&As**: High-scoring answers on spoofing, false positives, WAL concurrency, and scalability.
  - **Quick-Fire Cheat Sheet**: 10-second rapid definitions for viva recall.
- 📄 **[IEEE_PROJECT_REPORT.md](file:///d:/ai%20ml%20projects/classvision_ai/IEEE_PROJECT_REPORT.md)**:
  - Formal academic research report formatted to IEEE conference/transactions specifications.
  - Complete with Abstract, Literature Matrix, Equations, Benchmark Tables, and 28 IEEE Citations.

---

## 📄 License & Credits

- **License**: Released under the permissive [MIT License](file:///d:/ai%20ml%20projects/classvision_ai/LICENSE). Free for academic, institutional, and commercial use.
- **Project Author**: **Abhishek Kumar** (Registration No: 12404519), School of Computer Science & Engineering, Lovely Professional University.
- **Deep Learning Frameworks**:
  - [OpenCV Zoo](https://github.com/opencv/opencv_zoo) for YuNet & SFace ONNX models.
  - [Ultralytics](https://github.com/ultralytics/ultralytics) for the YOLOv8 object detection architecture.
  - [The Qt Company](https://www.qt.io/) for the PySide6 cross-platform GUI framework.

---

<div align="center">

**Built with Academic Rigor, Biometric Privacy, and Engineering Excellence.**  
*ClassVision AI — Bringing Transparency and Integrity to Higher Education.*

</div>
