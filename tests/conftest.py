"""Test fixtures. Sqlite stands in for any backend — only the URL differs."""

from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest
from sqlalchemy import create_engine, text

from consulta.backends import SQLITE
from consulta.config import Config


@pytest.fixture
def sample_df() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "app_id": [1, 2, 3],
            "email": ["a@x.com", "b@y.net", "c@z.org"],
            "score": [10, 30, 20],
        }
    )


@pytest.fixture
def sqlite_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "consulta_test.sqlite"
    engine = create_engine(f"sqlite:///{db_path}")
    with engine.connect() as conn:
        conn.execute(
            text("CREATE TABLE apps (app_id INTEGER, email TEXT, score INTEGER, strm TEXT)")
        )
        conn.execute(
            text("INSERT INTO apps VALUES (:a, :b, :c, :d)"),
            [
                {"a": 1, "b": "a@x.com", "c": 10, "d": "1261"},
                {"a": 2, "b": "b@y.net", "c": 30, "d": "1261"},
                {"a": 3, "b": "c@z.org", "c": 20, "d": "1265"},
            ],
        )
        conn.commit()
    return db_path


def sqlite_config(db_path: Path) -> Config:
    return Config(
        backend=SQLITE,
        host=None,
        port=None,
        database=str(db_path),
        user=None,
        password=None,
        database_url=f"sqlite:///{db_path}",
        fetch_limit=1000,
        env_path=None,
        profile=None,
    )
