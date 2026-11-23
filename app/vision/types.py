"""Plain data containers passed between the vision workers and the UI/services."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import numpy as np


@dataclass(frozen=True)
class Overlay:
    """A box to draw over the video preview. Coordinates are normalised to 0..1."""
    x: float
    y: float
    w: float
    h: float
    label: str = ""
    color: str = "#3DDC97"
    sub: str = ""
    tid: int = -1


@dataclass(frozen=True)
class TrackView:
    """Immutable snapshot of one tracked face (safe to hand to another thread)."""
    track_id: int
    bbox: Tuple[float, float, float, float]    # x, y, w, h in pixels
    sid: Optional[int]                          # confirmed student id, None if unknown/undecided
    score: float
    visible: bool                               # detected in this frame (False = coasting)
    face_ratio: float                           # face width / frame width
    yaw: float                                  # + = turned towards image right
    pitch: float                                # + = looking up
    roll: float
    age: float                                  # seconds since the track appeared
    votes: int                                  # quality-gated recognition attempts so far
    live_ok: bool                               # head-movement liveness passed
    last_seen: float
    mouth_open: float = 0.0


@dataclass(frozen=True)
class ObjectDet:
    label: str
    conf: float
    bbox: Tuple[float, float, float, float]


@dataclass
class FrameResult:
    ts: float
    width: int
    height: int
    tracks: List[TrackView]
    objects: List[ObjectDet] = field(default_factory=list)
    identity_changes: List[Tuple[int, Optional[int], Optional[int]]] = field(default_factory=list)
    frame: Optional[np.ndarray] = None          # BGR frame, kept for evidence snapshots
    notes: List[str] = field(default_factory=list)   # things the user should hear about (a feature switched itself off)
