"""First-run check: versions, face models, camera, and one detection + recognition pass.

    python scripts/doctor.py              uses camera 0
    python scripts/doctor.py 1            another camera
    python scripts/doctor.py clip.mp4     a video file
    python scripts/doctor.py rtsp://...   an IP camera

Every line starts with [ok], [info], [warn] or [FAIL]. Fix the FAIL lines and run it again.
"""
from __future__ import annotations

import importlib.util
import sys
import time
from pathlib import Path
from typing import List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

OK, INFO, WARN, FAIL = "ok", "info", "warn", "FAIL"


def _open(cv2, source: str):
    if source.isdigit():
        index = int(source)
        return cv2.VideoCapture(index, cv2.CAP_DSHOW) if sys.platform.startswith("win") else cv2.VideoCapture(index)
    return cv2.VideoCapture(source)


def _grab_frame(cv2, source: str):
    """Read a few frames (a webcam's first ones are often dark) and return the last good one, or None."""
    cap = _open(cv2, source)
    if cap is None or not cap.isOpened():
        return None, None, None
    is_camera = source.isdigit()
    frame = None
    try:
        for _ in range(15):
            ok, img = cap.read()
            if ok and img is not None:
                frame = img
            elif frame is not None:
                break                                    # a video file ran out; keep what we have
            if is_camera:
                time.sleep(0.05)
        return frame, True, float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
    finally:
        cap.release()


