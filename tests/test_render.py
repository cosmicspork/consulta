"""Output formatting."""

from __future__ import annotations

import json

import polars as pl
import pytest

from consulta import render


def test_csv(sample_df: pl.DataFrame) -> None:
    out = render.render(sample_df, "csv")
    assert out.splitlines()[0] == "app_id,email,score"
    assert "a@x.com" in out


def test_tsv(sample_df: pl.DataFrame) -> None:
    out = render.render(sample_df, "tsv")
    assert "\t" in out.splitlines()[0]


def test_json_roundtrips(sample_df: pl.DataFrame) -> None:
    rows = json.loads(render.render(sample_df, "json"))
    assert rows[0]["email"] == "a@x.com"
    assert len(rows) == 3


def test_markdown(sample_df: pl.DataFrame) -> None:
    out = render.render(sample_df, "markdown")
    lines = out.splitlines()
    assert lines[0] == "| app_id | email | score |"
    assert lines[1] == "| --- | --- | --- |"
    assert lines[2].startswith("| 1 | a@x.com |")


def test_markdown_escapes_pipes() -> None:
    df = pl.DataFrame({"note": ["a|b"]})
    assert "a\\|b" in render.render(df, "markdown")


def test_table_nonempty(sample_df: pl.DataFrame) -> None:
    out = render.render(sample_df, "table")
    assert "email" in out
    assert "a@x.com" in out


def test_unknown_format_raises(sample_df: pl.DataFrame) -> None:
    with pytest.raises(ValueError, match="unknown format"):
        render.render(sample_df, "yaml")
