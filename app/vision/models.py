"""Model files: where they live and how to fetch them (OpenCV Zoo, about 39 MB in total)."""
from __future__ import annotations

import hashlib
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from ..config import MODELS_DIR

_GITHUB = "https://github.com/opencv/opencv_zoo/raw/main/models"
_HF = "https://huggingface.co/opencv"

Progress = Callable[[str, int, int], None]


@dataclass(frozen=True)
class ModelSpec:
    urls: Tuple[str, ...]      # tried in order until one gives a file that passes verification
    size: int                  # exact size of the official file in bytes
    sha256: str                # SHA-256 of the official file
    min_size: int              # a file already on disk counts as installed if it is at least this big


# Size and SHA-256 are the values recorded in the OpenCV Zoo's Git LFS pointers for these two files.
# A download only counts if it matches them, which rules out HTML error pages, LFS pointer files and
# truncated transfers. Files placed in models/ by hand only need to pass the min_size check.
MODELS: Dict[str, ModelSpec] = {
    "face_detection_yunet_2023mar.onnx": ModelSpec(
        urls=(f"{_GITHUB}/face_detection_yunet/face_detection_yunet_2023mar.onnx",
              f"{_HF}/face_detection_yunet/resolve/main/face_detection_yunet_2023mar.onnx"),
        size=232_589, sha256="8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4",
        min_size=100_000),
    "face_recognition_sface_2021dec.onnx": ModelSpec(
        urls=(f"{_GITHUB}/face_recognition_sface/face_recognition_sface_2021dec.onnx",
              f"{_HF}/face_recognition_sface/resolve/main/face_recognition_sface_2021dec.onnx"),
        size=38_696_353, sha256="0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79",
        min_size=10_000_000),
}

DETECTOR = MODELS_DIR / "face_detection_yunet_2023mar.onnx"
RECOGNIZER = MODELS_DIR / "face_recognition_sface_2021dec.onnx"


def missing_models(specs: Optional[Dict[str, ModelSpec]] = None, folder: Optional[Path] = None) -> List[str]:
    specs, folder = specs or MODELS, folder or MODELS_DIR
    out = []
    for name, spec in specs.items():
        p = folder / name
        if not p.exists() or p.stat().st_size < spec.min_size:
            out.append(name)
    return out


def _fetch(url: str, dest: Path, spec: ModelSpec, name: str, progress: Optional[Progress]) -> None:
    """Download one URL to `dest` and verify size and checksum. Raises on any problem and never leaves
    a half-written file at `dest`."""
    tmp = dest.with_suffix(".part")
    digest = hashlib.sha256()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ClassVision/1.0"})
        with urllib.request.urlopen(req, timeout=60) as resp, open(tmp, "wb") as fh:
            total = int(resp.headers.get("Content-Length") or 0) or spec.size
            done = 0
            while True:
                chunk = resp.read(1 << 16)
                if not chunk:
                    break
                fh.write(chunk)
                digest.update(chunk)
                done += len(chunk)
                if progress:
                    progress(name, done, total)
        if done != spec.size:
            raise RuntimeError(f"received {done} bytes, expected {spec.size}")
        if digest.hexdigest() != spec.sha256:
            raise RuntimeError("the file does not match the official checksum")
        tmp.replace(dest)
    finally:
        tmp.unlink(missing_ok=True)


def download_models(progress: Optional[Progress] = None, specs: Optional[Dict[str, ModelSpec]] = None,
                    folder: Optional[Path] = None) -> None:
    """Download every missing model, trying each mirror in turn.
    progress(name, bytes_done, bytes_total) is optional. Raises RuntimeError listing every failure."""
    specs, folder = specs or MODELS, folder or MODELS_DIR
    folder.mkdir(parents=True, exist_ok=True)
    for name in missing_models(specs, folder):
        spec, errors = specs[name], []
        for url in spec.urls:
            try:
                _fetch(url, folder / name, spec, name, progress)
                break
            except Exception as exc:                     # network, HTTP, size or checksum problems
                errors.append(f"{url}: {exc}")
        else:
            raise RuntimeError(f"Could not download {name}.\n" + "\n".join(errors))
