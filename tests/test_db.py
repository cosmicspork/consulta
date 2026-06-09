"""db.run_query against sqlite via SQLAlchemy — the cross-backend code path."""

from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest

from consulta import db
from consulta.guard import ReadOnlyViolation

from .conftest import sqlite_config


def test_run_query_returns_named_columns(sqlite_db: Path) -> None:
    cfg = sqlite_config(sqlite_db)
    frame = db.run_query(cfg, "SELECT app_id, email FROM apps ORDER BY app_id")
    assert frame.columns == ["app_id", "email"]
    assert frame.height == 3
    assert frame["app_id"].to_list() == [1, 2, 3]


def test_run_query_binds_named_params(sqlite_db: Path) -> None:
    cfg = sqlite_config(sqlite_db)
    frame = db.run_query(
        cfg,
        "SELECT app_id FROM apps WHERE strm = :strm ORDER BY app_id",
        {"strm": "1261"},
    )
    assert frame["app_id"].to_list() == [1, 2]


def test_run_query_respects_limit(sqlite_db: Path) -> None:
    cfg = sqlite_config(sqlite_db)
    frame = db.run_query(cfg, "SELECT app_id FROM apps ORDER BY app_id", limit=2)
    assert frame.height == 2


def test_run_query_zero_limit_returns_all(sqlite_db: Path) -> None:
    cfg = sqlite_config(sqlite_db)
    frame = db.run_query(cfg, "SELECT app_id FROM apps", limit=0)
    assert frame.height == 3


def test_run_query_empty_result_keeps_columns(sqlite_db: Path) -> None:
    cfg = sqlite_config(sqlite_db)
    frame = db.run_query(cfg, "SELECT app_id, email FROM apps WHERE app_id = :id", {"id": -1})
    assert frame.height == 0
    assert frame.columns == ["app_id", "email"]


def test_run_query_refuses_write_before_connecting(sqlite_db: Path) -> None:
    cfg = sqlite_config(sqlite_db)
    with pytest.raises(ReadOnlyViolation):
        db.run_query(cfg, "DELETE FROM apps")
    # the row is still there
    frame = db.run_query(cfg, "SELECT count(*) AS n FROM apps")
    assert frame["n"].to_list() == [3]


def test_describe_lists_table_columns(sqlite_db: Path) -> None:
    cfg = sqlite_config(sqlite_db)
    assert cfg.backend.describe_query is not None
    frame = db.run_query(cfg, cfg.backend.describe_query, {"t": "apps"})
    assert frame["name"].to_list() == ["app_id", "email", "score", "strm"]


def test_describe_query_passes_the_guard() -> None:
    from consulta.backends import BACKENDS
    from consulta.guard import assert_read_only

    for backend in BACKENDS.values():
        if backend.describe_query is not None:
            assert_read_only(backend.describe_query)


def test_check_connects(sqlite_db: Path) -> None:
    cfg = sqlite_config(sqlite_db)
    db.check(cfg)  # raises on failure


def test_types_preserved(sqlite_db: Path) -> None:
    cfg = sqlite_config(sqlite_db)
    frame = db.run_query(cfg, "SELECT app_id, email FROM apps LIMIT 1")
    assert frame.schema["app_id"] == pl.Int64
    assert frame.schema["email"] == pl.Utf8
