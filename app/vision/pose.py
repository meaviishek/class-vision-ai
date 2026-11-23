"""Coarse head pose from 5 facial landmarks (good to roughly +/-10 degrees, enough for thresholds).

Conventions (camera frame: x right, y down, z away from camera):
    yaw   > 0  face turned towards the image's right
    pitch > 0  face tilted up (looking up)
    roll  > 0  face's right side tilted down in the image
"""
from __future__ import annotations

import math
from typing import Optional, Tuple

import cv2
import numpy as np

# Generic face model in millimetres, nose tip at the origin. Order matches YuNet's landmarks:
# right eye, left eye (image-left first), nose tip, right mouth corner, left mouth corner.
_MODEL = np.array([
    [-31.5, -42.0, 38.0],
    [31.5, -42.0, 38.0],
    [0.0, 0.0, 0.0],
    [-25.0, 38.0, 33.0],
    [25.0, 38.0, 33.0],
], dtype=np.float64)
_IPD_MM = 63.0


def head_pose(landmarks: np.ndarray, frame_w: int, frame_h: int) -> Optional[Tuple[float, float, float]]:
    pts = np.asarray(landmarks, np.float64).reshape(5, 2)
    if pts[0, 0] > pts[1, 0]:                            # left/right arrive mirrored: swap pairs to fit the model
        pts = pts[[1, 0, 2, 4, 3]]
    ipd = float(np.linalg.norm(pts[0] - pts[1]))
    if ipd < 4.0:
        return None
    f = float(frame_w)                                   # rough focal length guess
    cam = np.array([[f, 0, frame_w / 2.0], [0, f, frame_h / 2.0], [0, 0, 1]], np.float64)
    z0 = f * _IPD_MM / ipd                               # start from a frontal pose at the right depth
    tvec = np.array([[(pts[2, 0] - frame_w / 2.0) * z0 / f],
                     [(pts[2, 1] - frame_h / 2.0) * z0 / f],
                     [z0]], np.float64)
    rvec = np.zeros((3, 1), np.float64)
    try:
        ok, rvec, tvec = cv2.solvePnP(_MODEL, pts, cam, None, rvec, tvec, True, cv2.SOLVEPNP_ITERATIVE)
    except cv2.error:
        return None
    if not ok:
        return None
    rot, _ = cv2.Rodrigues(rvec)
    nose_dir = rot @ np.array([0.0, 0.0, -1.0])          # where the nose points
    right_dir = rot @ np.array([1.0, 0.0, 0.0])
    yaw = math.degrees(math.atan2(nose_dir[0], -nose_dir[2]))
    pitch = math.degrees(math.atan2(-nose_dir[1], math.hypot(nose_dir[0], nose_dir[2])))
    roll = math.degrees(math.atan2(right_dir[1], right_dir[0]))
    return yaw, pitch, roll


def project_model(yaw: float, pitch: float, frame_w: int, frame_h: int,
                  depth_mm: float = 600.0, center=None) -> np.ndarray:
    """Synthesise 5 landmarks for a given pose (used by the tests)."""
    psi, phi = math.radians(-yaw), math.radians(-pitch)
    ry = np.array([[math.cos(psi), 0, math.sin(psi)], [0, 1, 0], [-math.sin(psi), 0, math.cos(psi)]])
    rx = np.array([[1, 0, 0], [0, math.cos(phi), -math.sin(phi)], [0, math.sin(phi), math.cos(phi)]])
    pts = (ry @ rx @ _MODEL.T).T
    f = float(frame_w)
    nx, ny = center if center is not None else (frame_w / 2.0, frame_h / 2.0)   # where the nose lands
    pts = pts + np.array([(nx - frame_w / 2.0) * depth_mm / f,
                          (ny - frame_h / 2.0) * depth_mm / f, depth_mm])
    return np.stack([frame_w / 2.0 + f * pts[:, 0] / pts[:, 2],
                     frame_h / 2.0 + f * pts[:, 1] / pts[:, 2]], axis=1).astype(np.float32)
