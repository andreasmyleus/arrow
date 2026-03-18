"""File watcher for automatic background re-indexing using watchdog."""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Optional

from watchdog.events import FileSystemEventHandler, FileSystemEvent
from watchdog.observers import Observer

logger = logging.getLogger(__name__)


class _IndexHandler(FileSystemEventHandler):
    """Debounced handler that triggers re-indexing on file changes."""

    def __init__(self, callback, debounce_sec: float = 2.0):
        super().__init__()
        self._callback = callback
        self._debounce_sec = debounce_sec
        self._timer: Optional[threading.Timer] = None
        self._lock = threading.Lock()

    def _schedule(self):
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
            self._timer = threading.Timer(self._debounce_sec, self._callback)
            self._timer.daemon = True
            self._timer.start()

    def on_modified(self, event: FileSystemEvent):
        if not event.is_directory:
            self._schedule()

    def on_created(self, event: FileSystemEvent):
        if not event.is_directory:
            self._schedule()

    def on_deleted(self, event: FileSystemEvent):
        if not event.is_directory:
            self._schedule()


class FileWatcher:
    """Watches a directory for changes and triggers incremental re-indexing."""

    def __init__(self, root: str | Path, on_change_callback, debounce_sec: float = 2.0):
        self.root = Path(root).resolve()
        self._observer: Optional[Observer] = None
        self._handler = _IndexHandler(on_change_callback, debounce_sec)

    def start(self) -> None:
        """Start watching for file changes."""
        if self._observer is not None:
            return

        self._observer = Observer()
        self._observer.schedule(self._handler, str(self.root), recursive=True)
        self._observer.daemon = True
        self._observer.start()
        logger.info("File watcher started for %s", self.root)

    def stop(self) -> None:
        """Stop watching."""
        if self._observer is not None:
            self._observer.stop()
            self._observer.join(timeout=5)
            self._observer = None
            logger.info("File watcher stopped")

    @property
    def running(self) -> bool:
        return self._observer is not None and self._observer.is_alive()