def main(argv: Optional[List[str]] = None, db_path: Optional[Path] = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    source = argv[0] if argv else "0"
    problems = 0

    def say(level: str, text: str) -> None:
        nonlocal problems
        problems += level == FAIL
        print(f"[{level:<4}] {text}")

    def finish() -> int:
        if problems:
            print("\nFix the items marked FAIL, then run this again.")
            return 1
        print("\nAll checks passed. Start the app with:  python main.py")
        return 0

    # ------------------------------------------------------------------ install
    import platform
    say(OK if sys.version_info >= (3, 10) else FAIL, f"Python {platform.python_version()}"
        + ("" if sys.version_info >= (3, 10) else " (3.10 or newer is needed)"))
    try:
        import numpy as np
        import cv2
    except ImportError as exc:
        say(FAIL, f"{exc.name} is not installed. Run:  pip install -r requirements.txt")
        return finish()
    say(OK, f"numpy {np.__version__}, OpenCV {cv2.__version__}")
    if int(cv2.__version__.split(".")[0]) >= 5:
        say(WARN, "OpenCV 5 is not what this project was built and tested with. If anything misbehaves, run:  "
                  "pip install \"opencv-python-headless<5\"")
    if not (hasattr(cv2, "FaceDetectorYN") and hasattr(cv2, "FaceRecognizerSF")):
        say(FAIL, "This OpenCV build has no face detection or recognition. Run:  "
                  "pip install \"opencv-python-headless>=4.8,<5\"")
        return finish()
    try:
        import PySide6
        say(OK, f"PySide6 {getattr(PySide6, '__version__', '(version unknown)')}")
    except ImportError:
        say(FAIL, "PySide6 is not installed. Run:  pip install -r requirements.txt")
    if sys.platform.startswith("linux"):
        from importlib import metadata
        names = {(d.metadata["Name"] or "").lower() for d in metadata.distributions()}
        if "opencv-python" in names or "opencv-contrib-python" in names:
            say(WARN, "The full opencv-python package is installed next to PySide6; on Linux its bundled Qt can stop the "
                      "app from starting. Run:  pip uninstall opencv-python opencv-contrib-python  and  "
                      "pip install opencv-python-headless")
    has_yolo = importlib.util.find_spec("ultralytics") is not None
    say(OK if has_yolo else INFO, "Phone / book / laptop detection is available" if has_yolo else
        "Phone / book / laptop detection is not installed (optional: pip install ultralytics)")

    # ------------------------------------------------------------------- models
    from app.vision import models
    missing = models.missing_models()
    if missing:
        say(FAIL, "Face models are missing: " + ", ".join(missing) + ".  Run:  python scripts/download_models.py")
        return finish()
    say(OK, f"Face models found in {models.MODELS_DIR}")

    # ------------------------------------------------------------------- camera
    frame, _, fps = _grab_frame(cv2, source)
    if frame is None:
        say(FAIL, f"Cannot read frames from '{source}'. Close other apps that use the camera, try another number "
                  f"(1, 2...), or pass a video file path.")
        return finish()
    h, w = frame.shape[:2]
    say(OK, f"Source '{source}' gives {w}x{h}" + (f" at about {fps:.0f} fps" if fps else ""))
    if w < 1280 and not source.isdigit():
        say(WARN, "This video is under 1280 pixels wide; faces in a classroom shot may be too small to recognise.")

    # ---------------------------------------------------------------- detection
    from app.config import ensure_dirs, load_settings
    from app.vision.engine import FaceEngine
    from app.vision.pose import head_pose
    settings = load_settings()
    try:
        engine = FaceEngine(settings.det_score_threshold)
        faces = engine.detect(frame)
    except Exception as exc:                              # corrupt model file, unsupported OpenCV build, ...
        say(FAIL, f"The face detector could not run: {exc}")
        return finish()
    if len(faces) == 0:
        say(WARN, "No face found in this frame. Face the camera in good light and run this again.")
        return finish()
    faces = faces[faces[:, 2].argsort()[::-1]]            # largest first
    say(OK, f"Found {len(faces)} face{'s' if len(faces) != 1 else ''}")
    for i, f in enumerate(faces[:8], start=1):
        say(INFO, f"face {i}: {f[2]:.0f} px wide ({100 * f[2] / w:.0f}% of the frame), detector score {f[14]:.2f}")
    main_face = faces[0]
    if main_face[2] < settings.min_face_px:
        say(WARN, f"The largest face is under {settings.min_face_px} px wide. Faces that small are tracked but not "
                  f"recognised: move closer or use a higher-resolution camera.")
    if main_face[2] / w >= settings.gate_min_face_ratio:
        say(INFO, "The largest face is big enough to count as 'standing at the gate'.")
    else:
        say(INFO, f"The largest face is smaller than the {100 * settings.gate_min_face_ratio:.0f}% of the frame width "
                  f"needed to count as 'standing at the gate'.")
    pose = head_pose(main_face[4:14].reshape(5, 2), w, h)
    if pose is not None:
        yaw, pitch, roll = (int(round(v)) for v in pose)      # whole degrees; ints never print as "-0"
        say(INFO, f"Head pose of the largest face: yaw {yaw:+d}, pitch {pitch:+d}, roll {roll:+d} degrees. "
                  f"Facing the camera should read near 0; turning towards the right of the image should make yaw "
                  f"positive, and looking up should make pitch positive.")

    # -------------------------------------------------------------- recognition
    try:
        emb = engine.embed(frame, main_face)
    except Exception as exc:
        say(FAIL, f"The face recogniser could not run: {exc}")
        return finish()
    if emb.shape != (128,) or abs(float(np.linalg.norm(emb)) - 1.0) > 1e-3:
        say(FAIL, "The recogniser returned an unexpected result. Re-download the models.")
        return finish()
    say(OK, "The recognition model works (128-number face fingerprint)")
    from app.db import Database
    from app.vision.gallery import Gallery
    if db_path is None:
        ensure_dirs()
    db = Database(db_path) if db_path is not None else Database()
    try:
        gallery = Gallery.from_db(db)
        if len(gallery) == 0:
            say(INFO, "No one is enrolled yet. Enroll students in the app, then run this again to test recognition.")
        else:
            sid, score = gallery.identify(emb, settings.recog_threshold, settings.recog_margin)
            if sid is None:
                say(INFO, f"This face matches no enrolled student (best similarity {score:.2f}, needs "
                          f"{settings.recog_threshold:.2f}).")
            else:
                who = db.get_student(sid)
                say(OK, f"Recognised as {who['name']} ({who['reg_no']}), similarity {score:.2f}")
    finally:
        db.close()
    return finish()


if __name__ == "__main__":
    sys.exit(main())
