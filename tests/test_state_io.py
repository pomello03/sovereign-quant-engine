import json
import os
import time
import threading

import pytest

from core_engine.state_io import (
    atomic_write_json,
    read_json_fresh,
    file_age_seconds,
    file_lock,
    StaleStateError,
)


def test_atomic_write_and_read(tmp_path):
    path = str(tmp_path / "state.json")
    atomic_write_json(path, {"a": 1, "b": [2, 3]})
    with open(path, "r", encoding="utf-8") as f:
        assert json.load(f) == {"a": 1, "b": [2, 3]}
    # No leftover temp files in the directory
    assert [p.name for p in tmp_path.iterdir()] == ["state.json"]


def test_atomic_write_overwrites(tmp_path):
    path = str(tmp_path / "state.json")
    atomic_write_json(path, {"v": 1})
    atomic_write_json(path, {"v": 2})
    with open(path, "r", encoding="utf-8") as f:
        assert json.load(f)["v"] == 2


def test_read_json_fresh_passes_for_new_file(tmp_path):
    path = str(tmp_path / "alpha.json")
    atomic_write_json(path, {"signal": "long"})
    assert read_json_fresh(path, max_age_seconds=60) == {"signal": "long"}


def test_read_json_fresh_rejects_stale(tmp_path):
    path = str(tmp_path / "alpha.json")
    atomic_write_json(path, {"signal": "long"})
    # Backdate the mtime to simulate a silently-failed upstream agent.
    old = time.time() - 120
    os.utime(path, (old, old))
    with pytest.raises(StaleStateError):
        read_json_fresh(path, max_age_seconds=60)


def test_read_json_fresh_disabled_check(tmp_path):
    path = str(tmp_path / "alpha.json")
    atomic_write_json(path, {"signal": "long"})
    old = time.time() - 9999
    os.utime(path, (old, old))
    # max_age_seconds=None disables the freshness guard.
    assert read_json_fresh(path, max_age_seconds=None) == {"signal": "long"}


def test_read_json_fresh_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        read_json_fresh(str(tmp_path / "nope.json"), max_age_seconds=60)


def test_file_age_seconds(tmp_path):
    path = str(tmp_path / "x.json")
    atomic_write_json(path, {})
    assert file_age_seconds(path) < 5


def test_file_lock_serializes_writers(tmp_path):
    """Two threads incrementing a shared counter under an exclusive lock must
    not lose updates (the lock serializes the read-modify-write)."""
    path = str(tmp_path / "counter.json")
    atomic_write_json(path, {"n": 0})
    iterations = 50

    def worker():
        for _ in range(iterations):
            with file_lock(path, exclusive=True):
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                data["n"] += 1
                atomic_write_json(path, data)

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    with open(path, "r", encoding="utf-8") as f:
        assert json.load(f)["n"] == 2 * iterations


def test_file_lock_context_releases(tmp_path):
    """Acquiring the lock again after release must succeed quickly."""
    path = str(tmp_path / "s.json")
    atomic_write_json(path, {})
    with file_lock(path, exclusive=True):
        pass
    with file_lock(path, exclusive=True):
        pass  # would raise/hang if the first lock was never released
