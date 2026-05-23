"""
NeonDB connection helper.

Reads the connection string from the `db_string` env var (set in .env).
"""
import os
import sys
from contextlib import contextmanager

try:
    import psycopg
except ImportError:
    sys.exit("ERROR: pip install 'psycopg[binary]'")

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def get_dsn() -> str:
    dsn = (
        os.environ.get("db_string")
        or os.environ.get("DB_STRING")
        or os.environ.get("DATABASE_URL")
    )
    if not dsn:
        raise RuntimeError(
            "Database connection string not found in environment. "
            "Set db_string, DB_STRING, or DATABASE_URL."
        )
    return dsn.strip().strip('"').strip("'")


@contextmanager
def get_connection():
    """Yield a psycopg connection. Commits on success, rolls back on error."""
    conn = psycopg.connect(get_dsn())
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
