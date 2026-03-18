"""Tests for the file watcher."""

import threading
import time
from pathlib import Path

import pytest

from arrow.watcher import FileWatcher


class TestFileWatcher:
    def test_start_stop(self, tmp_path):
        watcher = FileWatcher(tmp_path, lambda: None)
        watcher.start()
        assert watcher.running
        watcher.stop()
        assert not watcher.running

    def test_double_start(self, tmp_path):
        watcher = FileWatcher(tmp_path, lambda: None)
        watcher.start()
        watcher.start()  # Should not crash
        assert watcher.running
        watcher.stop()

    def test_stop_without_start(self, tmp_path):
        watcher = FileWatcher(tmp_path, lambda: None)
        watcher.stop()  # Should not crash
        assert not watcher.running

    def test_callback_on_file_change(self, tmp_path):
        triggered = threading.Event()

        def callback():
            triggered.set()

        watcher = FileWatcher(tmp_path, callback, debounce_sec=0.1)
        watcher.start()

        try:
            # Create a file to trigger the watcher
            time.sleep(0.2)  # Give watcher time to start
            (tmp_path / "new_file.py").write_text("print('hello')")
            assert triggered.wait(timeout=3.0), "Watcher callback was not triggered"
        finally:
            watcher.stop()

    def test_debounce(self, tmp_path):
        call_count = 0
        lock = threading.Lock()

        def callback():
            nonlocal call_count
            with lock:
                call_count += 1

        watcher = FileWatcher(tmp_path, callback, debounce_sec=0.5)
        watcher.start()

        try:
            time.sleep(0.2)
            # Rapid file changes — should debounce into a single callback
            for i in range(5):
                (tmp_path / f"file_{i}.py").write_text(f"x = {i}")
                time.sleep(0.05)

            time.sleep(1.5)  # Wait for debounce + callback

            with lock:
                # Should have been called roughly once due to debounce
                assert call_count >= 1
                assert call_count <= 3  # Allow some slack
        finally:
            watcher.stop()
