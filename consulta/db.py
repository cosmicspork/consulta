"""Connect and run read-only queries, returning polars DataFrames.

The same code path runs against any SQLAlchemy backend — only the URL changes.
Every query goes through the read-only guard first, then executes inside a
read-only transaction (where the backend supports one) that is never committed.
"""

from __future__ import annotations

import contextlib
from typing import Any

import polars as pl
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection
from sqlalchemy.engine.url import make_url

# Fetch Oracle CLOB/BLOB as str/bytes rather than LOB locator objects, so result
# frames hold plain values. No-op when the oracle driver isn't installed.
with contextlib.suppress(Exception):
    import oracledb

    oracledb.defaults.fetch_lobs = False

from consulta.backends import Backend
from consulta.config import Config
from consulta.guard import assert_read_only


class DbError(Exception):
    pass


def connect(cfg: Config) -> Connection:
    try:
        engine = create_engine(make_url(cfg.database_url))
        return engine.connect()
    except Exception as e:
        raise DbError(f"connection failed: {e}") from e


def check(cfg: Config) -> None:
    """Open a connection and run the backend's trivial SELECT."""
    with connect(cfg) as conn:
        conn.execute(text(cfg.backend.select_one))


def run_query(
    cfg: Config,
    sql: str,
    params: dict[str, Any] | None = None,
    *,
    limit: int | None = None,
) -> pl.DataFrame:
    assert_read_only(sql)
    with connect(cfg) as conn:
        _begin_read_only(conn, cfg.backend)
        return _execute(conn, sql, params or {}, limit)


def _begin_read_only(conn: Connection, backend: Backend) -> None:
    # Defense in depth behind the SQL guard: ask the server to reject writes for
    # this transaction. Best-effort — a backend that doesn't support it (sqlite)
    # or rejects the syntax just falls back to the guard.
    if backend.read_only_stmt:
        with contextlib.suppress(Exception):
            conn.execute(text(backend.read_only_stmt))


def _execute(
    conn: Connection,
    sql: str,
    params: dict[str, Any],
    limit: int | None,
) -> pl.DataFrame:
    bound = {name: (value() if callable(value) else value) for name, value in params.items()}
    result = conn.execute(text(sql), bound)
    if not result.returns_rows:
        return pl.DataFrame()

    columns = list(result.keys())
    mappings = result.mappings()
    rows = mappings.fetchmany(limit) if limit and limit > 0 else mappings.all()
    if not rows:
        return pl.DataFrame({col: [] for col in columns})
    return pl.DataFrame([dict(row) for row in rows])
