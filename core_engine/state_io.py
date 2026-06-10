"""
state_io — robust shared-state I/O primitives for the Sovereign Quant Engine.

Addresses two failure-backpropagation vulnerabilities:

* Silent State Propagation (Vuln 1): a downstream agent must never act on a
  stale signal file. ``read_json_fresh`` rejects files older than a max age,
  and ``atomic_write_json`` guarantees readers never observe a partial write.

* Race Conditions on shared state (Vuln 3): ``file_lock`` provides
  cross-platform advisory locking (fcntl on POSIX, msvcrt on Windows) on a
  ``.lock`` sidecar, so concurrent reader/writer agents serialize access to
  blueprint / report state files without corrupting them.
"""

import json
import os
import time
import contextlib

# Platform-specific locking backends. fcntl is the production (Linux/Hetzner)
# path; msvcrt keeps the test suite runnable on Windows.
try:
    import fcntl  # POSIX
    _HAS_FCNTL = True
except ImportError:  # pragma: no cover - Windows
    fcntl = None
    _HAS_FCNTL = False

try:
    import msvcrt  # Windows
    _HAS_MSVCRT = True
except ImportError:  # pragma: no cover - POSIX
    msvcrt = None
    _HAS_MSVCRT = False


class StaleStateError(RuntimeError):
    """Raised when a state file is older than the allowed freshness window."""


def atomic_write_json(path: str, data, indent: int = 2) -> None:
    """
    Atomically writes ``data`` as JSON to ``path``.

    Writes to a temporary file in the same directory and ``os.replace``s it
    into place. os.replace is atomic on both POSIX and Windows, so a concurrent
    reader sees either the old file or the fully written new file, never a
    partial one.
    """
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    tmp_path = f"{path}.{os.getpid()}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=indent)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, path)


def file_age_seconds(path: str) -> float:
    """Returns the age of ``path`` in seconds based on its mtime."""
    return time.time() - os.path.getmtime(path)


def read_json_fresh(path: str, max_age_seconds: float = 60.0):
    """
    Reads JSON from ``path`` only if it is fresher than ``max_age_seconds``.

    Raises FileNotFoundError if missing, StaleStateError if too old. A
    ``max_age_seconds`` of None disables the freshness check (plain read).
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"State file not found: {path}")
    if max_age_seconds is not None:
        age = file_age_seconds(path)
        if age > max_age_seconds:
            raise StaleStateError(
                f"State file '{os.path.basename(path)}' is stale: "
                f"{age:.1f}s old (max {max_age_seconds:.1f}s). "
                f"Upstream agent may have failed silently."
            )
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


@contextlib.contextmanager
def file_lock(path: str, exclusive: bool = True, timeout: float = 10.0,
              poll_interval: float = 0.05):
    """
    Cross-platform advisory file lock on a ``<path>.lock`` sidecar.

    Args:
        path: the state file being protected (the sidecar is ``path + '.lock'``).
        exclusive: True for a write lock, False for a shared read lock.
            (Shared locks are only differentiated on POSIX; on Windows the
            sidecar is always locked exclusively, which is safe but stricter.)
        timeout: max seconds to wait for the lock before raising TimeoutError.
        poll_interval: retry cadence while waiting (Windows backend).
    """
    lock_path = f"{path}.lock"
    os.makedirs(os.path.dirname(os.path.abspath(lock_path)), exist_ok=True)
    lock_file = open(lock_path, "a+")
    try:
        _acquire(lock_file, exclusive, timeout, poll_interval)
        try:
            yield lock_file
        finally:
            _release(lock_file)
    finally:
        lock_file.close()


def _acquire(lock_file, exclusive, timeout, poll_interval):
    deadline = time.time() + timeout
    if _HAS_FCNTL:
        flags = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
        while True:
            try:
                fcntl.flock(lock_file.fileno(), flags | fcntl.LOCK_NB)
                return
            except OSError:
                if time.time() >= deadline:
                    raise TimeoutError(f"Could not acquire lock within {timeout}s")
                time.sleep(poll_interval)
    elif _HAS_MSVCRT:  # pragma: no cover - Windows-only branch
        while True:
            try:
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
                return
            except OSError:
                if time.time() >= deadline:
                    raise TimeoutError(f"Could not acquire lock within {timeout}s")
                time.sleep(poll_interval)
    # No locking backend available: degrade to a no-op (single-process use).


def _release(lock_file):
    if _HAS_FCNTL:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
    elif _HAS_MSVCRT:  # pragma: no cover - Windows-only branch
        try:
            lock_file.seek(0)
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
        except OSError:
            pass
