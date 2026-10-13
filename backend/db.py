"""MySQL connection pool and connection helpers."""

from contextlib import contextmanager
from threading import Lock

from mysql.connector import pooling

from config import Config


_pool = None
_pool_lock = Lock()


def get_connection():
    """Borrow a connection from the configured pool."""
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                _pool = pooling.MySQLConnectionPool(
                    pool_name="santhi_cashew_pool",
                    pool_size=Config.DB_POOL_SIZE,
                    pool_reset_session=True,
                    host=Config.DB_HOST,
                    port=Config.DB_PORT,
                    user=Config.DB_USER,
                    password=Config.DB_PASSWORD,
                    database=Config.DB_NAME,
                    charset="utf8mb4",
                    collation="utf8mb4_unicode_ci",
                    autocommit=False,
                )
    return _pool.get_connection()


@contextmanager
def cursor(dictionary=True):
    """Yield a pooled connection and cursor, closing both afterward."""
    connection = get_connection()
    try:
        db_cursor = connection.cursor(dictionary=dictionary)
        try:
            yield connection, db_cursor
        except Exception:
            connection.rollback()
            raise
        finally:
            db_cursor.close()
    finally:
        connection.close()
