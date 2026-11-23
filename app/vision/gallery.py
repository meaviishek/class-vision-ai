"""Gallery of enrolled face embeddings and nearest-student matching (cosine similarity)."""
from __future__ import annotations

from typing import Iterable, Optional, Tuple

import numpy as np


class Gallery:
    """Read-only after construction, so it can be shared with worker threads."""

    def __init__(self, ids: np.ndarray, embs: np.ndarray):
        ids = np.asarray(ids, np.int64)
        if len(ids):
            embs = np.asarray(embs, np.float32).reshape(len(ids), -1)
            norms = np.linalg.norm(embs, axis=1, keepdims=True)
            embs = embs / np.maximum(norms, 1e-9)
            order = np.argsort(ids, kind="stable")
            ids, embs = ids[order], embs[order]
            self.students, self._starts = np.unique(ids, return_index=True)
        else:
            embs = np.zeros((0, 128), np.float32)
            self.students, self._starts = np.zeros((0,), np.int64), np.zeros((0,), np.int64)
        self.ids, self.embs = ids, embs

    @classmethod
    def from_db(cls, db, student_ids: Optional[Iterable[int]] = None) -> "Gallery":
        ids, embs = db.embeddings(student_ids)
        return cls(ids, embs)

    def __len__(self) -> int:
        return int(len(self.students))

    def identify(self, emb: np.ndarray, threshold: float, margin: float) -> Tuple[Optional[int], float]:
        """Return (student_id or None, best_similarity). A match needs similarity >= threshold
        and must beat the second-best *student* by at least `margin` (guards look-alikes)."""
        if len(self.students) == 0:
            return None, 0.0
        sims = self.embs @ np.asarray(emb, np.float32)
        per_student = np.maximum.reduceat(sims, self._starts)
        order = np.argsort(per_student)[::-1]
        best = float(per_student[order[0]])
        second = float(per_student[order[1]]) if len(order) > 1 else -1.0
        if best >= threshold and (best - second) >= margin:
            return int(self.students[order[0]]), best
        return None, best
