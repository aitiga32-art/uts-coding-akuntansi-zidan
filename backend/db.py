import os
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row


def database_url():
    url = os.getenv("DATABASE_URL", "")
    if not url:
        raise RuntimeError("DATABASE_URL belum diatur. Ikuti README untuk menghubungkan database.")
    return url


@contextmanager
def connection():
    # Setiap operasi memakai transaksi baru; exit normal commit, exception rollback.
    with psycopg.connect(database_url(), row_factory=dict_row, connect_timeout=5) as conn:
        conn.execute("SET TIME ZONE 'UTC'")
        yield conn
