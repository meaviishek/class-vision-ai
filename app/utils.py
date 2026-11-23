"""Formatting helpers shared by the backend and the UI (no Qt imports here)."""
from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

# Colours used for boxes drawn over live video (bright variants for dark footage).
VIDEO_OK = "#3DDC97"
VIDEO_WARN = "#FFB84D"
VIDEO_BAD = "#FF6B5E"
VIDEO_IDLE = "#9DB0C3"


def fmt_clock(ts: Optional[float], with_sec: bool = True) -> str:
    if not ts:
        return "-"
    return datetime.fromtimestamp(ts).strftime("%H:%M:%S" if with_sec else "%H:%M")


def fmt_datetime(ts: Optional[float]) -> str:
    if not ts:
        return "-"
    return datetime.fromtimestamp(ts).strftime("%d %b %Y, %H:%M")


def fmt_dur(sec: float) -> str:
    sec = int(max(0, round(sec)))
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h {m:02d}m"
    if m:
        return f"{m}m {s:02d}s"
    return f"{s}s"


def fmt_mmss(sec: float) -> str:
    sec = int(max(0, round(sec)))
    return f"{sec // 60:02d}:{sec % 60:02d}"


def slug(text: str, maxlen: int = 40) -> str:
    """ASCII-only, filesystem-safe version of a name or registration number (short enough for Windows paths)."""
    return re.sub(r"[^A-Za-z0-9]+", "_", text or "").strip("_")[:maxlen].strip("_") or "student"
