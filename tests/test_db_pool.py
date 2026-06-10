import threading

import pytest

from core_engine.db_pool import PostgresConnectionPool, PoolExhaustedError


class FakeCursor:
    def __init__(self, conn):
        self._conn = conn
        self.description = None

    def execute(self, sql, params=()):
        self._conn.executed.append((sql, params))
        if self._conn.fail_with is not None:
            exc = self._conn.fail_with
            self._conn.fail_with = None  # fail once, then succeed on retry
            raise exc
        if sql.strip().lower().startswith("select"):
            self.description = [("col",)]

    def fetchall(self):
        return [(1,)]

    def close(self):
        pass


class FakeConnection:
    def __init__(self):
        self.committed = 0
        self.rolled_back = 0
        self.closed = False
        self.executed = []
        self.fail_with = None

    def cursor(self):
        return FakeCursor(self)

    def commit(self):
        self.committed += 1

    def rollback(self):
        self.rolled_back += 1

    def close(self):
        self.closed = True


class DeadlockError(Exception):
    pgcode = "40P01"  # deadlock_detected


def make_pool(**kwargs):
    created = []

    def factory():
        conn = FakeConnection()
        created.append(conn)
        return conn

    pool = PostgresConnectionPool(connection_factory=factory, **kwargs)
    return pool, created


def test_connection_commits_on_success():
    pool, created = make_pool(minconn=1, maxconn=2)
    with pool.connection() as conn:
        conn.cursor().execute("INSERT INTO t VALUES (1)")
    assert created[0].committed == 1
    assert created[0].rolled_back == 0


def test_connection_rolls_back_and_discards_on_error():
    pool, created = make_pool(minconn=1, maxconn=2)
    with pytest.raises(ValueError):
        with pool.connection():
            raise ValueError("boom")
    assert created[0].rolled_back == 1
    assert created[0].closed is True  # broken connection discarded, not reused


def test_pool_reuses_connection():
    pool, created = make_pool(minconn=1, maxconn=2)
    with pool.connection():
        pass
    with pool.connection():
        pass
    # Same single connection reused for both transactions.
    assert len(created) == 1


def test_pool_grows_to_maxconn_then_blocks():
    pool, created = make_pool(minconn=0, maxconn=2, acquire_timeout=0.2)
    c1 = pool._acquire()
    c2 = pool._acquire()
    assert len(created) == 2
    with pytest.raises(PoolExhaustedError):
        pool._acquire()  # cap reached, none returned -> timeout
    pool._return(c1)
    pool._return(c2)


def test_execute_retries_on_deadlock():
    pool, created = make_pool(minconn=1, maxconn=2, max_retries=3, backoff_base=0.0)

    # Prime exactly the first acquired connection to raise a deadlock once;
    # the retry must acquire a fresh connection and succeed.
    original = pool._acquire
    primed = {"done": False}

    def acquire_with_one_failure():
        conn = original()
        if not primed["done"]:
            conn.fail_with = DeadlockError()
            primed["done"] = True
        return conn

    pool._acquire = acquire_with_one_failure
    rows = pool.execute("SELECT 1")
    assert rows == [(1,)]


def test_execute_does_not_retry_non_transient():
    pool, created = make_pool(minconn=1, maxconn=2, max_retries=3, backoff_base=0.0)

    class FatalError(Exception):
        pgcode = "23505"  # unique_violation, not retryable

    with pool.connection() as conn:
        pass
    # Prime the next acquired connection to fail fatally.
    created[0].fail_with = FatalError()
    with pytest.raises(FatalError):
        pool.execute("INSERT INTO t VALUES (1)")


def test_invalid_sizing_rejected():
    with pytest.raises(ValueError):
        PostgresConnectionPool(minconn=3, maxconn=1, connection_factory=FakeConnection)


def test_thread_safety_smoke():
    pool, created = make_pool(minconn=0, maxconn=4)
    errors = []

    def worker():
        try:
            for _ in range(20):
                with pool.connection() as conn:
                    conn.cursor().execute("SELECT 1")
        except Exception as e:  # pragma: no cover
            errors.append(e)

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    assert len(created) <= 4  # never exceeds the pool cap
