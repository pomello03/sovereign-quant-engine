"""
db_pool — thread-safe Postgres connection pool for the Sovereign Quant Engine.

Addresses the persistence/concurrency vulnerability (Vuln 3): concurrent agents
sharing a single raw connection cause "packets out of sync" / state drift. This
module provides a bounded, thread-safe pool with:

* transactional ``connection()`` context manager (commit on success, rollback
  on error, connection always returned to the pool),
* exponential backoff retry on transient deadlock / serialization failures,
* an injectable ``connection_factory`` so the pool is fully unit-testable
  without a live database (and so psycopg2 stays an optional dependency).

DB settings mirror jesse_workspace/config.py (Postgres via DB_* env vars).
"""

import os
import time
import threading
import contextlib
import queue

# Transient Postgres SQLSTATE codes worth retrying:
#   40001 serialization_failure, 40P01 deadlock_detected
_RETRYABLE_SQLSTATES = {"40001", "40P01"}


class PoolExhaustedError(RuntimeError):
    """Raised when no connection becomes available within the timeout."""


def default_connection_factory():  # pragma: no cover - requires live DB / psycopg2
    """Creates a real psycopg2 connection from DB_* environment variables."""
    import psycopg2
    return psycopg2.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        port=int(os.environ.get("DB_PORT", 5432)),
        dbname=os.environ.get("DB_NAME", "jesse_db"),
        user=os.environ.get("DB_USER", "jesse_user"),
        password=os.environ.get("DB_PASSWORD", "jesse_password"),
    )


def _sqlstate(exc):
    """Best-effort extraction of a SQLSTATE code from a DB exception."""
    code = getattr(exc, "pgcode", None)
    if code:
        return code
    inner = getattr(exc, "orig", None)
    return getattr(inner, "pgcode", None)


class PostgresConnectionPool:
    """A bounded, thread-safe pool of Postgres connections."""

    def __init__(self, minconn: int = 1, maxconn: int = 5,
                 connection_factory=None, acquire_timeout: float = 10.0,
                 max_retries: int = 3, backoff_base: float = 0.1):
        if maxconn < 1 or minconn < 0 or minconn > maxconn:
            raise ValueError("Invalid pool sizing: require 0 <= minconn <= maxconn and maxconn >= 1")
        self._factory = connection_factory or default_connection_factory
        self._maxconn = maxconn
        self._acquire_timeout = acquire_timeout
        self._max_retries = max_retries
        self._backoff_base = backoff_base
        self._pool = queue.LifoQueue(maxsize=maxconn)
        self._created = 0
        self._lock = threading.Lock()
        self._closed = False
        for _ in range(minconn):
            self._pool.put(self._new_connection())

    def _new_connection(self):
        with self._lock:
            self._created += 1
        return self._factory()

    def _acquire(self):
        if self._closed:
            raise RuntimeError("Pool is closed")
        # Fast path: reuse an idle connection.
        try:
            return self._pool.get_nowait()
        except queue.Empty:
            pass
        # Grow the pool if we are under the cap.
        with self._lock:
            can_grow = self._created < self._maxconn
        if can_grow:
            return self._new_connection()
        # Otherwise block until one is returned.
        try:
            return self._pool.get(timeout=self._acquire_timeout)
        except queue.Empty:
            raise PoolExhaustedError(
                f"No DB connection available within {self._acquire_timeout}s"
            )

    def _return(self, conn, discard: bool = False):
        if discard:
            with self._lock:
                self._created -= 1
            try:
                conn.close()
            except Exception:
                pass
            return
        try:
            self._pool.put_nowait(conn)
        except queue.Full:  # pragma: no cover - defensive
            with self._lock:
                self._created -= 1
            conn.close()

    @contextlib.contextmanager
    def connection(self):
        """
        Yields a pooled connection inside a transaction.

        Commits on clean exit, rolls back on exception. A connection that
        errored is discarded (not reused) to avoid propagating a broken
        session ("packets out of sync") to the next caller.
        """
        conn = self._acquire()
        try:
            yield conn
            conn.commit()
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            self._return(conn, discard=True)
            raise
        else:
            self._return(conn)

    def execute(self, sql, params=None):
        """
        Runs a statement with deadlock-aware retry and exponential backoff.

        Retries only transient serialization/deadlock failures; other errors
        propagate immediately. Returns ``cursor.fetchall()`` when the cursor
        produced rows, else None.
        """
        attempt = 0
        while True:
            try:
                with self.connection() as conn:
                    cur = conn.cursor()
                    cur.execute(sql, params or ())
                    rows = cur.fetchall() if cur.description else None
                    cur.close()
                    return rows
            except Exception as exc:
                if _sqlstate(exc) in _RETRYABLE_SQLSTATES and attempt < self._max_retries:
                    time.sleep(self._backoff_base * (2 ** attempt))
                    attempt += 1
                    continue
                raise

    def closeall(self):
        self._closed = True
        while True:
            try:
                conn = self._pool.get_nowait()
            except queue.Empty:
                break
            try:
                conn.close()
            except Exception:
                pass
        with self._lock:
            self._created = 0
