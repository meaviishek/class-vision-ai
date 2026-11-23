"""Camera worker. Three cooperating threads keep the preview smooth while heavy AI work runs:

    grabber thread    reads frames as fast as the camera delivers them (keeps only the latest)
    process thread    runs `processor.process(frame, ts)` at `process_fps`, emits results + overlays
    this QThread      emits downscaled preview frames (~20 fps) and reconnects if the camera drops
"""
from __future__ import annotations

import logging
import os
import sys
import threading
import time
from typing import Optional, Union

import cv2
from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QImage

log = logging.getLogger(__name__)
PREVIEW_FPS = 20.0


def parse_source(text) -> Union[int, str]:
    """'0' -> webcam 0; anything else (rtsp://..., http://..., a video file path) stays text."""
    t = str(text).strip()
    return int(t) if t.isascii() and t.isdigit() else t          # '²'.isdigit() is True but int('²') fails


def webcam_index(text) -> Optional[int]:
    """The webcam number if `text` names a local webcam (only one program can open it at a time), else None."""
    src = parse_source(text)
    return src if isinstance(src, int) else None


def open_capture(src: Union[int, str], width: int, height: int) -> Optional[cv2.VideoCapture]:
    if isinstance(src, int):
        cap = cv2.VideoCapture(src, cv2.CAP_DSHOW) if sys.platform.startswith("win") else cv2.VideoCapture(src)
        if cap.isOpened():
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    else:
        cap = cv2.VideoCapture(src)
    if cap is not None and cap.isOpened():
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    return cap


def to_qimage(frame, max_w: int) -> QImage:
    h, w = frame.shape[:2]
    if w > max_w:
        frame = cv2.resize(frame, (max_w, int(h * max_w / w)), interpolation=cv2.INTER_AREA)
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    h, w = rgb.shape[:2]
    return QImage(rgb.data, w, h, w * 3, QImage.Format.Format_RGB888).copy()


class _Grabber(threading.Thread):
    def __init__(self, cap: cv2.VideoCapture, is_file: bool):
        super().__init__(daemon=True)
        self.cap, self.is_file = cap, is_file
        self._lock = threading.Lock()
        self._frame = None
        self._fid = 0
        self._stop_ev = threading.Event()

    def run(self) -> None:
        try:
            delay = 0.0
            if self.is_file:                              # pace video files at their own frame rate
                delay = 1.0 / max(1.0, min(self.cap.get(cv2.CAP_PROP_FPS) or 25.0, 60.0))
            while not self._stop_ev.is_set():
                ok, frame = self.cap.read()
                if not ok or frame is None:
                    break
                with self._lock:
                    self._frame, self._fid = frame, self._fid + 1
                if delay:
                    time.sleep(delay)
        finally:
            self.cap.release()                            # the thread that reads is the one that releases

    def latest(self):
        with self._lock:
            return self._frame, self._fid

    def stop(self) -> None:
        self._stop_ev.set()


class CameraWorker(QThread):
    frame = Signal(QImage)         # preview image
    result = Signal(object)        # whatever the processor returned (FrameResult, EnrollFrame, ...)
    overlays = Signal(object)      # list of Overlay boxes for the preview
    status = Signal(str)

    def __init__(self, source, processor, process_fps: float, width: int, height: int,
                 preview_width: int = 960, parent=None):
        super().__init__(parent)
        self.source, self.processor = source, processor
        self.process_fps = max(0.2, float(process_fps))
        self.width, self.height, self.preview_width = int(width), int(height), int(preview_width)
        self._stop_ev = threading.Event()

    def request_stop(self) -> None:
        """Ask the thread to finish without waiting, so several cameras can wind down at the same time."""
        self._stop_ev.set()

    def stop(self) -> None:
        self._stop_ev.set()
        self.wait(5000)

    def _process_loop(self, grabber: _Grabber) -> None:
        interval = 1.0 / self.process_fps
        last_fid, next_at, last_err = -1, 0.0, 0.0
        while not self._stop_ev.is_set() and grabber.is_alive():
            frame, fid = grabber.latest()
            now = time.time()
            if frame is None or fid == last_fid or now < next_at:
                time.sleep(0.01)
                continue
            last_fid, next_at = fid, now + interval
            try:
                payload, overlays = self.processor.process(frame, now)
            except Exception as exc:                      # keep the camera running; report at most every 5 s
                log.exception("Frame processing failed")
                if now - last_err > 5.0:
                    self.status.emit(f"Processing error: {exc}")
                    last_err = now
                continue
            self.result.emit(payload)
            self.overlays.emit(overlays)

    def run(self) -> None:
        try:
            self._run()
        except Exception as exc:                              # never let the camera thread die without a word
            log.exception("Camera thread crashed")
            self.status.emit(f"Camera stopped: {exc}")

    def _run(self) -> None:
        is_file = isinstance(self.source, str) and os.path.isfile(self.source)
        while not self._stop_ev.is_set():
            try:
                cap = open_capture(self.source, self.width, self.height)
            except Exception as exc:                          # e.g. a malformed URL: retry like any failed open
                log.warning("Could not open %r: %s", self.source, exc)
                cap = None
            if cap is None or not cap.isOpened():
                if cap is not None:
                    cap.release()
                self.status.emit(f"Cannot open camera '{self.source}'. Retrying...")
                self._stop_ev.wait(2.0)
                continue
            self.status.emit("Live")
            grabber = _Grabber(cap, is_file)
            grabber.start()
            worker = threading.Thread(target=self._process_loop, args=(grabber,), daemon=True)
            worker.start()
            last_fid, last_preview, warned = -1, 0.0, False
            while not self._stop_ev.is_set() and grabber.is_alive():
                frame, fid = grabber.latest()
                now = time.time()
                if frame is None or fid == last_fid or now - last_preview < 1.0 / PREVIEW_FPS:
                    time.sleep(0.004)
                    continue
                last_fid, last_preview = fid, now
                try:
                    img = to_qimage(frame, self.preview_width)
                except Exception as exc:                      # an odd frame must not end the camera
                    if not warned:
                        log.warning("Cannot show a frame in the preview: %s", exc)
                        warned = True
                    continue
                self.frame.emit(img)
            grabber.stop()
            worker.join(timeout=2.0)
            grabber.join(timeout=2.0)                     # the grabber releases the capture itself
            if self._stop_ev.is_set():
                break
            if is_file:                                   # a video file does not reconnect or loop
                got_frames = grabber.latest()[1] > 0
                self.status.emit("Video ended" if got_frames else "Cannot read frames from this video file")
                self._stop_ev.wait()                      # idle until the session is stopped
            else:
                self.status.emit("Camera disconnected. Reconnecting...")
                self._stop_ev.wait(1.5)
        self.status.emit("Stopped")
