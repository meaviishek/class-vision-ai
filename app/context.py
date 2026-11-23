"""Application-wide state shared by every page: database, settings and change notifications."""
from __future__ import annotations

from pathlib import Path
from typing import Optional, Set

from PySide6.QtCore import QObject, Signal

from .config import DB_PATH, SETTINGS_PATH, Settings, ensure_dirs, load_settings, save_settings
from .db import Database


class AppContext(QObject):
    settings_changed = Signal()
    students_changed = Signal()
    sessions_changed = Signal()
    timetable_changed = Signal()

    def __init__(self, db_path: Optional[Path] = None, settings_path: Optional[Path] = None):
        super().__init__()
        ensure_dirs()
        self.settings_path = Path(settings_path or SETTINGS_PATH)
        self.db = Database(db_path or DB_PATH)
        self.db.mark_interrupted()                        # nothing can be running at start-up
        self.settings: Settings = load_settings(self.settings_path)
        # Webcam numbers that a running session has open. A webcam can only be used by one thing at a time,
        # so the enrollment page and a second session check this before they try to open the same one.
        self.live_sources: Set[int] = set()

    def update_settings(self, settings: Settings) -> None:
        self.settings = settings
        save_settings(settings, self.settings_path)
        self.settings_changed.emit()

    def close(self) -> None:
        """Called when the application quits."""
        try:
            self.db.close()
        except Exception:                                 # closing twice, or already closed
            pass
