"""Database connection pool for the API layer."""

import os
from contextlib import contextmanager
import psycopg2
from psycopg2.pool import ThreadedConnectionPool

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "5432")),
    "dbname": os.getenv("DB_NAME", "observatory"),
    "user": os.getenv("DB_USER", "observatory"),
    "password": os.getenv("DB_PASSWORD", "observatory_dev_2026"),
}

_pool = None


def get_pool() -> ThreadedConnectionPool:
    global _pool
    if _pool is None or _pool.closed:
        _pool = ThreadedConnectionPool(minconn=2, maxconn=10, **DB_CONFIG)
    return _pool


@contextmanager
def get_db():
    """Yield a connection from the pool, auto-return on exit."""
    pool = get_pool()
    conn = pool.getconn()
    try:
        yield conn
    finally:
        pool.putconn(conn)
